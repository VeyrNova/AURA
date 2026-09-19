from __future__ import annotations

"""AURA v3 read-only hardware capability adapter.

This module intentionally DOES NOT probe CPU/GPU/RAM by itself.
It normalizes information already owned by AURA's existing runtime services:
ResourceGuardian, SystemService, LLMManager, hardware_runtime and adaptive_profile.

No model loading, unloading, TTS residency change, provider call, or source mutation
is performed by the adapter itself.
"""

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import importlib
from typing import Any, Mapping

SCHEMA = "aura.hardware_capability_service.v3"
VERSION = "3.0.0"


def _plain(value: Any) -> Any:
    """Convert dataclasses/mappings/simple containers to JSON-friendly values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return {str(k): _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_plain(v) for v in value]
    if hasattr(value, "_asdict") and callable(value._asdict):
        return _plain(value._asdict())
    if hasattr(value, "__dict__"):
        return {
            str(k): _plain(v)
            for k, v in vars(value).items()
            if not str(k).startswith("_")
        }
    return str(value)


class HardwareCapabilityServiceV3:
    """Read-only facade over AURA's already-certified capability owners."""

    def __init__(
        self,
        *,
        aura_core: Any = None,
        resource_guardian: Any = None,
        system_service: Any = None,
        llm_manager: Any = None,
        hardware_runtime: Any = None,
    ) -> None:
        self.aura_core = aura_core
        self.resource_guardian = resource_guardian or getattr(aura_core, "resource_guardian", None)
        self.system_service = system_service
        self.llm_manager = (
            llm_manager
            or getattr(aura_core, "llm_manager", None)
            or getattr(self.resource_guardian, "llm_manager", None)
        )
        self.hardware_runtime = hardware_runtime or self._discover_hardware_runtime()

    @staticmethod
    def _discover_hardware_runtime() -> Any:
        """Reuse an existing hardware_runtime singleton if the module exposes one.

        The adapter never creates a second HardwareRuntimeDiagnostics authority.
        """
        try:
            mod = importlib.import_module("runtime.hardware_runtime")
        except Exception:
            return None

        preferred = (
            "hardware_runtime",
            "hardware_runtime_diagnostics",
            "runtime_diagnostics",
            "HARDWARE_RUNTIME",
        )
        for name in preferred:
            obj = getattr(mod, name, None)
            if obj is not None and callable(getattr(obj, "snapshot", None)):
                return obj

        for name, obj in vars(mod).items():
            if name.startswith("_") or isinstance(obj, type):
                continue
            if callable(getattr(obj, "snapshot", None)) and callable(getattr(obj, "diagnostics", None)):
                return obj
        return None

    @staticmethod
    def _unavailable(source: str, reason: str) -> dict:
        return {"available": False, "source": source, "reason": str(reason or "unavailable"), "data": {}}

    def resource_snapshot(
        self,
        *,
        include_ollama: bool = False,
        force_gpu: bool = False,
        ollama_model: str | None = None,
    ) -> dict:
        guardian = self.resource_guardian
        fn = getattr(guardian, "sample", None)
        if not callable(fn):
            return self._unavailable("ResourceGuardian.sample", "resource_guardian unavailable")
        try:
            snap = fn(
                include_ollama=bool(include_ollama),
                force_gpu=bool(force_gpu),
                ollama_model=ollama_model,
            )
            return {"available": True, "source": "ResourceGuardian.sample", "data": _plain(snap)}
        except TypeError:
            # Compatibility with an older certified sample() signature.
            try:
                snap = fn(force_gpu=bool(force_gpu))
                return {"available": True, "source": "ResourceGuardian.sample", "data": _plain(snap)}
            except Exception as exc:
                return self._unavailable("ResourceGuardian.sample", repr(exc))
        except Exception as exc:
            return self._unavailable("ResourceGuardian.sample", repr(exc))

    def system_snapshot(self) -> dict:
        service = self.system_service
        fn = getattr(service, "snapshot", None)
        if not callable(fn):
            return self._unavailable("SystemService.snapshot", "system_service not bound")
        try:
            return {"available": True, "source": "SystemService.snapshot", "data": _plain(fn())}
        except Exception as exc:
            return self._unavailable("SystemService.snapshot", repr(exc))

    def gpu_runtime_snapshot(self) -> dict:
        runtime = self.hardware_runtime
        if runtime is None:
            return self._unavailable("hardware_runtime", "existing runtime singleton not discovered")

        diag = getattr(runtime, "diagnostics", None)
        snap = getattr(runtime, "snapshot", None)
        try:
            if callable(diag):
                return {"available": True, "source": "hardware_runtime.diagnostics", "data": _plain(diag())}
            if callable(snap):
                return {"available": True, "source": "hardware_runtime.snapshot", "data": _plain(snap())}
        except Exception as exc:
            return self._unavailable("hardware_runtime", repr(exc))
        return self._unavailable("hardware_runtime", "no diagnostics/snapshot API")

    def adaptive_capacity_snapshot(self) -> dict:
        """Call AURA's existing adaptive_profile implementation; no duplicated probes."""
        try:
            mod = importlib.import_module("adaptive_profile")
            capacity_fn = getattr(mod, "hardware_capacity_snapshot", None)
            profile_fn = getattr(mod, "select_profile_id", None)
            if not callable(capacity_fn):
                return self._unavailable("adaptive_profile.hardware_capacity_snapshot", "API unavailable")
            capacity = _plain(capacity_fn())
            profile_id = profile_fn(capacity) if callable(profile_fn) else None
            return {
                "available": True,
                "source": "adaptive_profile",
                "data": capacity,
                "profile_id": str(profile_id or ""),
            }
        except Exception as exc:
            return self._unavailable("adaptive_profile", repr(exc))

    def route_profile(
        self,
        *,
        voice_output: bool,
        user_text: str = "",
        force_local: bool = False,
        preferred_provider: str | None = None,
    ) -> dict:
        guardian = self.resource_guardian
        fn = getattr(guardian, "llm_request_profile", None)
        if not callable(fn):
            return self._unavailable("ResourceGuardian.llm_request_profile", "API unavailable")
        try:
            profile = fn(
                voice_output=bool(voice_output),
                user_text=str(user_text or ""),
                force_local=bool(force_local),
                preferred_provider=preferred_provider,
            )
            return {"available": True, "source": "ResourceGuardian.llm_request_profile", "data": _plain(profile)}
        except Exception as exc:
            return self._unavailable("ResourceGuardian.llm_request_profile", repr(exc))

    def local_model_catalog(self, *, force: bool = False) -> dict:
        manager = self.llm_manager
        fn = getattr(manager, "local_model_catalog", None)
        if not callable(fn):
            return self._unavailable("LLMManager.local_model_catalog", "llm_manager unavailable")
        try:
            models = fn(force=bool(force))
            return {
                "available": True,
                "source": "LLMManager.local_model_catalog",
                "data": _plain(models),
            }
        except Exception as exc:
            return self._unavailable("LLMManager.local_model_catalog", repr(exc))

    def provider_availability(self) -> dict:
        manager = self.llm_manager
        fn = getattr(manager, "remote_available", None)
        if not callable(fn):
            return self._unavailable("LLMManager.remote_available", "llm_manager unavailable")
        data = {}
        for provider in ("groq", "gemini"):
            try:
                data[provider] = bool(fn(provider))
            except Exception:
                data[provider] = False
        try:
            data["any_remote"] = bool(fn(None))
        except Exception:
            data["any_remote"] = any(data.values())
        return {"available": True, "source": "LLMManager.remote_available", "data": data}

    def voice_residency_snapshot(self, *, route_profile: dict | None = None) -> dict:
        guardian = self.resource_guardian
        xtts_fn = getattr(guardian, "xtts_local_first_hot", None)
        realtime_fn = getattr(guardian, "realtime_dialogue_ready", None)
        if not callable(xtts_fn) and not callable(realtime_fn):
            return self._unavailable("ResourceGuardian.voice_residency", "voice residency APIs unavailable")
        data = {}
        if callable(xtts_fn):
            try:
                data["xtts_local_first_hot"] = bool(xtts_fn())
            except Exception:
                data["xtts_local_first_hot"] = False
        if callable(realtime_fn):
            try:
                data["realtime_dialogue_ready"] = bool(realtime_fn(route_profile))
            except Exception:
                data["realtime_dialogue_ready"] = False
        return {"available": True, "source": "ResourceGuardian.voice_residency", "data": data}

    def snapshot(
        self,
        *,
        include_system: bool = True,
        include_adaptive: bool = False,
        include_route_profile: bool = False,
        include_local_models: bool = False,
        include_provider_availability: bool = False,
        include_voice_residency: bool = False,
        include_ollama_resource_state: bool = False,
        force_gpu_refresh: bool = False,
        voice_output: bool = False,
        user_text: str = "",
        force_local: bool = False,
        preferred_provider: str | None = None,
    ) -> dict:
        """Return one normalized capability document.

        Expensive or stateful existing APIs are opt-in. The default snapshot is
        deliberately conservative: ResourceGuardian sample + SystemService +
        existing hardware-runtime state.
        """
        route = None
        result = {
            "schema": SCHEMA,
            "version": VERSION,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "read_only_adapter": True,
            "owners": {
                "resource": "runtime.resource_guardian.ResourceGuardian",
                "system": "services.core_bridge.SystemService",
                "llm": "ai.llm_manager.LLMManager",
                "gpu_runtime": "runtime.hardware_runtime",
                "adaptive_profile": "adaptive_profile",
                "installed_model_policy": "installed_model_policy",
                "fabric_model_catalog": "runtime.aura_fabric_model_catalog.ModelCatalog",
                "fabric_provider_registry": "runtime.aura_fabric_provider_registry.ProviderRegistry",
            },
            "resource": self.resource_snapshot(
                include_ollama=include_ollama_resource_state,
                force_gpu=force_gpu_refresh,
            ),
            "gpu_runtime": self.gpu_runtime_snapshot(),
        }

        if include_system:
            result["system"] = self.system_snapshot()
        if include_adaptive:
            result["adaptive"] = self.adaptive_capacity_snapshot()
        if include_route_profile:
            route = self.route_profile(
                voice_output=voice_output,
                user_text=user_text,
                force_local=force_local,
                preferred_provider=preferred_provider,
            )
            result["route_profile"] = route
        if include_local_models:
            result["local_models"] = self.local_model_catalog(force=False)
        if include_provider_availability:
            result["providers"] = self.provider_availability()
        if include_voice_residency:
            route_data = None
            if isinstance(route, Mapping) and route.get("available"):
                route_data = route.get("data")
            result["voice_residency"] = self.voice_residency_snapshot(route_profile=route_data)

        return result


def build_hardware_capability_service_v3(
    *,
    aura_core: Any = None,
    resource_guardian: Any = None,
    system_service: Any = None,
    llm_manager: Any = None,
    hardware_runtime: Any = None,
) -> HardwareCapabilityServiceV3:
    """Small factory for explicit dependency binding by the future integration seam."""
    return HardwareCapabilityServiceV3(
        aura_core=aura_core,
        resource_guardian=resource_guardian,
        system_service=system_service,
        llm_manager=llm_manager,
        hardware_runtime=hardware_runtime,
    )
