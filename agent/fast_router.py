from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from agent.schemas import AgentPlan, AgentStep
from agent.tool_registry import AgentToolRegistry, AgentToolSpec
from agent.tool_selector import AgentToolSelector
from ai.llm_manager import LLMManager, LLMProviderError
from config.settings import settings
from runtime.hybrid_runtime import choose_router_route
from tools.internet_manager import InternetToolManager

logger = logging.getLogger("aura.agent.fast_router")

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_REF_RE = re.compile(r"\$\{step\d+\.[A-Za-z0-9_.-]+\}")


@dataclass(frozen=True)
class FastRouteDecision:
    route: str
    complexity: str = "fast"
    need_memory: bool = False
    confidence: float = 0.0
    speech_ack: str = ""
    plan: AgentPlan | None = None
    elapsed_seconds: float = 0.0


class FastStructuredRouter:
    """One-pass low-latency router + strict JSON multi-tool planner.

    User text is treated as untrusted data. The model can only name tools that
    were pre-selected from AgentToolRegistry; actions/categories are inferred by
    deterministic code and the resulting AgentPlan is still validated, guarded
    against loops, and authorized by SecurityPolicyEngine before execution.
    """

    _ALLOWED_ARGS = {
        "weather": {"location", "tomorrow"},
        "maps.locate": {"query"},
        "maps.directions": {"destination", "origin", "travelmode"},
        "web.search": {"query", "count"},
        "web.fetch": {"url"},
        "knowledge.reference.local": {"subject", "allow_web"},
        "knowledge.reference.web": {"subject", "allow_web"},
    }

    _ARG_HINTS = {
        "weather": "location:string requis; tomorrow:boolean optionnel",
        "maps.locate": "query:string requis",
        "maps.directions": "destination:string requis; origin:string optionnel; travelmode:driving|walking|bicycling|transit optionnel",
        "web.search": "query:string requis; count:int 1..8 optionnel",
        "web.fetch": "url:http(s) explicite présent dans la demande utilisateur",
        "knowledge.reference.local": "subject:string requis; allow_web doit rester false",
        "knowledge.reference.web": "subject:string requis; allow_web doit rester true",
    }

    def __init__(
        self,
        llm_manager: LLMManager,
        registry: AgentToolRegistry,
        *,
        max_steps: int = 6,
        selector_max_tools: int = 5,
    ):
        self.llm_manager = llm_manager
        self.registry = registry
        self.max_steps = max(2, int(max_steps))
        self.selector = AgentToolSelector(registry, max_tools=selector_max_tools)
        self.last_decision = FastRouteDecision("legacy")

    def should_try(self, text: str) -> bool:
        return bool(settings.AGENT_LLM_PLANNER_ENABLED and self.selector.should_try_structured(text))

    @staticmethod
    def effective_num_ctx() -> int:
        # Ollama can recreate/reload a runner when the same model is requested
        # with a different context size. AURA's router shares llama3.2:3b with
        # the fast/voice brain, so keep the runner profile identical and avoid
        # the 16s reload observed after a 1536 -> 2048 context switch.
        if str(settings.AGENT_ROUTER_MODEL).casefold() == str(settings.LLM_VOICE_MODEL).casefold():
            return int(settings.LLM_VOICE_NUM_CTX)
        return int(settings.AGENT_ROUTER_NUM_CTX)

    @staticmethod
    def _tool_contract(spec: AgentToolSpec) -> dict[str, Any]:
        return {
            "tool": spec.name,
            "required": list(spec.required_args),
            "args": FastStructuredRouter._ARG_HINTS.get(spec.name, ""),
        }

    def _messages(self, text: str, specs: tuple[AgentToolSpec, ...]) -> list[dict[str, str]]:
        tools_json = json.dumps([self._tool_contract(spec) for spec in specs], ensure_ascii=False, separators=(",", ":"))
        system = (
            "Routeur JSON AURA. Réponds uniquement en JSON brut. "
            "Si la demande exige au moins 2 outils autorisés: "
            '{"route":"agent","confidence":0.9,"steps":[{"tool":"...","args":{}}]}. ' 
            "Sinon: {\"route\":\"legacy\",\"confidence\":1,\"steps\":[]}. "
            "N'invente ni lieu ni URL. Réutilise uniquement les lieux du texte. "
            "Outils=" + tools_json
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": str(text or "").strip()},
        ]

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any] | None:
        clean = _JSON_FENCE_RE.sub("", str(raw or "").strip()).strip()
        if not clean:
            return None
        start = clean.find("{")
        end = clean.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(clean[start:end + 1])
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @classmethod
    def _sanitize_args(cls, tool: str, args: Any, user_text: str) -> dict[str, Any] | None:
        if not isinstance(args, dict):
            return None
        allowed = cls._ALLOWED_ARGS.get(tool)
        if not allowed or any(str(key) not in allowed for key in args):
            return None
        out: dict[str, Any] = {}
        for key, value in args.items():
            key = str(key)
            if isinstance(value, str):
                value = value.strip()
                if len(value) > 512:
                    return None
            out[key] = value

        if tool == "web.fetch":
            url = str(out.get("url") or "").strip()
            explicit_urls = {match.rstrip(".,;!?") for match in _URL_RE.findall(user_text or "")}
            if url not in explicit_urls:
                return None
        elif tool == "web.search":
            try:
                out["count"] = max(1, min(8, int(out.get("count", settings.WEB_SEARCH_RESULT_COUNT))))
            except (TypeError, ValueError):
                out["count"] = int(settings.WEB_SEARCH_RESULT_COUNT)
        elif tool == "weather":
            out["tomorrow"] = bool(out.get("tomorrow", False))
            raw_location = str(out.get("location") or "").strip()
            safe_location = InternetToolManager.resolve_weather_location(
                user_text,
                raw_location,
            )
            if not safe_location:
                return None
            out["location"] = safe_location
        elif tool == "maps.directions":
            travelmode = str(out.get("travelmode") or "driving").strip().casefold()
            if travelmode not in {"driving", "walking", "bicycling", "transit"}:
                travelmode = "driving"
            out["travelmode"] = travelmode
        elif tool == "knowledge.reference.local":
            out["allow_web"] = False
        elif tool == "knowledge.reference.web":
            out["allow_web"] = True
        return out

    def _to_plan(self, payload: dict[str, Any], text: str, specs: tuple[AgentToolSpec, ...]) -> AgentPlan | None:
        if str(payload.get("route") or "").strip().casefold() != "agent":
            return None
        rows = payload.get("steps")
        if not isinstance(rows, list) or not (2 <= len(rows) <= self.max_steps):
            return None
        allowed_names = {spec.name for spec in specs}
        steps: list[AgentStep] = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                return None
            tool = str(row.get("tool") or "").strip()
            if tool not in allowed_names:
                return None
            spec = self.registry.by_name(tool)
            if spec is None:
                return None
            args = self._sanitize_args(tool, row.get("args") or {}, text)
            if args is None:
                return None
            steps.append(AgentStep(
                id=f"step{index}",
                tool=spec.name,
                action=spec.action,
                args=args,
                category=spec.category,
                description=spec.description,
            ))
        # This optional LLM route is reserved for genuinely cross-domain work.
        # It must not manufacture a "multi-step" plan by querying two variants
        # of the same capability (for example local+web knowledge) when one tool
        # would have been sufficient.
        domains = set()
        for step in steps:
            if step.category == "maps":
                domains.add("maps")
            elif step.category == "weather":
                domains.add("weather")
            elif step.category in {"web_search", "web_fetch", "news"}:
                domains.add("web")
            elif step.category == "knowledge_reference":
                domains.add("knowledge")
            else:
                domains.add(step.category or step.tool)
        if len(domains) < 2:
            return None
        return AgentPlan(
            objective=str(text or "").strip(),
            steps=tuple(steps),
            source="fast-structured-router",
            stop_on_error=False,
        )

    def route(self, text: str) -> FastRouteDecision:
        started = time.perf_counter()
        specs = self.selector.select(text)
        if len(specs) < 2:
            decision = FastRouteDecision("legacy", elapsed_seconds=time.perf_counter() - started)
            self.last_decision = decision
            return decision
        try:
            route = choose_router_route(text)
            raw = self.llm_manager.generate(
                self._messages(text, specs),
                provider=route.provider,
                model=route.model,
                keep_alive="remote" if route.remote else settings.AGENT_ROUTER_KEEP_ALIVE,
                num_ctx=self.effective_num_ctx(),
                num_predict=settings.AGENT_ROUTER_NUM_PREDICT,
                temperature=settings.AGENT_ROUTER_TEMPERATURE,
                top_p=settings.AGENT_ROUTER_TOP_P,
                force_non_stream=True,
                read_timeout=settings.AGENT_ROUTER_READ_TIMEOUT,
            )
        except LLMProviderError as exc:
            logger.info("Fast router unavailable: %s", exc)
            decision = FastRouteDecision("legacy", elapsed_seconds=time.perf_counter() - started)
            self.last_decision = decision
            return decision
        except Exception:
            logger.exception("Fast router unexpected failure")
            decision = FastRouteDecision("legacy", elapsed_seconds=time.perf_counter() - started)
            self.last_decision = decision
            return decision

        payload = self._extract_json(raw)
        if payload is None:
            logger.info("Fast router rejected non-JSON response chars=%d", len(str(raw or "")))
            decision = FastRouteDecision("legacy", elapsed_seconds=time.perf_counter() - started)
            self.last_decision = decision
            return decision

        plan = self._to_plan(payload, text, specs)
        try:
            confidence = max(0.0, min(1.0, float(payload.get("confidence") or 0.0)))
        except (TypeError, ValueError):
            confidence = 0.0
        if plan is None or confidence < settings.AGENT_ROUTER_MIN_CONFIDENCE:
            decision = FastRouteDecision(
                "legacy",
                complexity=str(payload.get("complexity") or "fast")[:16],
                need_memory=bool(payload.get("need_memory", False)),
                confidence=confidence,
                speech_ack=str(payload.get("speech_ack") or "")[:80],
                elapsed_seconds=time.perf_counter() - started,
            )
        else:
            decision = FastRouteDecision(
                "agent",
                complexity=str(payload.get("complexity") or "fast")[:16],
                need_memory=bool(payload.get("need_memory", False)),
                confidence=confidence,
                speech_ack=str(payload.get("speech_ack") or "")[:80],
                plan=plan,
                elapsed_seconds=time.perf_counter() - started,
            )
        self.last_decision = decision
        metrics = getattr(self.llm_manager, "last_metrics", None)
        logger.info(
            "Fast router decision route=%s confidence=%.2f tools=%s elapsed=%.3fs load=%.3fs prompt=%.3fs gen=%.3fs out=%d",
            decision.route, decision.confidence,
            ",".join(step.tool for step in decision.plan.steps) if decision.plan else "none",
            decision.elapsed_seconds, float(getattr(metrics, "load_seconds", 0.0) or 0.0),
            float(getattr(metrics, "prompt_eval_seconds", 0.0) or 0.0),
            float(getattr(metrics, "eval_seconds", 0.0) or 0.0),
            int(getattr(metrics, "output_tokens", 0) or 0),
        )
        return decision
