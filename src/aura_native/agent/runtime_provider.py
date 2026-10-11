"""Per-request routing from persisted provider settings to native adapters."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Callable

from aura_native.agent.provider import GeminiRuntimeProvider, OllamaProvider
from aura_native.config.agent_provider import AgentProviderSettings

PROVIDER_IDS = ("openai", "anthropic", "gemini", "ollama", "custom_openai")


class ProviderRoutingError(Exception):
    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)


@dataclass(frozen=True)
class ProviderSelection:
    provider_id: str
    model: str
    host: str


@dataclass(frozen=True)
class ResolvedProviderRuntime:
    provider_id: str
    model: str
    adapter: object = field(repr=False, compare=False)
    is_local: bool
    supports_streaming: bool
    supports_cancel: bool
    supports_tools: bool


class RuntimeProviderRouter:
    """Resolve one immutable provider adapter snapshot for each agent request."""

    def __init__(self, settings_service, credential_store, *, environment=None,
                 adapters: dict[str, Callable[[ProviderSelection], object]] | None = None,
                 ollama_timeout_seconds: float = 30.0):
        self.settings_service = settings_service
        self.credential_store = credential_store
        self.environment = os.environ if environment is None else environment
        self.ollama_timeout_seconds = max(1.0, min(float(ollama_timeout_seconds), 180.0))
        self.adapters = dict(adapters or {})
        self.adapters.setdefault("ollama", self._ollama_adapter)
        self.adapters.setdefault("gemini", self._gemini_adapter)

    def selection(self) -> ProviderSelection:
        override_provider = str(self.environment.get("AURA_PROVIDER", "")).strip().lower()
        provider_id = override_provider or str(self.settings_service.get_active_provider() or "").strip().lower()
        if provider_id and provider_id not in PROVIDER_IDS:
            return ProviderSelection(provider_id, "", "")
        config = self.settings_service.get_provider_config(provider_id) if provider_id else None
        override_model = str(self.environment.get("AURA_MODEL", "")).strip()
        model = override_model or (str(config.selected_model or "").strip() if config else "")
        host = str(self.environment.get("AURA_OLLAMA_HOST", "")).strip()
        if not host:
            host = str(getattr(config, "base_url", "") or "http://127.0.0.1:11434").strip()
        return ProviderSelection(provider_id, model, host.rstrip("/"))

    def resolve_active_provider(self) -> ResolvedProviderRuntime:
        selection = self.selection()
        provider_id = selection.provider_id
        if not provider_id:
            raise ProviderRoutingError("provider_not_selected", "Aucun fournisseur d’IA n’est sélectionné.")
        if provider_id not in PROVIDER_IDS:
            raise ProviderRoutingError("invalid_configuration", "Le fournisseur sélectionné n’est pas reconnu.")
        config = self.settings_service.get_provider_config(provider_id)
        if config is None:
            raise ProviderRoutingError("invalid_configuration", "Le fournisseur sélectionné n’est pas configuré.")
        if provider_id in ("openai", "anthropic", "gemini", "custom_openai"):
            try:
                configured = bool(self.credential_store and self.credential_store.has_secret(provider_id))
            except Exception:
                configured = False
            if not configured:
                raise ProviderRoutingError("provider_not_configured", "Configurez ce fournisseur dans IA & Intégrations.")
        if not selection.model:
            message = "Choisissez un modèle Gemini dans IA & Intégrations." if provider_id == "gemini" else "Choisissez un modèle pour ce fournisseur."
            raise ProviderRoutingError("model_not_selected", message)
        if provider_id == "ollama" and not re.match(r"^https?://[^/]+$",selection.host):
            raise ProviderRoutingError("invalid_configuration", "Vérifiez l’adresse locale d’Ollama dans IA & Intégrations.")
        if provider_id not in self.adapters:
            raise ProviderRoutingError("provider_unavailable", "Ce fournisseur n’est pas disponible dans cette version.")
        adapter = self.adapters[provider_id](selection)
        return ResolvedProviderRuntime(
            provider_id=provider_id,
            model=selection.model,
            adapter=adapter,
            is_local=provider_id == "ollama",
            supports_streaming=callable(getattr(adapter, "generate_stream", None)),
            supports_cancel=True,
            supports_tools=bool(getattr(adapter, "supports_tools", False)),
        )

    def _ollama_adapter(self, selection):
        settings = AgentProviderSettings(
            provider_name="ollama",
            model=selection.model,
            ollama_host=selection.host,
            timeout_seconds=self.ollama_timeout_seconds,
        )
        return OllamaProvider(settings)

    def _gemini_adapter(self, selection):
        # The credential remains inside this request-scoped Python adapter.
        secret = self.credential_store.get_secret("gemini")
        if not secret:
            raise ProviderRoutingError("provider_not_configured", "Configurez ce fournisseur dans IA & Intégrations.")
        return GeminiRuntimeProvider(model=selection.model, api_key=secret)

