from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Mapping

SCHEMA = "aura.adaptive-profile.v1"
PATCH = "P0.8.5.3.4"
PROFILE_IDS = ("efficient", "balanced", "performance")
MANAGED_ENV_KEYS = (
    "DUAL_BRAIN_VOICE_KEEP_ALIVE",
    "VOICE_BRAIN_POST_START_PREWARM",
    "LLM_VOICE_NUM_CTX",
    "LLM_VOICE_NUM_PREDICT",
    "LLM_VOICE_MAX_HISTORY_MESSAGES",
    "LLM_VOICE_MEMORY_LIMIT",
    "LLM_NUM_CTX",
    "LLM_NUM_PREDICT",
    "LLM_VISUAL_NUM_PREDICT",
    "LLM_VISUAL_FAST_NUM_PREDICT",
    "LLM_TEXT_MODEL",
    "LLM_VOICE_MODEL",
    "LOCAL_LLM_MODEL",
    "AGENT_ROUTER_MODEL",
)

PROFILE_DEFAULTS = {
    "efficient": {
        "code": "P1",
        "label": "EFFICIENT",
        "llm_num_ctx": 3072,
        "llm_num_predict": 180,
        "llm_voice_num_ctx": 1536,
        "llm_voice_num_predict": 80,
        "llm_voice_history": 3,
        "llm_voice_memory": 1,
        "llm_visual_num_predict": 480,
        "llm_visual_fast_num_predict": 320,
        "dual_brain_voice_keep_alive": "2m",
        "voice_brain_post_start_prewarm": False,
        "visual_budget": "30-45-fps",
        "browser_core_fps": 30,
        "browser_legacy_orb_fps": 24,
        "browser_official_orb_fps": 30,
        "native_opengl_fps": 36,
        "xtts_prewarm_min_available_ram_gib": 3.5,
        "shell_service_poll_ms": 50,
        "browser_heartbeat_ms": 1200,
        "browser_runtime_status_ms": 1000,
        "system_state_poll_ms": 6500,
        "vitals_poll_ms": 3500,
        "router_observatory_poll_ms": 1000,
        "model_policy": "compact-installed-only",
    },
    "balanced": {
        # P2 intentionally preserves AURA's validated 16 GiB / 6 GiB VRAM baseline.
        "code": "P2",
        "label": "BALANCED",
        "llm_num_ctx": 4096,
        "llm_num_predict": 220,
        "llm_voice_num_ctx": 2048,
        "llm_voice_num_predict": 104,
        "llm_voice_history": 4,
        "llm_voice_memory": 2,
        "llm_visual_num_predict": 640,
        "llm_visual_fast_num_predict": 420,
        "dual_brain_voice_keep_alive": "5m",
        "voice_brain_post_start_prewarm": True,
        "visual_budget": "48-60-fps",
        # P2 preserves the exact browser/native visual baselines validated before P0.8.5.3.3.
        "browser_core_fps": 48,
        "browser_legacy_orb_fps": 36,
        "browser_official_orb_fps": 40,
        "native_opengl_fps": 60,
        # P2: allow a background XTTS attempt around 3 GiB free RAM.
        # The existing post-load guard still releases XTTS if RAM becomes unsafe.
        "xtts_prewarm_min_available_ram_gib": 2.75,
        # P2 workload timings preserve the exact validated pre-P0.8.5.3.4 runtime.
        "shell_service_poll_ms": 30,
        "browser_heartbeat_ms": 900,
        "browser_runtime_status_ms": 700,
        "system_state_poll_ms": 4000,
        "vitals_poll_ms": 2200,
        "router_observatory_poll_ms": 650,
        "model_policy": "balanced-installed-only",
    },
    "performance": {
        "code": "P3",
        "label": "PERFORMANCE",
        "llm_num_ctx": 6144,
        "llm_num_predict": 320,
        "llm_voice_num_ctx": 3072,
        "llm_voice_num_predict": 128,
        "llm_voice_history": 6,
        "llm_voice_memory": 3,
        "llm_visual_num_predict": 800,
        "llm_visual_fast_num_predict": 520,
        "dual_brain_voice_keep_alive": "10m",
        "voice_brain_post_start_prewarm": True,
        "visual_budget": "60-72-fps",
        "browser_core_fps": 60,
        "browser_legacy_orb_fps": 48,
        "browser_official_orb_fps": 60,
        "native_opengl_fps": 72,
        "xtts_prewarm_min_available_ram_gib": 3.5,
        "shell_service_poll_ms": 20,
        "browser_heartbeat_ms": 700,
        "browser_runtime_status_ms": 500,
        "system_state_poll_ms": 2500,
        "vitals_poll_ms": 1500,
        "router_observatory_poll_ms": 450,
        "model_policy": "medium-installed-only",
    },
}


def _truthy(value, default=True) -> bool:
    if value is None:
        return bool(default)
    return str(value).strip().casefold() in {"1", "true", "yes", "on", "auto"}


def _ram_total_gib() -> float:
    try:
        import psutil  # type: ignore
        return round(float(psutil.virtual_memory().total) / (1024 ** 3), 2)
    except Exception:
        pass
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        s = MEMORYSTATUSEX()
        s.dwLength = ctypes.sizeof(s)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
                return round(float(s.ullTotalPhys) / (1024 ** 3), 2)
        except Exception:
            pass
    try:
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        page = int(os.sysconf("SC_PAGE_SIZE"))
        return round((pages * page) / (1024 ** 3), 2)
    except Exception:
        return 0.0


def _find_nvidia_smi() -> str | None:
    explicit = str(os.getenv("NVIDIA_SMI_PATH") or "").strip().strip('"')
    if explicit and Path(explicit).is_file():
        return explicit
    for name in ("nvidia-smi.exe", "nvidia-smi"):
        p = shutil.which(name)
        if p:
            return p
    if os.name == "nt":
        candidates = []
        system_root = os.getenv("SystemRoot") or os.getenv("WINDIR")
        if system_root:
            candidates.append(Path(system_root) / "System32" / "nvidia-smi.exe")
        for env_name in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
            base = os.getenv(env_name)
            if base:
                candidates.append(Path(base) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe")
        for p in candidates:
            if p.is_file():
                return str(p)
    return None


def _dedicated_vram_gib() -> float:
    exe = _find_nvidia_smi()
    if not exe:
        return 0.0
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(
            [exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2.5, check=False, creationflags=flags,
        )
        if r.returncode != 0:
            return 0.0
        values = []
        for line in r.stdout.splitlines():
            try:
                values.append(float(line.strip()) / 1024.0)
            except Exception:
                pass
        return round(max(values) if values else 0.0, 2)
    except Exception:
        return 0.0


def hardware_capacity_snapshot() -> dict:
    return {
        "logical_cores": int(os.cpu_count() or 1),
        "ram_gib": float(_ram_total_gib()),
        "vram_gib": float(_dedicated_vram_gib()),
    }


def select_profile_id(snapshot: Mapping[str, object]) -> str:
    cores = int(snapshot.get("logical_cores") or 0)
    ram = float(snapshot.get("ram_gib") or 0.0)
    vram = float(snapshot.get("vram_gib") or 0.0)
    if ram >= 24 and cores >= 12 and vram >= 8:
        return "performance"
    if ram >= 12 and cores >= 6 and vram >= 4:
        return "balanced"
    return "efficient"


class AdaptiveProfile:
    def __init__(self, profile_id: str, *, enabled: bool, source: str, snapshot: dict, override_keys=()):
        profile_id = profile_id if profile_id in PROFILE_DEFAULTS else "balanced"
        self.id = profile_id
        self.enabled = bool(enabled)
        self.source = str(source)
        self.snapshot = dict(snapshot)
        self.override_keys = tuple(sorted(set(str(x) for x in override_keys)))
        for key, value in PROFILE_DEFAULTS[profile_id].items():
            setattr(self, key, value)

    @property
    def applies_runtime_defaults(self) -> bool:
        return bool(self.enabled)

    @property
    def applies_model_switch(self) -> bool:
        # P0.8.5.3.2 may select among models that are already installed,
        # but only when the local LLM runtime is explicitly enabled.
        return bool(self.enabled)

    @property
    def applies_ui_switch(self) -> bool:
        # Layout/branding switching remains forbidden: NORMAL/COMPACT and shell geometry
        # are not selected automatically by P0.8.5.3.3.
        return False

    @property
    def applies_visual_budget(self) -> bool:
        # Only technical frame budgets are adaptive.
        return bool(self.enabled)

    @property
    def applies_workload_budget(self) -> bool:
        # Background/service polling cadence only; feature semantics stay unchanged.
        return bool(self.enabled)

    def as_dict(self) -> dict:
        defaults = {k: getattr(self, k) for k in PROFILE_DEFAULTS[self.id]}
        return {
            "schema": SCHEMA,
            "patch": PATCH,
            "enabled": self.enabled,
            "id": self.id,
            "code": self.code,
            "label": self.label,
            "source": self.source,
            "hardware": dict(self.snapshot),
            "runtime_defaults": defaults,
            "environment_overrides": list(self.override_keys),
            "applies_runtime_defaults": self.applies_runtime_defaults,
            "applies_model_switch": self.applies_model_switch,
            "applies_ui_switch": self.applies_ui_switch,
            "applies_visual_budget": self.applies_visual_budget,
            "applies_workload_budget": self.applies_workload_budget,
            "no_model_download": True,
            "installed_model_policy": "installed-only-no-pull",
        }


def resolve_adaptive_profile(
    *,
    core_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    snapshot: Mapping[str, object] | None = None,
) -> AdaptiveProfile:
    del core_root  # reserved for future cached hardware-signature persistence
    e = dict(os.environ if env is None else env)
    enabled = _truthy(e.get("AURA_ADAPTIVE_ENABLED"), True)
    forced = str(e.get("AURA_ADAPTIVE_PROFILE") or "auto").strip().casefold()
    snap = dict(snapshot or hardware_capacity_snapshot())

    if not enabled:
        # Compatibility mode is P2 because P2 equals the validated pre-adaptive baseline.
        profile_id = "balanced"
        source = "disabled-compatibility-p2"
    elif forced in PROFILE_IDS:
        profile_id = forced
        source = "explicit-profile-override"
    else:
        profile_id = select_profile_id(snap)
        source = "automatic-static-capacity-v1"

    overrides = [key for key in MANAGED_ENV_KEYS if str(e.get(key) or "").strip()]
    return AdaptiveProfile(
        profile_id,
        enabled=enabled,
        source=source,
        snapshot=snap,
        override_keys=overrides,
    )


def self_test() -> bool:
    cases = [
        ({"logical_cores": 4, "ram_gib": 8, "vram_gib": 0}, "efficient"),
        ({"logical_cores": 8, "ram_gib": 16, "vram_gib": 4}, "balanced"),
        ({"logical_cores": 20, "ram_gib": 16, "vram_gib": 6}, "balanced"),
        ({"logical_cores": 16, "ram_gib": 32, "vram_gib": 12}, "performance"),
    ]
    if not all(select_profile_id(s) == expected for s, expected in cases):
        return False
    p2 = resolve_adaptive_profile(
        env={"AURA_ADAPTIVE_PROFILE": "balanced"},
        snapshot={"logical_cores": 8, "ram_gib": 16, "vram_gib": 4},
    )
    return (
        p2.code == "P2"
        and p2.llm_num_ctx == 4096
        and p2.llm_voice_num_ctx == 2048
        and p2.applies_model_switch is True
        and p2.applies_ui_switch is False
        and p2.applies_visual_budget is True
        and p2.browser_core_fps == 48
        and p2.browser_legacy_orb_fps == 36
        and p2.browser_official_orb_fps == 40
        and p2.native_opengl_fps == 60
        and abs(p2.xtts_prewarm_min_available_ram_gib - 2.75) < 0.001
        and p2.shell_service_poll_ms == 30
        and p2.browser_heartbeat_ms == 900
        and p2.browser_runtime_status_ms == 700
        and p2.system_state_poll_ms == 4000
        and p2.vitals_poll_ms == 2200
        and p2.router_observatory_poll_ms == 650
    )


if __name__ == "__main__":
    print(json.dumps({"self_test": self_test(), "profile": resolve_adaptive_profile().as_dict()}, indent=2))
