from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from aura_native.providers.connection import ConnectionHttpClient


PROVIDER_IDS = ("openai", "anthropic", "gemini", "ollama", "custom_openai")


@dataclass(frozen=True)
class ProviderModelDescriptor:
    provider_id: str
    model_id: str
    display_name: str
    description: str = ""
    capabilities: tuple[str, ...] = ()
    is_recommended: bool = False
    is_available: bool = True
    is_local: bool = False
    metadata_safe: bool = True

    def as_dict(self):
        return {"provider_id": self.provider_id, "model_id": self.model_id,
                "display_name": self.display_name, "description": self.description,
                "capabilities": list(self.capabilities), "is_recommended": self.is_recommended,
                "is_available": self.is_available, "is_local": self.is_local,
                "metadata_safe": self.metadata_safe}


class ModelCatalogError(RuntimeError):
    def __init__(self, code, message="model catalog unavailable"):
        self.code = code
        super().__init__(message)


class FakeModelCatalogProvider:
    catalogs = {
        "ollama": ("qwen3:8b", "llama-test:latest"),
        "gemini": ("gemini-test-fast", "gemini-test-pro", "gemini-test-lite"),
        "openai": ("openai-test-model",), "anthropic": ("claude-test-model",),
        "custom_openai": ("custom-test-model",),
    }

    def __init__(self, catalogs=None, *, error=None, delay=0.0):
        self.catalogs = dict(catalogs or self.catalogs)
        self.error = error
        self.delay = float(delay)
        self.calls = []

    def list_models(self, provider_id):
        if self.delay:
            import time; time.sleep(self.delay)
        self.calls.append(provider_id)
        if self.error: raise ModelCatalogError(self.error)
        return tuple(ProviderModelDescriptor(provider_id, model, model,
            capabilities=("streaming",), is_recommended=index == 0,
            is_local=provider_id == "ollama") for index, model in enumerate(self.catalogs.get(provider_id, ())))


class OllamaModelCatalogProvider:
    def __init__(self, base_url, http=None, timeout=8.0): self.base_url=str(base_url or "").rstrip("/"); self.http=http or ConnectionHttpClient(); self.timeout=timeout
    def list_models(self, provider_id="ollama"):
        if not self.base_url: raise ModelCatalogError("invalid_configuration")
        try: response=self.http.get_json(self.base_url+"/api/tags", timeout=self.timeout)
        except TimeoutError as exc: raise ModelCatalogError("timeout") from exc
        except Exception as exc: raise ModelCatalogError("network_error") from exc
        if response.status != 200: raise ModelCatalogError("provider_unavailable" if response.status >= 500 else "invalid_response")
        rows=response.payload.get("models") if isinstance(response.payload, dict) else None
        if not isinstance(rows, list): raise ModelCatalogError("invalid_response")
        result=[]
        for row in rows:
            if isinstance(row, dict) and row.get("name"):
                safe={k:row[k] for k in ("size","modified_at","family","parameter_size","quantization_level") if k in row}
                result.append(ProviderModelDescriptor("ollama",str(row["name"]),str(row["name"]),capabilities=("streaming",),is_local=True,metadata_safe=True))
        return tuple(result)


class GeminiModelCatalogProvider:
    def __init__(self, credential_store, http=None, timeout=8.0): self.store=credential_store; self.http=http or ConnectionHttpClient(); self.timeout=timeout
    def list_models(self, provider_id="gemini"):
        secret=self.store.get_secret("gemini") if self.store else None
        if not secret: raise ModelCatalogError("not_configured")
        try: response=self.http.get_json("https://generativelanguage.googleapis.com/v1beta/models", {"x-goog-api-key":secret}, self.timeout)
        except TimeoutError as exc: raise ModelCatalogError("timeout") from exc
        except Exception as exc: raise ModelCatalogError("network_error") from exc
        if response.status in (401,403,429): raise ModelCatalogError({401:"authentication_failed",403:"permission_denied",429:"rate_limited"}[response.status])
        if response.status >= 500: raise ModelCatalogError("provider_unavailable")
        if response.status != 200 or not isinstance(response.payload, dict): raise ModelCatalogError("invalid_response")
        result=[]
        for row in response.payload.get("models", []):
            if not isinstance(row, dict): continue
            methods=tuple(row.get("supportedGenerationMethods") or ())
            if "generateContent" not in methods: continue
            raw=str(row.get("name") or ""); model_id=raw.removeprefix("models/")
            if model_id: result.append(ProviderModelDescriptor("gemini",model_id,str(row.get("displayName") or model_id),str(row.get("description") or ""),tuple(m for m in methods if isinstance(m,str)),is_local=False,metadata_safe=True))
        return tuple(result)


class ModelCatalogService:
    """Explicit, in-memory catalog refresh boundary. It never selects a model."""
    def __init__(self, providers):
        self.providers = dict(providers)
        self._catalogs = {}
        self._last_refresh = {}
        self._states = {pid: "idle" for pid in self.providers}
        self._lock = Lock()
        self._generations = {pid: 0 for pid in self.providers}

    def refresh_models(self, provider_id):
        if provider_id not in self.providers: raise ModelCatalogError("not_configured")
        with self._lock:
            if self._states.get(provider_id) == "loading": raise ModelCatalogError("refresh_in_progress")
            self._states[provider_id] = "loading"; self._generations[provider_id] += 1
            generation = self._generations[provider_id]
        try:
            values = tuple(self.providers[provider_id].list_models(provider_id))
            with self._lock:
                if generation == self._generations[provider_id]:
                    self._catalogs[provider_id] = values
                    self._last_refresh[provider_id] = datetime.now(timezone.utc).isoformat()
                    self._states[provider_id] = "success"
            return values
        except ModelCatalogError:
            with self._lock: self._states[provider_id] = "error"
            raise
        except Exception as exc:
            with self._lock: self._states[provider_id] = "error"
            raise ModelCatalogError("unknown_error") from exc

    def get_models(self, provider_id): return tuple(self._catalogs.get(provider_id, ()))
    def get_last_refresh(self, provider_id): return self._last_refresh.get(provider_id)
    def get_state(self, provider_id): return self._states.get(provider_id, "idle")
