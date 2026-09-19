from __future__ import annotations

import re
import unicodedata

from agent.tool_registry import AgentToolRegistry, AgentToolSpec


_SEQUENCE_HINT_RE = re.compile(
    r"(?:;|\b(?:puis|ensuite|et\s+puis|et\s+ensuite|apres|après|avant|"
    r"en\s+meme\s+temps|en\s+même\s+temps|a\s+la\s+fois|à\s+la\s+fois)\b)",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def _normalize(text: str) -> str:
    raw = unicodedata.normalize("NFKD", str(text or ""))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", raw).strip()


class AgentToolSelector:
    """Select a tiny relevant subset of the Agent registry before LLM routing.

    This is intentionally deterministic. The LLM never decides which tools it
    is allowed to see; it can only choose among this pre-filtered allow-list.
    """

    def __init__(self, registry: AgentToolRegistry, *, max_tools: int = 5):
        self.registry = registry
        self.max_tools = max(2, int(max_tools))

    @staticmethod
    def _domains(text: str) -> set[str]:
        n = _normalize(text)
        domains: set[str] = set()
        if any(token in n for token in ("meteo", "weather", "temperature", "pleuv", "vent", "humidite", "prevision")):
            domains.add("weather")
        if any(token in n for token in ("itineraire", "trajet", "route", "distance", "duree", "conduire", "driving", "depuis", "vers ")):
            domains.add("directions")
        if any(token in n for token in ("carte", "localise", "localiser", "ou se trouve", "où se trouve", "montre-moi ", "affiche-moi ")):
            domains.add("locate")
        if _URL_RE.search(text or ""):
            domains.add("fetch")
        if any(token in n for token in ("cherche", "recherche", "recherches", "faire une recherche", "faire des recherches", "trouve", "sources", "actualite", "news", "sur le web", "internet")):
            domains.add("search")
        if any(token in n for token in ("qu'est-ce", "qu est ce", "definition", "définition", "explique", "pourquoi", "qui est", "c'est quoi", "c est quoi")):
            domains.add("knowledge")
        return domains

    def should_try_structured(self, text: str) -> bool:
        domains = self._domains(text)
        high_level = {
            "weather" if "weather" in domains else "",
            "maps" if ({"directions", "locate"} & domains) else "",
            "web" if ({"search", "fetch"} & domains) else "",
            "knowledge" if "knowledge" in domains else "",
        }
        high_level.discard("")
        # The LLM router is optional and must never be paid for a request where
        # deterministic selection sees only one high-level capability. Natural
        # route+weather phrasing is handled by DeterministicAgentPlanner first.
        if len(high_level) >= 2:
            return True
        return False

    def select(self, text: str) -> tuple[AgentToolSpec, ...]:
        domains = self._domains(text)
        names: list[str] = []
        if "directions" in domains:
            names.append("maps.directions")
        if "locate" in domains:
            names.append("maps.locate")
        if "weather" in domains:
            names.append("weather")
        if "fetch" in domains:
            names.append("web.fetch")
        if "search" in domains:
            names.append("web.search")
        if "knowledge" in domains:
            names.extend(("knowledge.reference.local", "knowledge.reference.web"))

        selected: list[AgentToolSpec] = []
        for name in names:
            spec = self.registry.by_name(name)
            if spec is not None and spec not in selected:
                selected.append(spec)
            if len(selected) >= self.max_tools:
                break
        return tuple(selected)
