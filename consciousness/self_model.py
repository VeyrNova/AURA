"""Truthful capability SelfModel for AURA v0.7.2.1 consolidation."""
from dataclasses import asdict, dataclass, replace

from config.settings import settings


@dataclass(frozen=True)
class CapabilityState:
    notes: bool = True
    tasks: bool = True
    reminders: bool = True
    security_core: bool = True
    consciousness_core: bool = True
    metacognition: bool = True
    adaptive_learning: bool = True
    cloud_intelligence: bool = False
    groq: bool = False
    gemini: bool = False
    local_llm: bool = False
    voice: bool = False
    voice_input: bool = False
    voice_output: bool = False
    internet: bool = False
    agent_kernel: bool = False
    persistent_memory: bool = True
    continuity: bool = True
    relationship_model: bool = True
    private_memory_mode: bool = True
    calendar: bool = False
    system_control: bool = False
    email: bool = False


class SelfModel:
    """Functional model of what AURA really can and cannot do."""

    def __init__(self, capabilities: CapabilityState | None = None):
        self._capabilities = capabilities or CapabilityState()

    def capabilities(self) -> dict[str, bool]:
        return asdict(self._capabilities)

    def has_capability(self, name: str) -> bool:
        return bool(self.capabilities().get(name, False))

    def with_capability(self, name: str, enabled: bool) -> "SelfModel":
        if name not in self.capabilities():
            raise KeyError(f"Capacite inconnue : {name}")
        return SelfModel(replace(self._capabilities, **{name: bool(enabled)}))

    def enabled_capabilities(self) -> list[str]:
        return [name for name, enabled in self.capabilities().items() if enabled]

    def disabled_capabilities(self) -> list[str]:
        return [name for name, enabled in self.capabilities().items() if not enabled]

    def render_for_prompt(self) -> str:
        enabled = ", ".join(self.enabled_capabilities()) or "aucune"
        disabled = ", ".join(self.disabled_capabilities()) or "aucune"
        local_line = (
            f"- IA locale optionnelle : active ({settings.LOCAL_LLM_PROVIDER} / {settings.LLM_TEXT_MODEL})\n"
            if settings.LOCAL_LLM_ENABLED
            else "- IA locale optionnelle : désactivée ; aucune dépendance Ollama requise au démarrage\n"
        )
        return (
            "SELF MODEL / CAPACITES REELLES\n"
            f"- Version application : {settings.APP_VERSION} (build {settings.APP_BUILD})\n"
            f"- Runtime : {settings.AURA_RUNTIME_MODE} · Cloud Intelligence / Local Control\n"
            f"- Groq configuré : {'oui' if bool(settings.GROQ_ENABLED and settings.GROQ_API_KEY) else 'non'}\n"
            f"- Gemini configuré : {'oui' if bool(settings.GEMINI_ENABLED and settings.GEMINI_API_KEY) else 'non'}\n"
            + local_line
            + f"- Capacites actives : {enabled}\n"
            + f"- Capacites indisponibles : {disabled}\n"
            + "- Ne prétends jamais avoir effectué une action via une capacité indisponible.\n"
            + "- Si une capacité manque, dis-le simplement et propose une alternative disponible."
        )
