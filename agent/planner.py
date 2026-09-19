from __future__ import annotations

import re

from agent.schemas import AgentPlan, AgentStep
from agent.tool_registry import AgentToolRegistry
from tools.internet_manager import InternetToolManager
from tools.models import ToolPlan

# Explicit sequencing only for the generic splitter. Natural route+weather
# phrasing is handled by the dedicated deterministic composite below so it does
# not need an LLM router just to understand "météo à l'arrivée".
_SEQUENCE_RE = re.compile(
    r"\s*(?:;|\b(?:puis|ensuite|et\s+puis|et\s+ensuite|apr[eè]s\s+cela|apres\s+cela)\b)\s*",
    re.IGNORECASE,
)
_ACTION_ET_RE = re.compile(
    r"\s+et\s+(?=(?:donne(?:-moi)?|montre(?:-moi)?|affiche(?:-moi)?|"
    r"cherche(?:-moi)?|recherche(?:-moi)?|trouve(?:-moi)?|v[ée]rifie|regarde|"
    r"indique(?:-moi)?|dis(?:-moi)?|quelle\s+est\s+la\s+m[ée]t[ée]o|m[ée]t[ée]o)\b)",
    re.IGNORECASE,
)
_WEATHER_HINT_RE = re.compile(r"\b(?:m[ée]t[ée]o|temps|temp[ée]rature|pleuv|vent|humidit[ée])\b", re.I)
_ROUTE_WORD_RE = re.compile(r"\b(?:itin[ée]raire|trajet|route)\b", re.I)

# Stop destination capture before the second intent begins. This is deliberately
# conservative and targets natural French formulations observed in runtime logs.
_DEST_STOP = r"(?=\s*(?:,|;|\.|\?|!|\b(?:puis|ensuite|ainsi\s+que|et)\b|\bj['’]aimerais\b|\bje\s+voudrais\b|$))"
_EXPLICIT_ROUTE_RE = re.compile(
    rf"\b(?:itin[ée]raire|trajet|route)\s+(?:de|depuis)\s+(.+?)\s+(?:à|a|vers|jusqu['’]à|jusqu'a)\s+(.+?){_DEST_STOP}",
    re.I,
)
_NATURAL_ROUTE_RE = re.compile(
    rf"\b(?:je\s+(?:vais|pars|me\s+rends?|dois\s+aller)|aller)\s+(?:de|depuis)\s+(.+?)\s+(?:à|a|vers)\s+(.+?){_DEST_STOP}",
    re.I,
)
_WEATHER_AT_RE = re.compile(
    r"\b(?:m[ée]t[ée]o|temps|temp[ée]rature)\s+(?:à|a|pour|sur)\s+(.+?)(?=\s*(?:[?.!,;]|$))",
    re.I,
)
_DESTINATION_PRONOUNS = {
    "l'arrivée", "l arrivee", "arrivée", "arrivee", "la destination", "destination",
    "sur place", "là-bas", "la bas", "à l'arrivée", "a l arrivee",
}


class DeterministicAgentPlanner:
    """Conservative multi-tool planner built from AURA's existing parsers.

    Common route+weather formulations are resolved deterministically first. The
    optional small LLM router is therefore reserved for genuinely ambiguous
    cross-domain requests instead of paying several seconds for phrases AURA can
    parse safely itself.
    """

    def __init__(
        self,
        internet_manager: InternetToolManager,
        registry: AgentToolRegistry,
        *,
        max_steps: int = 6,
    ):
        self.internet_manager = internet_manager
        self.registry = registry
        self.max_steps = max(2, int(max_steps))

    @staticmethod
    def _split(text: str) -> list[str]:
        clean = re.sub(r"\s+", " ", str(text or "").strip())
        if not clean:
            return []
        parts = [p.strip(" ,") for p in _SEQUENCE_RE.split(clean) if p.strip(" ,")]
        if len(parts) < 2:
            parts = [p.strip(" ,") for p in _ACTION_ET_RE.split(clean) if p.strip(" ,")]
        return parts

    @staticmethod
    def _clean_place(value: str) -> str:
        value = re.sub(r"\s+", " ", str(value or "")).strip(" ,.;?!")
        return value[:120]

    @classmethod
    def _extract_route_pair(cls, text: str) -> tuple[str, str] | None:
        raw = re.sub(r"\s+", " ", str(text or "").strip())
        for pattern in (_EXPLICIT_ROUTE_RE, _NATURAL_ROUTE_RE):
            match = pattern.search(raw)
            if not match:
                continue
            origin = cls._clean_place(match.group(1))
            destination = cls._clean_place(match.group(2))
            if len(origin) >= 2 and len(destination) >= 2:
                return origin, destination
        return None

    @classmethod
    def _weather_place_for_route(cls, text: str, destination: str) -> str:
        match = _WEATHER_AT_RE.search(str(text or ""))
        if not match:
            return destination
        candidate = cls._clean_place(match.group(1))
        normalized = candidate.casefold().replace("’", "'")
        if (
            InternetToolManager._is_relative_weather_location(candidate)
            or normalized in _DESTINATION_PRONOUNS
            or any(
                token in normalized
                for token in ("arrivee", "arrivée", "destination", "sur place", "la bas", "là-bas")
            )
        ):
            return destination
        return candidate or destination

    def _plan_route_weather(self, text: str) -> AgentPlan | None:
        if not _WEATHER_HINT_RE.search(str(text or "")):
            return None
        route_pair = self._extract_route_pair(text)
        if route_pair is None:
            return None
        origin, destination = route_pair
        weather_location = self._weather_place_for_route(text, destination)
        maps_spec = self.registry.by_name("maps.directions")
        weather_spec = self.registry.by_name("weather")
        if maps_spec is None or weather_spec is None:
            return None
        tomorrow = bool(re.search(r"\bdemain\b", str(text or ""), re.I))
        steps = (
            AgentStep(
                id="step1", tool=maps_spec.name, action=maps_spec.action,
                args={"origin": origin, "destination": destination, "travelmode": "driving"},
                category=maps_spec.category, description=maps_spec.description,
            ),
            AgentStep(
                id="step2", tool=weather_spec.name, action=weather_spec.action,
                args={"location": weather_location, "tomorrow": tomorrow},
                category=weather_spec.category, description=weather_spec.description,
            ),
        )
        return AgentPlan(
            objective=str(text or "").strip(), steps=steps,
            source="deterministic-route-weather", stop_on_error=False,
        )

    def _to_agent_step(self, index: int, plan: ToolPlan) -> AgentStep | None:
        spec = self.registry.by_action(plan.action)
        if spec is None:
            return None
        return AgentStep(
            id=f"step{index}",
            tool=spec.name,
            action=plan.action,
            args=dict(plan.args or {}),
            category=plan.category or spec.category,
            description=spec.description,
        )

    def plan(self, text: str) -> AgentPlan | None:
        natural = self._plan_route_weather(text)
        if natural is not None:
            return natural

        parts = self._split(text)
        if len(parts) < 2 or len(parts) > self.max_steps:
            return None

        # Composite planning must be self-contained. Preserve/restore the
        # short-lived conversational tool context so an old pending weather
        # slot cannot silently reinterpret one clause of a new agent request.
        context = getattr(self.internet_manager, "context", None)
        saved_state = getattr(context, "state", None)
        if context is not None and hasattr(context, "clear"):
            context.clear()
        try:
            steps: list[AgentStep] = []
            for index, clause in enumerate(parts, start=1):
                clause = re.sub(r"^(?:aura)[,\s:]+", "", clause, flags=re.IGNORECASE).strip()
                tool_plan = self.internet_manager.plan(clause)
                if tool_plan is None:
                    return None
                step = self._to_agent_step(index, tool_plan)
                if step is None:
                    return None
                steps.append(step)
        finally:
            if context is not None and saved_state is not None:
                context.state = saved_state

        if len(steps) < 2:
            return None
        return AgentPlan(
            objective=str(text or "").strip(),
            steps=tuple(steps),
            source="deterministic-sequence",
            stop_on_error=False,
        )
