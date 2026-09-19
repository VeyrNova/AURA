from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    action: str
    category: str
    description: str
    required_args: tuple[str, ...] = ()
    read_only: bool = True
    background_safe: bool = True


class AgentToolRegistry:
    """Explicit allow-list of tools visible to the Agent Kernel.

    Registering a tool here does *not* grant permission. Every planned action is
    still authorized by SecurityPolicyEngine on the UI/main thread before an
    executor worker may run it.
    """

    def __init__(self):
        self._by_action: dict[str, AgentToolSpec] = {}
        self._by_name: dict[str, AgentToolSpec] = {}

    def register(self, spec: AgentToolSpec) -> None:
        action = str(spec.action or "").strip().upper()
        name = str(spec.name or "").strip()
        if not action or not name:
            raise ValueError("Agent tool name/action must be non-empty")
        if action in self._by_action or name in self._by_name:
            raise ValueError(f"Agent tool already registered: {name}/{action}")
        self._by_action[action] = spec
        self._by_name[name] = spec

    def by_action(self, action: str) -> AgentToolSpec | None:
        return self._by_action.get(str(action or "").strip().upper())

    def by_name(self, name: str) -> AgentToolSpec | None:
        return self._by_name.get(str(name or "").strip())

    def specs(self) -> tuple[AgentToolSpec, ...]:
        return tuple(self._by_name.values())

    @classmethod
    def default_readonly(cls) -> "AgentToolRegistry":
        registry = cls()
        for spec in (
            AgentToolSpec(
                "weather", "WEB_WEATHER", "weather",
                "Météo actuelle/prévision d'un lieu explicitement fourni.",
                ("location",),
            ),
            AgentToolSpec(
                "maps.locate", "MAPS_LOCATE", "maps",
                "Localiser un lieu fourni par l'utilisateur.",
                ("query",),
            ),
            AgentToolSpec(
                "maps.directions", "MAPS_DIRECTIONS", "maps",
                "Calculer/préparer un itinéraire vers une destination.",
                ("destination",),
            ),
            AgentToolSpec(
                "web.search", "WEB_SEARCH", "web_search",
                "Rechercher des sources sur le Web via le fournisseur configuré.",
                ("query",),
            ),
            AgentToolSpec(
                "web.fetch", "WEB_FETCH", "web_fetch",
                "Lire une page HTTP/HTTPS explicitement autorisée.",
                ("url",),
            ),
            AgentToolSpec(
                "knowledge.reference.local", "KNOWLEDGE_REFERENCE_LOCAL", "knowledge_reference",
                "Consulter la référence locale auditée.",
                ("subject",),
            ),
            AgentToolSpec(
                "knowledge.reference.web", "WEB_KNOWLEDGE_REFERENCE", "knowledge_reference",
                "Consulter la référence Web déterministe autorisée.",
                ("subject",),
            ),
        ):
            registry.register(spec)
        return registry
