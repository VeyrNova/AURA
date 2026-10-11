"""Legacy-compatible native provider settings.

The AURA_PROVIDER, AURA_MODEL and AURA_OLLAMA_HOST variables are development
overrides only. Runtime provider selection belongs to ProviderSettingsService;
historical environment names and installations are ignored.
"""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AgentProviderSettings:
    provider_name:str=""
    model:str=""
    ollama_host:str="http://127.0.0.1:11434"
    timeout_seconds:float=30.0
    @classmethod
    def from_environment(cls):
        name=os.environ.get("AURA_PROVIDER","").strip().lower()
        if name not in ("","ollama"): raise ValueError("AURA_PROVIDER must be ollama or absent")
        timeout=float(os.environ.get("AURA_PROVIDER_TIMEOUT_SECONDS","30"))
        return cls(name,os.environ.get("AURA_MODEL","").strip(),os.environ.get("AURA_OLLAMA_HOST","http://127.0.0.1:11434").strip().rstrip("/"),max(1.0,min(timeout,180.0)))
