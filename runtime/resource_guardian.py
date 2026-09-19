"""AURA v0.7.0.15.4 Resource Guardian + hysteretic Dual Brain residency.

v0.6.4 keeps the v0.6.2 fail-safe RAM/VRAM policy, but can route spoken turns
to a smaller Ollama model and, only after an explicit GPU co-residency probe,
allow that fast voice model to remain in VRAM while XTTS speaks.
"""
from __future__ import annotations

import ctypes
import gc
import glob
import json
import logging
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable

from config.settings import settings
from runtime.hardware_runtime import hardware_runtime
from runtime.memory_policy import MemoryAction, MemoryPressureStateMachine
from runtime.hybrid_runtime import choose_document_route, choose_llm_route, groq_configured, gemini_configured

logger = logging.getLogger("aura.runtime.guardian")


class ResourcePressureError(RuntimeError):
    """Raised when starting another heavyweight model would be unsafe."""


@dataclass(frozen=True)
class ResourceSnapshot:
    ram_used_pct: float = 0.0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    vram_used_pct: float = 0.0
    gpu_name: str = ""
    ollama_vram_mb: float = 0.0
    ollama_model: str = ""

    @property
    def pressure(self) -> str:
        if self.ram_used_pct >= settings.RESOURCE_RAM_EMERGENCY_PCT:
            return "EMERGENCY"
        if self.ram_used_pct >= settings.RESOURCE_RAM_CRITICAL_PCT:
            return "CRITICAL"
        if self.ram_used_pct >= settings.RESOURCE_RAM_WARN_PCT:
            return "WARN"
        if self.vram_used_pct >= settings.RESOURCE_VRAM_CRITICAL_PCT:
            return "CRITICAL"
        if self.vram_used_pct >= settings.RESOURCE_VRAM_WARN_PCT:
            return "WARN"
        return "NORMAL"


@dataclass(frozen=True)
class ResourceDecision:
    backend: str
    reason: str
    snapshot: ResourceSnapshot
    ollama_unloaded: bool = True

    @property
    def use_fallback(self) -> bool:
        return self.backend == "fallback"


class _MEMORYSTATUSEX(ctypes.Structure):
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


class ResourceGuardian:
    """Coordinates LLM, STT and TTS resource use without owning their logic."""

    def __init__(self, llm_manager, voice_engine, *, clock: Callable[[], float] = time.monotonic):
        self.llm_manager = llm_manager
        self.voice_engine = voice_engine
        self.clock = clock
        self._last_tts_use = 0.0
        self._last_gpu_sample_at = 0.0
        self._cached_gpu = (0.0, 0.0, "")
        self._gpu_probe_source = "not-run"
        self._gpu_probe_detail = ""
        self._gpu_probe_executable = ""
        self._last_decision = "Guardian prêt"
        self._last_backend = ""
        self._last_llm_profile: dict = {}
        self._prewarm_lock = threading.RLock()
        self._prewarm_cancel_requested = threading.Event()
        self._xtts_prewarm_active = False
        self._xtts_prewarm_last_result = "not-run"
        self._xtts_trial_last_result = "not-run"
        self._xtts_trial_last_metrics: dict = {}
        self._voice_llm_prewarm_cancel_requested = threading.Event()
        self._voice_llm_prewarm_active = False
        self._voice_llm_prewarm_last_result = "not-run"
        self._last_gpu_attribution: dict = {
            "status": "not-run", "reason": "not-run", "source": "",
            "nvidia_used_before_mb": 0.0, "nvidia_used_after_mb": 0.0,
            "nvidia_delta_mb": 0.0, "ollama_claimed_vram_mb": 0.0,
        }
        self._memory_policy = MemoryPressureStateMachine()

    # ------------------------------------------------------------------
    # Sampling
    @staticmethod
    def _ram_snapshot() -> tuple[float, float, float]:
        try:
            if os.name == "nt":
                stat = _MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
                ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                if not ok:
                    raise OSError("GlobalMemoryStatusEx failed")
                total = float(stat.ullTotalPhys)
                avail = float(stat.ullAvailPhys)
                used_pct = 100.0 * max(0.0, total - avail) / total if total else 0.0
                return used_pct, total / (1024**3), avail / (1024**3)
            meminfo = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    key, value = line.split(":", 1)
                    meminfo[key] = float(value.strip().split()[0]) * 1024.0
            total = meminfo.get("MemTotal", 0.0)
            avail = meminfo.get("MemAvailable", meminfo.get("MemFree", 0.0))
            used_pct = 100.0 * max(0.0, total - avail) / total if total else 0.0
            return used_pct, total / (1024**3), avail / (1024**3)
        except Exception:
            logger.debug("Mesure RAM indisponible", exc_info=True)
            return 0.0, 0.0, 0.0

    @staticmethod
    def _find_nvidia_smi() -> str | None:
        """Find nvidia-smi without relying only on the inherited PATH.

        Windows Store / launcher contexts can expose a different PATH than an
        interactive cmd.exe.  Search the common NVIDIA driver locations too.
        """
        if os.name != "nt":
            return None

        explicit = os.environ.get("NVIDIA_SMI_PATH", "").strip().strip('"')
        if explicit and os.path.isfile(explicit):
            return explicit

        for name in ("nvidia-smi.exe", "nvidia-smi"):
            found = shutil.which(name)
            if found:
                return found

        candidates: list[str] = []
        system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
        if system_root:
            candidates.extend([
                os.path.join(system_root, "System32", "nvidia-smi.exe"),
                os.path.join(system_root, "Sysnative", "nvidia-smi.exe"),
            ])
        for env_name in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env_name)
            if base:
                candidates.append(os.path.join(base, "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe"))

        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate

        # Rare driver-store installs do not expose NVSMI in PATH/System32.
        if system_root:
            store = os.path.join(system_root, "System32", "DriverStore", "FileRepository")
            patterns = [
                os.path.join(store, "nv*_amd64_*", "nvidia-smi.exe"),
                os.path.join(store, "nv*", "nvidia-smi.exe"),
            ]
            for pattern in patterns:
                matches = sorted(glob.glob(pattern))
                if matches:
                    return matches[-1]
        return None

    @classmethod
    def _run_nvidia_smi_detailed(cls) -> tuple[float, float, str, str, str]:
        executable = cls._find_nvidia_smi()
        if not executable:
            return 0.0, 0.0, "", "", "nvidia-smi introuvable"
        cmd = [executable, "--query-gpu=memory.used,memory.total,name", "--format=csv,noheader,nounits"]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        base_timeout = max(2.5, float(settings.RESOURCE_GPU_QUERY_TIMEOUT))
        attempts = (base_timeout, max(5.0, base_timeout * 2.0))
        last_error = ""
        for index, timeout in enumerate(attempts, start=1):
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=timeout, check=False, creationflags=flags,
                )
                if result.returncode != 0:
                    stderr = (result.stderr or "").strip().replace("\r", " ").replace("\n", " ")
                    last_error = f"exit={result.returncode} {stderr}".strip()
                    continue
                line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
                parts = [part.strip() for part in line.split(",", 2)]
                if len(parts) < 3:
                    last_error = f"sortie CSV invalide: {line[:120]}"
                    continue
                used, total = float(parts[0]), float(parts[1])
                if total <= 0 or used < 0:
                    last_error = f"valeurs VRAM invalides used={used} total={total}"
                    continue
                return used, total, parts[2], executable, f"attempt={index} timeout={timeout:.1f}s"
            except subprocess.TimeoutExpired:
                last_error = f"timeout après {timeout:.1f}s"
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        return 0.0, 0.0, "", executable, last_error or "échec nvidia-smi"

    @classmethod
    def _run_nvidia_smi(cls) -> tuple[float, float, str]:
        used, total, name, _path, _detail = cls._run_nvidia_smi_detailed()
        return used, total, name

    @staticmethod
    def _load_nvml_dll():
        if os.name != "nt":
            return None, "NVML réservé à Windows"
        candidates = ["nvml.dll"]
        system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
        if system_root:
            candidates.append(os.path.join(system_root, "System32", "nvml.dll"))
        for env_name in ("ProgramW6432", "ProgramFiles"):
            base = os.environ.get(env_name)
            if base:
                candidates.append(os.path.join(base, "NVIDIA Corporation", "NVSMI", "nvml.dll"))
        errors = []
        for candidate in candidates:
            try:
                return ctypes.WinDLL(candidate), candidate
            except Exception as exc:
                errors.append(f"{candidate}: {type(exc).__name__}")
        return None, "; ".join(errors[-3:]) or "nvml.dll introuvable"

    @classmethod
    def _run_nvml_ctypes(cls) -> tuple[float, float, str, str]:
        """Query NVIDIA memory through NVML without creating a CUDA context."""
        dll, dll_source = cls._load_nvml_dll()
        if dll is None:
            return 0.0, 0.0, "", str(dll_source)

        class _NvmlMemory(ctypes.Structure):
            _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]

        initialized = False
        try:
            init = getattr(dll, "nvmlInit_v2", None) or getattr(dll, "nvmlInit", None)
            get_count = getattr(dll, "nvmlDeviceGetCount_v2", None) or getattr(dll, "nvmlDeviceGetCount", None)
            get_handle = getattr(dll, "nvmlDeviceGetHandleByIndex_v2", None) or getattr(dll, "nvmlDeviceGetHandleByIndex", None)
            get_mem = getattr(dll, "nvmlDeviceGetMemoryInfo", None)
            get_name = getattr(dll, "nvmlDeviceGetName", None)
            shutdown = getattr(dll, "nvmlShutdown", None)
            if not all((init, get_count, get_handle, get_mem)):
                return 0.0, 0.0, "", "fonctions NVML manquantes"
            if int(init()) != 0:
                return 0.0, 0.0, "", "nvmlInit a échoué"
            initialized = True
            count = ctypes.c_uint(0)
            if int(get_count(ctypes.byref(count))) != 0 or count.value < 1:
                return 0.0, 0.0, "", "aucun GPU NVIDIA NVML"

            # Choose the NVIDIA adapter with the largest dedicated VRAM.
            best = (0.0, 0.0, "")
            for index in range(int(count.value)):
                handle = ctypes.c_void_p()
                if int(get_handle(ctypes.c_uint(index), ctypes.byref(handle))) != 0:
                    continue
                mem = _NvmlMemory()
                if int(get_mem(handle, ctypes.byref(mem))) != 0:
                    continue
                name = f"NVIDIA GPU {index}"
                if get_name is not None:
                    buf = ctypes.create_string_buffer(128)
                    try:
                        if int(get_name(handle, buf, ctypes.c_uint(len(buf)))) == 0:
                            name = buf.value.decode("utf-8", errors="replace") or name
                    except Exception:
                        pass
                used_mb = float(mem.used) / (1024 * 1024)
                total_mb = float(mem.total) / (1024 * 1024)
                if total_mb > best[1]:
                    best = (used_mb, total_mb, name)
            if best[1] > 0:
                return best[0], best[1], best[2], str(dll_source)
            return 0.0, 0.0, "", "NVML n'a retourné aucune mémoire GPU"
        except Exception as exc:
            return 0.0, 0.0, "", f"{type(exc).__name__}: {exc}"
        finally:
            if initialized:
                try:
                    shutdown = getattr(dll, "nvmlShutdown", None)
                    if shutdown is not None:
                        shutdown()
                except Exception:
                    pass

    def _run_windows_counter_fallback(self) -> tuple[float, float, str, str]:
        """Last-resort Windows counter using the already validated Dual Brain total VRAM.

        We only trust this fallback when the explicit co-residency probe created a
        marker containing the GPU name and total dedicated VRAM.
        """
        if os.name != "nt":
            return 0.0, 0.0, "", "PowerShell fallback réservé à Windows"
        marker = self.dual_brain_marker()
        total = float(marker.get("vram_total_mb") or 0.0)
        name = str(marker.get("gpu_name") or "").strip()
        if not marker.get("passed") or total <= 0:
            return 0.0, 0.0, "", "marqueur Dual Brain sans VRAM validée"
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
            candidate = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe") if system_root else ""
            if candidate and os.path.isfile(candidate):
                powershell = candidate
        if not powershell:
            return 0.0, 0.0, "", "PowerShell introuvable"
        command = (
            r"$s=(Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -ErrorAction Stop).CounterSamples;"
            "$m=($s|Measure-Object -Property CookedValue -Maximum).Maximum;"
            "if($null -eq $m){$m=0};[Console]::Out.WriteLine([math]::Round($m/1MB,2))"
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5.0,
                check=False, creationflags=flags,
            )
            if result.returncode != 0:
                return 0.0, 0.0, "", f"PowerShell exit={result.returncode}"
            raw = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "0").replace(",", ".")
            used = max(0.0, float(raw))
            if used > total * 1.10:
                return 0.0, 0.0, "", f"compteur incohérent used={used:.0f} > total={total:.0f}"
            return used, total, name or "NVIDIA GPU (Dual Brain marker)", str(powershell)
        except Exception as exc:
            return 0.0, 0.0, "", f"{type(exc).__name__}: {exc}"

    def _probe_gpu_memory(self) -> tuple[float, float, str]:
        used, total, name, executable, detail = self._run_nvidia_smi_detailed()
        if total > 0:
            self._gpu_probe_source = "nvidia-smi"
            self._gpu_probe_executable = executable
            self._gpu_probe_detail = detail
            return used, total, name

        smi_error = detail
        used, total, name, nvml_detail = self._run_nvml_ctypes()
        if total > 0:
            self._gpu_probe_source = "nvml.dll"
            self._gpu_probe_executable = nvml_detail
            self._gpu_probe_detail = f"fallback après nvidia-smi: {smi_error}"
            return used, total, name

        used, total, name, ps_detail = self._run_windows_counter_fallback()
        if total > 0:
            self._gpu_probe_source = "windows-counter+dual-marker"
            self._gpu_probe_executable = ps_detail
            self._gpu_probe_detail = f"nvidia-smi={smi_error}; nvml={nvml_detail}"
            return used, total, name

        self._gpu_probe_source = "unavailable"
        self._gpu_probe_executable = executable
        self._gpu_probe_detail = f"nvidia-smi={smi_error}; nvml={nvml_detail}; powershell={ps_detail}"
        return 0.0, 0.0, ""

    def _gpu_snapshot(self, *, force: bool = False) -> tuple[float, float, str]:
        now = self.clock()
        refresh = max(1.0, float(settings.RESOURCE_GPU_SAMPLE_SECONDS))
        if force or now - self._last_gpu_sample_at >= refresh:
            self._cached_gpu = self._probe_gpu_memory()
            self._last_gpu_sample_at = now
        return self._cached_gpu

    def _running_info(self, model: str | None = None) -> dict | None:
        getter = getattr(self.llm_manager, "running_model_info", None)
        if not callable(getter):
            return None
        try:
            return getter(model=model)
        except TypeError:  # backward-compatible fakes/tests
            return getter()

    def _unload_model(self, model: str | None = None) -> bool:
        unload = getattr(self.llm_manager, "unload", None)
        if not callable(unload):
            return False
        try:
            return bool(unload(model=model))
        except TypeError:
            return bool(unload())

    def _model_available(self, model: str) -> bool:
        getter = getattr(self.llm_manager, "model_available", None)
        if not callable(getter):
            return model == settings.LLM_TEXT_MODEL
        try:
            return bool(getter(model))
        except Exception:
            return False

    def _model_processor_info(self, model: str) -> dict:
        getter = getattr(self.llm_manager, "model_processor_info", None)
        if callable(getter):
            try:
                return dict(getter(model=model) or {})
            except TypeError:
                try:
                    return dict(getter(model) or {})
                except Exception:
                    pass
            except Exception:
                pass
        info = self._running_info(model) or {}
        size = max(0, int(info.get("size", 0) or 0))
        size_vram = max(0, int(info.get("size_vram", 0) or 0))
        ratio = min(1.0, float(size_vram) / float(size)) if size > 0 else 0.0
        return {
            "model": str(info.get("name") or info.get("model") or model),
            "size": size,
            "size_vram": size_vram,
            "gpu_ratio": ratio,
            "processor": "not-loaded" if size <= 0 else "100% CPU" if size_vram <= 0 else f"{int(round(ratio * 100.0))}% GPU",
        }

    def _voice_cold_load_projection(self, snapshot: ResourceSnapshot) -> tuple[float, float]:
        estimate_gb = max(0.0, float(settings.DUAL_BRAIN_VOICE_RAM_ESTIMATE_GB))
        if snapshot.ram_total_gb <= 0 or snapshot.ram_available_gb <= 0:
            return 100.0, -1.0
        used_gb = max(0.0, snapshot.ram_total_gb - snapshot.ram_available_gb)
        predicted_pct = 100.0 * (used_gb + estimate_gb) / snapshot.ram_total_gb
        return predicted_pct, snapshot.ram_available_gb - estimate_gb

    def _voice_gpu_probe_eligible(self, model: str, snapshot: ResourceSnapshot) -> tuple[bool, str, float]:
        if not settings.VOICE_GPU_PROBE_ENABLED:
            return False, "disabled", 0.0
        if snapshot.vram_total_mb < 1024 or "nvidia" not in str(snapshot.gpu_name or "").casefold():
            return False, "no-nvidia-compute", 0.0
        if snapshot.ram_used_pct > float(settings.VOICE_GPU_PROBE_MAX_RAM_PCT):
            return False, "ram-percent", 0.0
        if snapshot.ram_available_gb < float(settings.VOICE_GPU_PROBE_MIN_AVAILABLE_GB):
            return False, "ram-headroom", 0.0
        getter = getattr(self.llm_manager, "local_model_info", None)
        if not callable(getter):
            return False, "model-metadata-unavailable", 0.0
        try:
            meta = getter(model) or {}
        except Exception:
            return False, "model-metadata-error", 0.0
        model_mb = max(0.0, float(meta.get("size", 0) or 0) / (1024 * 1024))
        if model_mb <= 0:
            return False, "model-size-unknown", 0.0
        free_vram_mb = max(0.0, snapshot.vram_total_mb - snapshot.vram_used_mb)
        usable_vram_mb = max(0.0, free_vram_mb - float(settings.VOICE_GPU_PROBE_VRAM_RESERVE_MB))
        if model_mb > usable_vram_mb:
            return False, "model-does-not-fit-vram", model_mb
        return True, "fit", model_mb

    def _verify_nvidia_physical_attribution(
        self, *, before_used_mb: float, claimed_vram_mb: float
    ) -> tuple[bool, str, dict]:
        """Cross-check an Ollama GPU claim against the physical NVIDIA adapter.

        /api/ps identifies GPU residency but does not identify the physical
        adapter. On Windows hybrid systems AURA therefore accepts NVIDIA
        attribution only when nvidia-smi or NVML also observes dedicated
        NVIDIA memory. Generic Windows GPU counters are intentionally excluded.
        """
        if not settings.VOICE_NVIDIA_PHYSICAL_CONFIRM_ENABLED or os.name != "nt":
            data = {
                "status": "skipped", "reason": "non-windows-or-disabled",
                "source": self._gpu_probe_source,
                "nvidia_used_before_mb": float(before_used_mb or 0.0),
                "nvidia_used_after_mb": float(before_used_mb or 0.0),
                "nvidia_delta_mb": 0.0,
                "ollama_claimed_vram_mb": float(claimed_vram_mb or 0.0),
            }
            self._last_gpu_attribution = data
            return True, data["reason"], data

        after_used, after_total, after_name = self._gpu_snapshot(force=True)
        source = str(self._gpu_probe_source or "")
        trusted = source in {"nvidia-smi", "nvml.dll"}
        before = max(0.0, float(before_used_mb or 0.0))
        after = max(0.0, float(after_used or 0.0))
        delta = max(0.0, after - before)
        claimed = max(0.0, float(claimed_vram_mb or 0.0))
        min_used = max(0.0, float(settings.VOICE_NVIDIA_CONFIRM_MIN_USED_MB))
        min_delta = max(0.0, float(settings.VOICE_NVIDIA_CONFIRM_MIN_DELTA_MB))
        absolute_ok = after >= min_used
        delta_ok = delta >= min_delta or before >= min_used
        confirmed = bool(
            trusted and after_total >= 1024 and "nvidia" in str(after_name or "").casefold()
            and absolute_ok and delta_ok
        )
        reason = "confirmed" if confirmed else (
            "untrusted-telemetry" if not trusted else
            "nvidia-memory-not-observed" if not absolute_ok else
            "nvidia-memory-delta-too-small"
        )
        data = {
            "status": "pass" if confirmed else "fail", "reason": reason, "source": source,
            "gpu_name": str(after_name or ""), "nvidia_total_mb": float(after_total or 0.0),
            "nvidia_used_before_mb": before, "nvidia_used_after_mb": after,
            "nvidia_delta_mb": delta, "ollama_claimed_vram_mb": claimed,
        }
        self._last_gpu_attribution = data
        return confirmed, reason, data

    def _enforce_postload_host_ram(self, model: str) -> None:
        ram_pct, _total_gb, avail_gb = self._ram_snapshot()
        unsafe = (
            ram_pct >= float(settings.VOICE_GPU_POSTLOAD_MAX_RAM_PCT)
            or (avail_gb > 0 and avail_gb < float(settings.VOICE_GPU_POSTLOAD_MIN_AVAILABLE_GB))
        )
        if not unsafe:
            logger.info(
                "Voice brain postload RAM PASS model=%s ram=%.1f%% avail=%.2fGiB",
                model, ram_pct, avail_gb,
            )
            return
        self._unload_model(model)
        self._wait_model_unloaded(model)
        self._collect()
        logger.warning(
            "Voice brain postload RAM FAIL model=%s ram=%.1f%% avail=%.2fGiB; unloaded before generation",
            model, ram_pct, avail_gb,
        )
        raise ResourcePressureError(
            "Le cerveau vocal a bien été préchargé, mais la mémoire système restante est trop faible. "
            "AURA l'a déchargé avant la génération pour éviter un gel du PC."
        )

    def _probe_voice_brain_gpu_residency(self, profile: dict, snapshot: ResourceSnapshot) -> bool:
        model = str(profile.get("model") or settings.LLM_VOICE_MODEL)
        eligible, reason, model_mb = self._voice_gpu_probe_eligible(model, snapshot)
        logger.info(
            "Voice brain GPU preflight model=%s eligible=%s reason=%s model_size=%.0fMiB ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB reserve=%.0fMiB",
            model, eligible, reason, model_mb, snapshot.ram_used_pct, snapshot.ram_available_gb,
            snapshot.vram_used_mb, snapshot.vram_total_mb, float(settings.VOICE_GPU_PROBE_VRAM_RESERVE_MB),
        )
        if not eligible:
            return False
        warmup = getattr(self.llm_manager, "warmup", None)
        if not callable(warmup):
            return False
        physical_before_mb = 0.0
        if settings.VOICE_NVIDIA_PHYSICAL_CONFIRM_ENABLED and os.name == "nt":
            physical_before_mb, _physical_total_mb, _physical_name = self._gpu_snapshot(force=True)
        try:
            warmup(
                model=model,
                keep_alive=profile.get("keep_alive", settings.RESOURCE_LLM_KEEP_ALIVE_VOICE),
                num_ctx=int(profile.get("num_ctx") or settings.LLM_VOICE_NUM_CTX),
                force=True,
            )
        except Exception as exc:
            logger.warning("Voice brain GPU probe preload failed model=%s error=%s", model, type(exc).__name__)
            return False
        proc = self._model_processor_info(model)
        ratio = float(proc.get("gpu_ratio", 0.0) or 0.0)
        if ratio >= float(settings.VOICE_GPU_OFFLOAD_MIN_RATIO):
            claimed_mb = float(proc.get("size_vram", 0) or 0) / (1024 * 1024)
            confirmed, attribution_reason, attribution = self._verify_nvidia_physical_attribution(
                before_used_mb=physical_before_mb, claimed_vram_mb=claimed_mb
            )
            if not confirmed:
                self._unload_model(model)
                self._wait_model_unloaded(model)
                self._collect()
                logger.warning(
                    "Voice brain physical GPU attribution FAIL model=%s ollama_processor=%s ollama_vram=%.0fMiB "
                    "nvidia_source=%s nvidia_used=%.0f->%.0fMiB delta=%.0fMiB reason=%s; unloaded",
                    model, proc.get("processor", "?"), claimed_mb, attribution.get("source", ""),
                    attribution.get("nvidia_used_before_mb", 0.0), attribution.get("nvidia_used_after_mb", 0.0),
                    attribution.get("nvidia_delta_mb", 0.0), attribution_reason,
                )
                raise ResourcePressureError(
                    "Ollama annonce un calcul GPU, mais AURA ne détecte pas de résidence mémoire sur la RTX NVIDIA. "
                    "Le modèle a été déchargé; AURA ne considère pas l'offload RTX comme validé."
                )
            logger.info(
                "Voice brain physical GPU attribution PASS model=%s ollama_processor=%s ollama_vram=%.0fMiB "
                "nvidia_source=%s nvidia_used=%.0f->%.0fMiB delta=%.0fMiB",
                model, proc.get("processor", "?"), claimed_mb, attribution.get("source", ""),
                attribution.get("nvidia_used_before_mb", 0.0), attribution.get("nvidia_used_after_mb", 0.0),
                attribution.get("nvidia_delta_mb", 0.0),
            )
            self._enforce_postload_host_ram(model)
            logger.info(
                "Voice brain GPU probe PASS model=%s processor=%s gpu_ratio=%.1f%% size_vram=%.0fMiB physical_nvidia=%s",
                model, proc.get("processor", "?"), ratio * 100.0, claimed_mb, attribution.get("status", "unknown"),
            )
            return True
        self._unload_model(model)
        self._wait_model_unloaded(model)
        self._collect()
        logger.warning(
            "Voice brain GPU probe FAIL model=%s processor=%s gpu_ratio=%.1f%%; unloaded before generation",
            model, proc.get("processor", "?"), ratio * 100.0,
        )
        raise ResourcePressureError(
            "Le test du cerveau vocal confirme qu'Ollama ne l'a pas placé sur la RTX. "
            "AURA l'a déchargé avant la génération pour protéger la mémoire système."
        )

    def _enforce_voice_brain_load_safety(self, profile: dict, snapshot: ResourceSnapshot) -> None:
        """Fail closed before an unsafe cold voice-brain load or CPU-only residency.

        The target laptop has a supported NVIDIA compute GPU but a cold Ollama
        voice model was observed consuming system RAM until 98.6%. We cannot
        change the environment of an already-running Ollama server from AURA,
        so the safe contract is: verify actual /api/ps VRAM residency when the
        model is loaded, and conservatively preflight RAM before the first load.
        """
        if str(profile.get("provider") or "local").casefold() != "local":
            return
        if str(profile.get("name") or "").casefold() not in {"voice-fast", "voice-safe"}:
            return
        model = str(profile.get("model") or settings.LLM_VOICE_MODEL)
        proc = self._model_processor_info(model)
        size = int(proc.get("size", 0) or 0)
        gpu_ratio = float(proc.get("gpu_ratio", 0.0) or 0.0)
        nvidia_compute = snapshot.vram_total_mb >= 1024 and "nvidia" in str(snapshot.gpu_name or "").casefold()

        if size > 0:
            if (
                settings.VOICE_REQUIRE_GPU_WHEN_NVIDIA
                and nvidia_compute
                and gpu_ratio < float(settings.VOICE_GPU_OFFLOAD_MIN_RATIO)
            ):
                self._unload_model(model)
                self._wait_model_unloaded(model)
                self._collect()
                logger.warning(
                    "Voice brain GPU offload absent model=%s processor=%s gpu_ratio=%.1f%% ram=%.1f%%; model unloaded",
                    model, proc.get("processor", "?"), gpu_ratio * 100.0, snapshot.ram_used_pct,
                )
                raise ResourcePressureError(
                    "Le cerveau vocal local est chargé sur le CPU au lieu de la RTX. "
                    "AURA l'a déchargé pour éviter de saturer la RAM. Le TTS reste disponible."
                )
            claimed_mb = float(proc.get("size_vram", 0) or 0) / (1024 * 1024)
            if settings.VOICE_NVIDIA_PHYSICAL_CONFIRM_ENABLED and os.name == "nt" and nvidia_compute:
                # No clean baseline exists for an already-resident model. A
                # trusted absolute NVIDIA memory observation is still enough to
                # reject the Iris-only / RTX-zero mismatch.
                current_used, current_total, current_name = self._gpu_snapshot(force=True)
                source = str(self._gpu_probe_source or "")
                confirmed = bool(
                    source in {"nvidia-smi", "nvml.dll"}
                    and current_total >= 1024
                    and "nvidia" in str(current_name or "").casefold()
                    and current_used >= float(settings.VOICE_NVIDIA_CONFIRM_MIN_USED_MB)
                )
                self._last_gpu_attribution = {
                    "status": "pass" if confirmed else "fail",
                    "reason": "confirmed-resident" if confirmed else "resident-nvidia-memory-not-observed",
                    "source": source, "gpu_name": str(current_name or ""),
                    "nvidia_total_mb": float(current_total or 0.0),
                    "nvidia_used_before_mb": float(current_used or 0.0),
                    "nvidia_used_after_mb": float(current_used or 0.0),
                    "nvidia_delta_mb": 0.0, "ollama_claimed_vram_mb": claimed_mb,
                }
                if not confirmed:
                    self._unload_model(model)
                    self._wait_model_unloaded(model)
                    self._collect()
                    logger.warning(
                        "Voice brain resident physical GPU mismatch model=%s ollama_vram=%.0fMiB "
                        "nvidia_used=%.0fMiB source=%s; unloaded",
                        model, claimed_mb, current_used, source,
                    )
                    raise ResourcePressureError(
                        "Ollama indique que le cerveau vocal est sur un GPU, mais la RTX NVIDIA reste inactive. "
                        "AURA a déchargé le modèle pour éviter d'attribuer à tort le calcul à la RTX."
                    )
            self._enforce_postload_host_ram(model)
            logger.info(
                "Voice brain residency verified model=%s processor=%s gpu_ratio=%.1f%% size_vram=%.0fMiB physical_nvidia=%s",
                model, proc.get("processor", "?"), gpu_ratio * 100.0, claimed_mb,
                self._last_gpu_attribution.get("status", "not-run"),
            )
            return

        predicted_pct, available_after = self._voice_cold_load_projection(snapshot)
        unsafe = (
            predicted_pct >= float(settings.VOICE_COLD_LOAD_MAX_PREDICTED_RAM_PCT)
            or available_after < float(settings.VOICE_COLD_LOAD_MIN_AVAILABLE_AFTER_GB)
        )
        if unsafe:
            # Before failing closed, a supported NVIDIA machine may perform one
            # bounded *empty* Ollama preload when /api/tags proves the model fits
            # dedicated VRAM. We then verify /api/ps immediately. This avoids
            # treating a GPU-resident 3B model as a 4 GiB CPU allocation, while
            # still rejecting CPU fallback before any user prompt is generated.
            if nvidia_compute and self._probe_voice_brain_gpu_residency(profile, snapshot):
                return
            logger.warning(
                "Voice brain cold-load blocked model=%s ram=%.1f%% avail=%.2fGiB predicted=%.1f%% avail_after=%.2fGiB vram=%.0f/%.0fMiB",
                model, snapshot.ram_used_pct, snapshot.ram_available_gb, predicted_pct, available_after,
                snapshot.vram_used_mb, snapshot.vram_total_mb,
            )
            raise ResourcePressureError(
                "Je n'ouvre pas le cerveau vocal local : la projection mémoire est trop proche de la saturation. "
                "AURA garde la voix et l'interface actives sans risquer un gel du PC."
            )
        logger.info(
            "Voice brain cold-load preflight PASS model=%s ram=%.1f%% predicted=%.1f%% avail_after=%.2fGiB gpu=%s",
            model, snapshot.ram_used_pct, predicted_pct, available_after, snapshot.gpu_name or "unknown",
        )

    def sample(
        self, *, include_ollama: bool = False, force_gpu: bool = False, ollama_model: str | None = None
    ) -> ResourceSnapshot:
        ram_pct, ram_total, ram_avail = self._ram_snapshot()
        vram_used, vram_total, gpu_name = self._gpu_snapshot(force=force_gpu)
        hardware_runtime.register_compute(name=gpu_name, used_mb=vram_used, total_mb=vram_total)
        ollama_vram_mb = 0.0
        ollama_name = ""
        if include_ollama:
            try:
                info = self._running_info(ollama_model)
                if info:
                    ollama_vram_mb = float(info.get("size_vram", 0) or 0) / (1024 * 1024)
                    ollama_name = str(info.get("name") or info.get("model") or "")
            except Exception:
                logger.debug("Etat Ollama indisponible", exc_info=True)
        vram_pct = 100.0 * vram_used / vram_total if vram_total > 0 else 0.0
        return ResourceSnapshot(
            ram_used_pct=ram_pct, ram_total_gb=ram_total, ram_available_gb=ram_avail,
            vram_used_mb=vram_used, vram_total_mb=vram_total, vram_used_pct=vram_pct,
            gpu_name=gpu_name, ollama_vram_mb=ollama_vram_mb, ollama_model=ollama_name,
        )

    # ------------------------------------------------------------------
    # Dual Brain marker / policy
    def dual_brain_marker(self) -> dict:
        path = settings.DUAL_BRAIN_MARKER
        try:
            if not path.is_file():
                return {}
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.debug("Marqueur Dual Brain invalide", exc_info=True)
            return {}

    def dual_brain_co_resident_ready(self, *, snapshot: ResourceSnapshot | None = None) -> bool:
        if not bool(getattr(settings, "LOCAL_LLM_ENABLED", False)):
            return False
        if not (settings.DUAL_BRAIN_ENABLED and settings.DUAL_BRAIN_AUTO_COHABITATION):
            return False
        marker = self.dual_brain_marker()
        if not marker.get("passed"):
            return False
        if str(marker.get("voice_model") or "").casefold() != settings.LLM_VOICE_MODEL.casefold():
            return False
        if snapshot is None:
            snapshot = self.sample(force_gpu=True)
        if self._display_gpu_guard_reason(snapshot, predicted_xtts_mb=self._xtts_estimate_mb()):
            return False
        marker_total = float(marker.get("vram_total_mb") or 0)
        if snapshot.vram_total_mb > 0 and marker_total > 0 and abs(snapshot.vram_total_mb - marker_total) > 512:
            return False
        marker_gpu = str(marker.get("gpu_name") or "").strip().casefold()
        if snapshot.gpu_name and marker_gpu and marker_gpu not in snapshot.gpu_name.casefold() and snapshot.gpu_name.casefold() not in marker_gpu:
            return False
        return True

    def _xtts_estimate_mb(self) -> float:
        marker = self.dual_brain_marker()
        measured = float(marker.get("xtts_vram_mb") or 0)
        return measured if measured > 256 else float(settings.DUAL_BRAIN_XTTS_ESTIMATE_MB)

    @staticmethod
    def _cuda_xtts_requested() -> bool:
        return bool(settings.XTTS_ALLOW_CUDA and settings.XTTS_DEVICE.strip().casefold() == "cuda")

    def _display_gpu_guard_reason(self, snapshot: ResourceSnapshot, *, predicted_xtts_mb: float = 0.0) -> str:
        """Fail closed before CUDA XTTS can destabilize the display adapter.

        The Qt/OpenGL shell and CUDA commonly share one WDDM adapter on laptops.
        A Python exception cannot catch a driver TDR/reset, so the only reliable
        protection is to reject the heavyweight CUDA load *before* it starts
        when dedicated VRAM is unknown or below the validated safety floor.
        """
        if not (self._cuda_xtts_requested() and settings.OPENGL_ORB_ENABLED):
            return ""
        total = float(snapshot.vram_total_mb or 0.0)
        if total <= 0:
            return "VRAM GPU de calcul non mesurable; XTTS CUDA bloqué par sécurité"
        hw = hardware_runtime.snapshot()
        separated = bool(
            hw.display_compute_separated is True
            and "intel" in str(hw.gl_renderer or "").casefold()
            and "nvidia" in str(hw.compute_gpu or snapshot.gpu_name or "").casefold()
        )
        predicted = max(0.0, float(predicted_xtts_mb))
        free_after = total - float(snapshot.vram_used_mb or 0.0) - predicted
        if separated:
            reserve = max(0.0, float(settings.XTTS_SAFE_PROBE_VRAM_RESERVE_MB))
            if free_after < reserve:
                return f"réserve RTX de calcul insuffisante après XTTS ({free_after:.0f} < {reserve:.0f} MiB)"
            logger.info(
                "XTTS display guard bypassed: Intel display + NVIDIA compute separated total=%.0fMiB free_after=%.0fMiB reserve=%.0fMiB",
                total, free_after, reserve,
            )
            return ""
        minimum = max(0.0, float(settings.XTTS_CUDA_DISPLAY_MIN_VRAM_MB))
        if total < minimum:
            return f"GPU d'affichage {total:.0f} MiB < seuil XTTS CUDA sûr {minimum:.0f} MiB"
        reserve = max(0.0, float(settings.RESOURCE_DISPLAY_GPU_RESERVE_MB))
        if free_after < reserve:
            return f"réserve GPU d'affichage insuffisante après XTTS ({free_after:.0f} < {reserve:.0f} MiB)"
        return ""

    def xtts_safe_residency_probe(self) -> dict:
        """Dry-run hardware-aware XTTS eligibility probe.

        This method NEVER loads XTTS, changes CUDA state, unloads Ollama, or
        changes Windows GPU preferences. It only combines measured dedicated
        NVIDIA VRAM, system RAM and the validated OpenGL/compute topology.
        """
        result = {
            "enabled": bool(settings.XTTS_SAFE_RESIDENCY_PROBE),
            "dry_run": True,
            "eligible": False,
            "reason": "disabled",
            "topology": "unknown",
            "display_compute_separated": None,
            "ram_available_gb": 0.0,
            "vram_total_mb": 0.0,
            "vram_used_mb": 0.0,
            "xtts_estimate_mb": 0.0,
            "predicted_free_vram_mb": 0.0,
            "shared_memory_counted_for_cuda": False,
        }
        if not settings.XTTS_SAFE_RESIDENCY_PROBE:
            logger.info("XTTS safe residency probe disabled")
            return result

        snap = self.sample(force_gpu=True)
        hw = hardware_runtime.snapshot()
        estimate = max(0.0, self._xtts_estimate_mb())
        reserve = max(0.0, float(settings.XTTS_SAFE_PROBE_VRAM_RESERVE_MB))
        fragmentation = max(0.0, float(settings.XTTS_SAFE_PROBE_FRAGMENTATION_MB))
        predicted_free = float(snap.vram_total_mb) - float(snap.vram_used_mb) - estimate - fragmentation

        result.update({
            "topology": hw.topology,
            "display_compute_separated": hw.display_compute_separated,
            "ram_available_gb": float(snap.ram_available_gb),
            "ram_used_pct": float(snap.ram_used_pct),
            "vram_total_mb": float(snap.vram_total_mb),
            "vram_used_mb": float(snap.vram_used_mb),
            "xtts_estimate_mb": estimate,
            "predicted_free_vram_mb": predicted_free,
            "vram_reserve_mb": reserve,
            "fragmentation_mb": fragmentation,
        })

        reasons = []
        if hw.display_compute_separated is not True:
            reasons.append("display-compute-not-separated")
        if snap.vram_total_mb <= 0:
            reasons.append("dedicated-vram-unmeasured")
        if snap.ram_available_gb < float(settings.XTTS_SAFE_PROBE_MIN_RAM_AVAILABLE_GB):
            reasons.append("system-ram-headroom")
        if predicted_free < reserve:
            reasons.append("dedicated-vram-headroom")

        result["eligible"] = not reasons
        result["reason"] = "pass-dry-run" if not reasons else ",".join(reasons)
        logger.info(
            "XTTS safe residency probe dry_run=True eligible=%s reason=%s topology=%s "
            "separated=%s ram=%.1f%% avail=%.2fGiB dedicated_vram=%.0f/%.0fMiB "
            "estimate=%.0fMiB fragmentation=%.0fMiB predicted_free=%.0fMiB reserve=%.0fMiB "
            "shared_memory_for_cuda=ignored",
            result["eligible"], result["reason"], result["topology"],
            result["display_compute_separated"], result["ram_used_pct"], result["ram_available_gb"],
            result["vram_used_mb"], result["vram_total_mb"], estimate, fragmentation,
            predicted_free, reserve,
        )
        return result

    def controlled_xtts_cuda_trial(self, probe: dict | None = None) -> dict:
        """Perform one real, silent, reversible XTTS CUDA trial.

        v0.7.1.3.2 deliberately does *not* make XTTS the production voice yet.
        The trial may load the model and synthesize a tiny WAV, but it never
        plays audio. Unless explicitly overridden, the shared XTTS model is
        released in ``finally`` so the historical Piper/voice-brain path stays
        unchanged after the measurement.
        """
        result = {
            "enabled": bool(settings.XTTS_CONTROLLED_TRIAL_ENABLED),
            "attempted": False,
            "passed": False,
            "reason": "disabled",
            "kept_loaded": False,
            "load_seconds": 0.0,
            "inference_seconds": 0.0,
            "vram_before_mb": 0.0,
            "vram_after_load_mb": 0.0,
            "vram_after_inference_mb": 0.0,
            "ram_available_before_gb": 0.0,
            "ram_available_after_load_gb": 0.0,
            "ram_available_after_inference_gb": 0.0,
        }
        self._xtts_trial_last_metrics = result
        if not settings.XTTS_CONTROLLED_TRIAL_ENABLED:
            self._xtts_trial_last_result = "disabled"
            return result
        if not self._cuda_xtts_requested():
            result["reason"] = "cuda-not-enabled"
            self._xtts_trial_last_result = result["reason"]
            logger.info("XTTS controlled CUDA trial skipped: CUDA XTTS non activé")
            return result

        probe = dict(probe or self.xtts_safe_residency_probe())
        if not probe.get("eligible"):
            result["reason"] = f"dry-probe:{probe.get('reason') or 'unsafe'}"
            self._xtts_trial_last_result = result["reason"]
            logger.info("XTTS controlled CUDA trial skipped: %s", result["reason"])
            return result

        # Never perform the experimental cold load while Ollama owns the RTX.
        getter = getattr(self.llm_manager, "running_models", None)
        try:
            running = list(getter() or []) if callable(getter) else []
        except Exception:
            running = []
        if running:
            result["reason"] = "ollama-resident"
            self._xtts_trial_last_result = result["reason"]
            logger.info("XTTS controlled CUDA trial skipped: Ollama résident")
            return result
        if self._prewarm_cancel_requested.is_set():
            result["reason"] = "cancelled-before-start"
            self._xtts_trial_last_result = result["reason"]
            return result

        before = self.sample(force_gpu=True)
        result.update({
            "vram_before_mb": float(before.vram_used_mb),
            "ram_available_before_gb": float(before.ram_available_gb),
        })
        result["attempted"] = True
        load_started = self.clock()
        keep_loaded = False

        def unsafe_reason(snap: ResourceSnapshot) -> str:
            if snap.ram_used_pct >= float(settings.XTTS_CONTROLLED_TRIAL_MAX_RAM_PCT):
                return "postload-ram-percent"
            if snap.ram_available_gb and snap.ram_available_gb < float(settings.XTTS_CONTROLLED_TRIAL_MIN_RAM_AVAILABLE_GB):
                return "postload-ram-headroom"
            if snap.vram_total_mb <= 0:
                return "postload-vram-unmeasured"
            free_vram = float(snap.vram_total_mb) - float(snap.vram_used_mb)
            if free_vram < float(settings.XTTS_CONTROLLED_TRIAL_MIN_FREE_VRAM_MB):
                return "postload-vram-headroom"
            if snap.vram_used_mb < 256:
                return "cuda-vram-not-observed"
            return ""

        with self._prewarm_lock:
            self._xtts_prewarm_active = True
            try:
                logger.warning(
                    "XTTS controlled CUDA trial START silent=True topology=%s ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB",
                    probe.get("topology"), before.ram_used_pct, before.ram_available_gb,
                    before.vram_used_mb, before.vram_total_mb,
                )
                loaded = bool(self.voice_engine.warmup_xtts_only())
                result["load_seconds"] = max(0.0, self.clock() - load_started)
                if not loaded:
                    result["reason"] = "load-unavailable"
                    return result

                after_load = self.sample(force_gpu=True)
                result.update({
                    "vram_after_load_mb": float(after_load.vram_used_mb),
                    "ram_available_after_load_gb": float(after_load.ram_available_gb),
                })
                reason = unsafe_reason(after_load)
                if reason:
                    result["reason"] = reason
                    logger.warning(
                        "XTTS controlled CUDA trial ROLLBACK stage=load reason=%s ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB",
                        reason, after_load.ram_used_pct, after_load.ram_available_gb,
                        after_load.vram_used_mb, after_load.vram_total_mb,
                    )
                    return result
                if self._prewarm_cancel_requested.is_set():
                    result["reason"] = "cancelled-after-load"
                    return result

                inference = dict(self.voice_engine.probe_xtts_inference(settings.XTTS_CONTROLLED_TRIAL_TEXT) or {})
                result["inference_seconds"] = float(inference.get("synthesis_seconds") or 0.0)
                result["device"] = str(inference.get("device") or "")
                result["cuda_allocated_mb"] = float(inference.get("cuda_allocated_mb") or 0.0)
                result["cuda_reserved_mb"] = float(inference.get("cuda_reserved_mb") or 0.0)
                result["gpu_name"] = str(inference.get("gpu_name") or "")
                after_inference = self.sample(force_gpu=True)
                result.update({
                    "vram_after_inference_mb": float(after_inference.vram_used_mb),
                    "ram_available_after_inference_gb": float(after_inference.ram_available_gb),
                })
                reason = unsafe_reason(after_inference)
                if str(result.get("device")).casefold() != "cuda":
                    reason = reason or "inference-not-cuda"
                if reason:
                    result["reason"] = reason
                    logger.warning(
                        "XTTS controlled CUDA trial ROLLBACK stage=inference reason=%s device=%s ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB",
                        reason, result.get("device"), after_inference.ram_used_pct,
                        after_inference.ram_available_gb, after_inference.vram_used_mb,
                        after_inference.vram_total_mb,
                    )
                    return result

                result["passed"] = True
                result["reason"] = "pass-controlled-trial"
                keep_loaded = bool(settings.XTTS_CONTROLLED_TRIAL_KEEP_LOADED)
                result["kept_loaded"] = keep_loaded
                logger.warning(
                    "XTTS controlled CUDA trial PASS silent=True load=%.3fs infer=%.3fs device=%s "
                    "ram_avail=%.2f->%.2fGiB vram=%.0f->%.0fMiB cuda_alloc=%.0fMiB cuda_reserved=%.0fMiB keep_loaded=%s",
                    result["load_seconds"], result["inference_seconds"], result.get("device"),
                    result["ram_available_before_gb"], result["ram_available_after_inference_gb"],
                    result["vram_before_mb"], result["vram_after_inference_mb"],
                    result.get("cuda_allocated_mb", 0.0), result.get("cuda_reserved_mb", 0.0), keep_loaded,
                )
                return result
            except Exception as exc:
                result["reason"] = f"error:{exc.__class__.__name__}"
                logger.warning("XTTS controlled CUDA trial ERROR; rollback Piper", exc_info=True)
                return result
            finally:
                self._xtts_trial_last_result = str(result.get("reason") or "unknown")
                self._xtts_trial_last_metrics = dict(result)
                if not keep_loaded:
                    try:
                        self.voice_engine.release_xtts_model()
                    finally:
                        self._collect()
                    final = self.sample(force_gpu=True)
                    logger.info(
                        "XTTS controlled CUDA trial cleanup released=True ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB",
                        final.ram_used_pct, final.ram_available_gb, final.vram_used_mb, final.vram_total_mb,
                    )
                self._xtts_prewarm_active = False

    # ------------------------------------------------------------------
    # Orchestration
    def _collect(self) -> None:
        gc.collect()

    def _remote_profile(self, route, *, voice_output: bool, document: bool = False) -> dict:
        provider = str(route.provider or "").casefold()
        model = str(route.model or "")
        profile = {
            "name": f"{provider}-document" if document else (f"{provider}-voice" if voice_output else f"{provider}-text"),
            "provider": provider,
            "remote": True,
            "route_reason": route.reason,
            "model": model,
            "keep_alive": "remote",
            "num_ctx": settings.LLM_VOICE_NUM_CTX if voice_output else settings.LLM_NUM_CTX,
            "num_predict": settings.DOCUMENT_NUM_PREDICT if document else (settings.LLM_VOICE_NUM_PREDICT if voice_output else settings.LLM_NUM_PREDICT),
            "temperature": 0.34 if document else (settings.LLM_VOICE_TEMPERATURE if voice_output else settings.LLM_TEMPERATURE),
            "top_p": 0.88 if document else (settings.LLM_VOICE_TOP_P if voice_output else settings.LLM_TOP_P),
            "compact": bool(voice_output),
            "co_resident": False,
            "document_context": bool(document),
        }

        # P0.6.2.3.3 — Gemini 3 reserves output tokens for internal thinking.
        # AURA's historical voice ceiling (104 tokens) is enough for Groq but
        # can leave Gemini with zero or only a few visible words. Explicit
        # minimal thinking plus a slightly larger *maximum* preserves the short
        # voice contract while guaranteeing room for the visible answer.
        if provider == "gemini" and model.casefold().startswith("gemini-3") and not document:
            profile["thinking_level"] = "minimal"
            if voice_output:
                profile["num_predict"] = max(int(profile["num_predict"]), 384)
            else:
                profile["num_predict"] = max(int(profile["num_predict"]), 768)

        return profile

    def llm_request_profile(
        self,
        *,
        voice_output: bool,
        user_text: str = "",
        force_local: bool = False,
        preferred_provider: str | None = None,
    ) -> dict:
        route = choose_llm_route(
            user_text,
            voice_output=voice_output,
            force_local=force_local,
            preferred_provider=preferred_provider,
        )
        if route.provider in {"groq", "gemini"}:
            remote_available = getattr(self.llm_manager, "remote_available", None)
            if callable(remote_available) and not remote_available(route.provider):
                route = choose_llm_route(user_text, voice_output=voice_output, force_local=True)
        if route.provider in {"groq", "gemini"}:
            profile = self._remote_profile(route, voice_output=voice_output, document=False)
        elif voice_output and settings.RESOURCE_GUARDIAN_ENABLED:
            fast_available = settings.DUAL_BRAIN_ENABLED and self._model_available(settings.LLM_VOICE_MODEL)
            model = settings.LLM_VOICE_MODEL if fast_available else settings.LLM_TEXT_MODEL
            snapshot = self.sample(force_gpu=False)
            co_resident = bool(fast_available and self.dual_brain_co_resident_ready(snapshot=snapshot))
            display_guard = (
                self._display_gpu_guard_reason(snapshot, predicted_xtts_mb=self._xtts_estimate_mb())
                if fast_available else ""
            )
            independent_resident = bool(
                fast_available
                and settings.VOICE_BRAIN_INDEPENDENT_RESIDENCY
                and display_guard
            )
            keep_alive = (
                settings.DUAL_BRAIN_VOICE_KEEP_ALIVE if co_resident
                else settings.VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE if independent_resident
                else settings.RESOURCE_LLM_KEEP_ALIVE_VOICE
            )
            profile = {
                "name": "voice-fast" if fast_available else "voice-safe",
                "provider": "local",
                "remote": False,
                "route_reason": route.reason,
                "model": model,
                "keep_alive": keep_alive,
                "num_ctx": settings.LLM_VOICE_NUM_CTX,
                "num_predict": settings.LLM_VOICE_NUM_PREDICT,
                "temperature": settings.LLM_VOICE_TEMPERATURE,
                "top_p": settings.LLM_VOICE_TOP_P,
                "compact": True,
                "co_resident": co_resident,
                "independent_resident": independent_resident,
                "tts_guard_reason": display_guard,
            }
        else:
            profile = {
                "name": "text",
                "provider": "local",
                "remote": False,
                "route_reason": route.reason,
                "model": settings.LLM_TEXT_MODEL,
                "keep_alive": settings.RESOURCE_LLM_KEEP_ALIVE_TEXT if settings.RESOURCE_GUARDIAN_ENABLED else settings.LLM_KEEP_ALIVE,
                "num_ctx": settings.LLM_NUM_CTX,
                "num_predict": settings.LLM_NUM_PREDICT,
                "temperature": settings.LLM_TEMPERATURE,
                "top_p": settings.LLM_TOP_P,
                "compact": False,
                "co_resident": False,
            }
        self._last_llm_profile = profile
        return profile

    def document_request_profile(self, *, user_text: str = "", preferred_provider: str | None = None) -> dict:
        remote_available = getattr(self.llm_manager, "remote_available", None)
        gemini_ready = bool(callable(remote_available) and remote_available("gemini"))
        groq_ready = bool(callable(remote_available) and remote_available("groq"))
        route = choose_document_route(
            user_text,
            preferred_provider=preferred_provider,
            gemini_ready=gemini_ready,
            groq_ready=groq_ready,
        )
        if route.provider in {"groq", "gemini"}:
            profile = self._remote_profile(route, voice_output=False, document=True)
        else:
            profile = self.llm_request_profile(voice_output=False, user_text=user_text, force_local=True)
            profile["document_context"] = True
            profile["num_predict"] = max(int(profile.get("num_predict") or 0), int(settings.DOCUMENT_NUM_PREDICT))
            profile["temperature"] = min(float(profile.get("temperature") or settings.LLM_TEMPERATURE), 0.42)
        self._last_llm_profile = profile
        return profile

    def _wait_model_unloaded(self, model: str | None = None) -> bool:
        timeout = max(0.0, float(settings.RESOURCE_OLLAMA_UNLOAD_TIMEOUT))
        if timeout <= 0:
            return True
        residual = int(settings.RESOURCE_OLLAMA_RESIDUAL_VRAM_MB * 1024 * 1024)
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            info = self._running_info(model)
            if not info or int(info.get("size_vram", 0) or 0) <= residual:
                return True
            time.sleep(0.12)
        info = self._running_info(model)
        return not info or int(info.get("size_vram", 0) or 0) <= residual

    # compatibility alias
    def _wait_ollama_unloaded(self) -> bool:
        return self._wait_model_unloaded(settings.LLM_TEXT_MODEL)

    def xtts_local_first_hot(self) -> bool:
        """Return True only when the explicitly opt-in CUDA local-first voice is resident."""
        active_voice_engine = str(getattr(getattr(self.voice_engine, "profile", None), "engine", "") or "").lower()
        return bool(
            settings.XTTS_LOCAL_FIRST_ENABLED
            and settings.XTTS_LOCAL_FIRST_PROTECT_RESIDENCY
            and settings.XTTS_ALLOW_CUDA
            and str(settings.XTTS_DEVICE).strip().lower() == "cuda"
            and active_voice_engine == "xtts"
            and self.voice_engine.xtts_model_loaded()
        )

    def prepare_for_llm(self, profile: dict | None = None) -> ResourceSnapshot:
        """Prepare resources for the selected brain without unsafe co-loading."""
        if not settings.RESOURCE_GUARDIAN_ENABLED:
            return self.sample()
        profile = profile or self._last_llm_profile or self.llm_request_profile(voice_output=False)
        model = str(profile.get("model") or settings.LLM_TEXT_MODEL)
        co_resident = bool(profile.get("co_resident"))

        # Runtime v2: when local generative AI is disabled, a forced-local turn
        # must fail closed later in DisabledLocalProvider without evicting STT or
        # XTTS first. This is the key no-Ollama startup/runtime path.
        if str(profile.get("provider") or "local").casefold() == "local" and not bool(getattr(settings, "LOCAL_LLM_ENABLED", False)):
            snapshot = self.sample(force_gpu=False)
            self._last_decision = "Runtime v2: IA locale désactivée, ressources vocales conservées"
            logger.info(
                "Guardian local preparation skipped local_enabled=False model=%s ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB",
                model, snapshot.ram_used_pct, snapshot.ram_available_gb, snapshot.vram_used_mb, snapshot.vram_total_mb,
            )
            return snapshot

        # Remote Groq/Gemini inference consumes no local model RAM/VRAM. Keep XTTS hot
        # and keep local Whisper available as a fallback instead of evicting
        # either resource merely to prepare a network request.
        if str(profile.get("provider") or "local").casefold() in {"groq", "gemini"}:
            snapshot = self.sample(force_gpu=False)
            self._last_decision = f"Hybrid {str(profile.get('provider') or 'cloud').title()}: ressources locales conservées pour la voix"
            logger.info(
                "Guardian before remote LLM provider=%s model=%s ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB xtts_hot=%s",
                str(profile.get("provider") or "remote"), model, snapshot.ram_used_pct, snapshot.ram_available_gb, snapshot.vram_used_mb, snapshot.vram_total_mb,
                self.voice_engine.xtts_model_loaded(),
            )
            return snapshot

        preserve_xtts = bool(profile.get("preserve_xtts_for_voice") and self.xtts_local_first_hot())
        if preserve_xtts:
            running_target = self._running_info(model)
            target_resident = bool(
                running_target
                and int((running_target or {}).get("size", 0) or (running_target or {}).get("size_vram", 0) or 0) > 0
            )
            if not target_resident:
                self._last_decision = "XTTS local-first: cold local LLM bypassed"
                logger.info(
                    "XTTS local-first safe bypass: cold local LLM skipped profile=%s model=%s xtts_hot=True",
                    profile.get("name"), model,
                )
                raise ResourcePressureError(
                    "Je garde ma voix locale XTTS prête : le cerveau local demandé n'est pas déjà résident dans un état sûr. "
                    "AURA évite donc de décharger la voix pour lancer un probe Ollama coûteux."
                )
            logger.info(
                "XTTS local-first residency preserved before LLM profile=%s model=%s resident=True",
                profile.get("name"), model,
            )

        if settings.RESOURCE_RELEASE_STT_BEFORE_LLM:
            self.voice_engine.release_stt_model()

        # The 8B text brain always gets exclusive GPU access. A validated fast
        # voice profile may keep XTTS resident; otherwise preserve v0.6.3 policy.
        if not preserve_xtts and (profile.get("name") == "text" or not co_resident):
            self.voice_engine.release_xtts_model()
        elif preserve_xtts:
            logger.info(
                "XTTS local-first residency priority: skip XTTS release profile=%s model=%s",
                profile.get("name"), model,
            )
        else:
            snap = self.sample(force_gpu=True)
            if snap.ram_used_pct >= settings.RESOURCE_RAM_CRITICAL_PCT:
                self.voice_engine.release_xtts_model()
                profile["co_resident"] = False
                profile["keep_alive"] = settings.RESOURCE_LLM_KEEP_ALIVE_VOICE
                co_resident = False
                logger.info("Dual Brain rétrogradé en mode séquentiel: RAM %.1f%%", snap.ram_used_pct)
            elif self.voice_engine.xtts_model_loaded():
                # v0.7.0.5: predict the transient SYSTEM-RAM cost before a cold
                # voice-brain load. Previously the Guardian reacted only after
                # llama3.2 had already pushed the machine into the critical
                # zone. If the model is already resident there is no cold-load
                # estimate to add.
                running = self._running_info(model)
                model_resident = bool(running and int(running.get("size", 0) or running.get("size_vram", 0) or 0) > 0)
                if not model_resident:
                    estimate_gb = max(0.0, float(settings.DUAL_BRAIN_VOICE_RAM_ESTIMATE_GB))
                    if snap.ram_total_gb > 0 and snap.ram_available_gb > 0:
                        used_gb = max(0.0, snap.ram_total_gb - snap.ram_available_gb)
                        predicted_pct = 100.0 * (used_gb + estimate_gb) / snap.ram_total_gb
                        available_after = snap.ram_available_gb - estimate_gb
                        memory_decision = self._memory_policy.evaluate(
                            ram_percent=snap.ram_used_pct,
                            available_gib=snap.ram_available_gb,
                            voice_brain_loaded=False,
                            xtts_hot=True,
                            predicted_with_voice_percent=predicted_pct,
                            predicted_available_after_gib=available_after,
                        )
                        safe_preload = memory_decision.allow_voice_prewarm
                    else:
                        predicted_pct = 100.0
                        available_after = -1.0
                        safe_preload = False

                    if not safe_preload:
                        self.voice_engine.release_xtts_model()
                        profile["co_resident"] = False
                        profile["keep_alive"] = settings.RESOURCE_LLM_KEEP_ALIVE_VOICE
                        co_resident = False
                        logger.info(
                            "Dual Brain preflight: XTTS libéré avant chargement LLM ram=%.1f%% predicted=%.1f%% avail_after=%.2fGiB estimate=%.2fGiB",
                            snap.ram_used_pct, predicted_pct, available_after, estimate_gb,
                        )
                    else:
                        logger.info(
                            "Dual Brain preflight PASS ram=%.1f%% predicted=%.1f%% avail_after=%.2fGiB estimate=%.2fGiB",
                            snap.ram_used_pct, predicted_pct, available_after, estimate_gb,
                        )

        # Ensure the other Ollama brain isn't consuming either VRAM *or system
        # RAM. On hybrid laptops Ollama can keep a model 100% CPU-resident; the
        # old GPU-only check missed that case and caused the next cold voice
        # load to be rejected even though several GiB could first be reclaimed.
        other_model = settings.LLM_VOICE_MODEL if model == settings.LLM_TEXT_MODEL else settings.LLM_TEXT_MODEL
        if other_model.casefold() != model.casefold():
            info_other = self._running_info(other_model)
            other_size = int((info_other or {}).get("size", 0) or 0)
            other_vram = int((info_other or {}).get("size_vram", 0) or 0)
            if info_other and max(other_size, other_vram) > 0:
                logger.info(
                    "Guardian unloading other Ollama brain before %s model=%s size=%.0fMiB size_vram=%.0fMiB",
                    profile.get("name"), other_model, other_size / (1024 * 1024), other_vram / (1024 * 1024),
                )
                self._unload_model(other_model)
                self._wait_model_unloaded(other_model)

        self._collect()
        snapshot = self.sample(force_gpu=True)
        self._enforce_voice_brain_load_safety(profile, snapshot)
        self._last_decision = "Dual Brain co-résident" if co_resident else "GPU préparé pour LLM"
        logger.info(
            "Guardian before LLM profile=%s model=%s coresident=%s ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB",
            profile.get("name"), model, co_resident, snapshot.ram_used_pct, snapshot.ram_available_gb,
            snapshot.vram_used_mb, snapshot.vram_total_mb,
        )
        if snapshot.ram_used_pct >= settings.RESOURCE_RAM_EMERGENCY_PCT:
            raise ResourcePressureError(
                "Mémoire système presque saturée. AURA a libéré ses modèles non indispensables, "
                "mais il reste trop peu de mémoire pour charger le moteur IA sans risque."
            )
        return snapshot

    def _sequential_tts_handoff(self, model: str, *, strict_test: bool) -> ResourceDecision:
        info_before = self._running_info(model)
        query_ok_getter = getattr(self.llm_manager, "running_model_query_ok", None)
        query_ok = bool(query_ok_getter()) if callable(query_ok_getter) else bool(info_before)
        residual_limit = int(settings.RESOURCE_OLLAMA_RESIDUAL_VRAM_MB * 1024 * 1024)
        already_free = query_ok and (not info_before or int(info_before.get("size_vram", 0) or 0) <= residual_limit)
        if already_free:
            confirmed = True
        else:
            unloaded = self._unload_model(model)
            if model.casefold() == settings.LLM_TEXT_MODEL.casefold():
                confirmed = unloaded and self._wait_ollama_unloaded()
            else:
                confirmed = unloaded and self._wait_model_unloaded(model)

        if settings.RESOURCE_RELEASE_STT_BEFORE_TTS:
            self.voice_engine.release_stt_model()
        self._collect()
        snapshot = self.sample(include_ollama=True, force_gpu=True, ollama_model=model)

        predicted_xtts = 0.0 if self.voice_engine.xtts_model_loaded() else self._xtts_estimate_mb()
        display_guard = self._display_gpu_guard_reason(snapshot, predicted_xtts_mb=predicted_xtts)
        reason = (
            "XTTS CUDA autorisé — aucun LLM local résident"
            if not bool(getattr(settings, "LOCAL_LLM_ENABLED", False))
            else "XTTS CUDA autorisé après libération d'Ollama"
        )
        unsafe = bool(display_guard)
        if display_guard:
            reason = display_guard
        if snapshot.ram_used_pct >= settings.RESOURCE_RAM_EMERGENCY_PCT:
            unsafe, reason = True, "RAM en zone d'urgence"
        elif snapshot.ram_used_pct >= settings.RESOURCE_RAM_CRITICAL_PCT:
            unsafe, reason = True, "RAM en zone critique"
        elif not confirmed:
            unsafe, reason = True, "Ollama n'a pas confirmé sa libération"
        elif snapshot.ollama_vram_mb > settings.RESOURCE_OLLAMA_RESIDUAL_VRAM_MB:
            unsafe, reason = True, "Ollama occupe encore la VRAM"
        elif snapshot.vram_total_mb > 0 and snapshot.vram_used_pct >= settings.RESOURCE_VRAM_CRITICAL_PCT:
            unsafe, reason = True, "VRAM déjà trop occupée"

        if unsafe:
            self.voice_engine.release_xtts_model()
            self._collect()
            if strict_test:
                raise ResourcePressureError(f"Test XTTS bloqué par Resource Guardian : {reason}. Ferme les applications lourdes puis réessaie.")
            backend = "fallback"
        else:
            backend = "xtts"
            self._last_tts_use = self.clock()
        return ResourceDecision(backend, reason, snapshot, ollama_unloaded=confirmed)

    def realtime_dialogue_ready(self, profile: dict | None = None) -> bool:
        """Return whether early speech may overlap the active voice LLM.

        This check is deliberately non-destructive: it never unloads Ollama or
        XTTS.  If the machine cannot guarantee hot co-residency, realtime speech
        simply falls back to the normal post-generation TTS path.
        """
        if not settings.REALTIME_DIALOGUE_ENABLED:
            return False
        profile = dict(profile or self._last_llm_profile or {})
        model = str(profile.get("model") or settings.LLM_VOICE_MODEL)
        if str(profile.get("provider") or "local").casefold() in {"groq", "gemini"}:
            # Remote generation never competes for local VRAM. If XTTS is hot,
            # producer/consumer speech may start as soon as the first complete
            # sentence arrives from Groq.
            if not self.voice_engine.xtts_model_loaded():
                return False
            snapshot = self.sample(force_gpu=False)
            return bool(snapshot.ram_used_pct < settings.REALTIME_DIALOGUE_MAX_RAM_PCT)
        if settings.REALTIME_DIALOGUE_REQUIRE_CORESIDENCE and not bool(profile.get("co_resident")):
            return False
        if model.casefold() != settings.LLM_VOICE_MODEL.casefold():
            return False
        if not self.dual_brain_co_resident_ready():
            return False
        if not self.voice_engine.xtts_model_loaded():
            return False
        return True

    def prepare_for_realtime_tts(self, profile: dict | None = None) -> ResourceDecision:
        """Reserve hot XTTS without ever evicting the LLM mid-generation."""
        profile = dict(profile or self._last_llm_profile or {})
        if not self.realtime_dialogue_ready(profile):
            raise ResourcePressureError("Dialogue temps réel indisponible : co-résidence locale non sûre.")
        model = str(profile.get("model") or settings.LLM_VOICE_MODEL)
        if settings.RESOURCE_RELEASE_STT_BEFORE_TTS:
            self.voice_engine.release_stt_model()
        self._collect()
        remote = str(profile.get("provider") or "local").casefold() in {"groq", "gemini"}
        snapshot = self.sample(include_ollama=not remote, force_gpu=True, ollama_model=None if remote else model)
        display_guard = self._display_gpu_guard_reason(snapshot, predicted_xtts_mb=0.0)
        if display_guard:
            raise ResourcePressureError(f"Dialogue temps réel suspendu : {display_guard}.")
        if snapshot.ram_used_pct >= settings.REALTIME_DIALOGUE_MAX_RAM_PCT:
            raise ResourcePressureError(
                f"Dialogue temps réel suspendu : RAM {snapshot.ram_used_pct:.1f}% >= "
                f"{settings.REALTIME_DIALOGUE_MAX_RAM_PCT:.1f}%."
            )
        if snapshot.vram_total_mb > 0:
            free_after = snapshot.vram_total_mb - snapshot.vram_used_mb
            used_pct = 100.0 * snapshot.vram_used_mb / snapshot.vram_total_mb
            if used_pct > settings.DUAL_BRAIN_MAX_VRAM_PCT or free_after < settings.DUAL_BRAIN_MIN_FREE_VRAM_MB:
                raise ResourcePressureError("Dialogue temps réel suspendu : marge VRAM insuffisante.")
        reason = "Realtime Dialogue: LLM vocal + XTTS chaud autorisés en parallèle"
        self._last_decision = reason
        self._last_backend = "xtts"
        self._last_tts_use = self.clock()
        logger.info(
            "Realtime dialogue reserve PASS model=%s ram=%.1f%% vram=%.0f/%.0fMiB",
            model, snapshot.ram_used_pct, snapshot.vram_used_mb, snapshot.vram_total_mb,
        )
        return ResourceDecision("xtts", reason, snapshot, ollama_unloaded=False)

    def prepare_for_tts(self, *, strict_test: bool = False) -> ResourceDecision:
        backend_kind = "none"
        try:
            backend_kind = str(self.voice_engine.output_backend_kind())
        except Exception:
            logger.debug("Impossible de déterminer le backend TTS avant arbitrage", exc_info=True)
        if backend_kind in {"elevenlabs", "gradium", "resemble"}:
            snapshot = self.sample(include_ollama=False, force_gpu=False)
            reason = f"{backend_kind} cloud concis: aucune résidence GPU locale TTS requise"
            self._last_decision = reason
            self._last_backend = backend_kind
            self._last_tts_use = self.clock()
            logger.info("Guardian before TTS decision=%s ram=%.1f%% avail=%.2fGiB", backend_kind, snapshot.ram_used_pct, snapshot.ram_available_gb)
            return ResourceDecision(backend_kind, reason, snapshot, ollama_unloaded=False)
        if not settings.RESOURCE_GUARDIAN_ENABLED:
            return ResourceDecision("xtts", "Guardian désactivé", self.sample())

        profile = self._last_llm_profile or {"model": settings.LLM_TEXT_MODEL, "co_resident": False, "name": "text"}
        model = str(profile.get("model") or settings.LLM_TEXT_MODEL)
        remote = str(profile.get("provider") or "local").casefold() in {"groq", "gemini"}

        # A remote LLM does not own local VRAM. Never run the sequential Ollama
        # handoff here: doing so would query/unload a model that did not produce
        # the answer and could also evict the local STT fallback for no benefit.
        # Only enforce the same RAM/VRAM safety envelope used by hot realtime
        # speech, then let VoiceEngine load/use XTTS directly.
        if remote:
            provider_name = str(profile.get("provider") or "cloud")
            snapshot = self.sample(include_ollama=False, force_gpu=True)
            xtts_hot = bool(self.voice_engine.xtts_model_loaded())

            # Patch 26.8.7 — Voice Identity Lock.
            # The normal post-load VRAM reserve is a *load admission* guard.
            # Once XTTS is already resident, switching to Piper does not recover
            # that VRAM unless XTTS is explicitly unloaded, so it only changes
            # AURA's voice for no useful resource gain. Keep the configured XTTS
            # voice stable while it is healthy/resident. Release it only for a
            # genuine emergency condition.
            if xtts_hot:
                free_now = (
                    float(snapshot.vram_total_mb) - float(snapshot.vram_used_mb)
                    if snapshot.vram_total_mb > 0 else 0.0
                )
                emergency_floor = max(
                    256.0,
                    float(getattr(settings, "XTTS_SAFE_PROBE_FRAGMENTATION_MB", 384.0)),
                )
                ram_emergency = snapshot.ram_used_pct >= float(settings.RESOURCE_RAM_CRITICAL_PCT)
                vram_emergency = snapshot.vram_total_mb > 0 and free_now < emergency_floor
                if not ram_emergency and not vram_emergency:
                    reason = (
                        f"Hybrid {provider_name.title()}: Voice Identity Lock — "
                        "XTTS déjà résident, voix conservée"
                    )
                    self._last_decision = reason
                    self._last_backend = "xtts"
                    self._last_tts_use = self.clock()
                    logger.info(
                        "Guardian before TTS decision=xtts provider=%s voice_identity_lock=True "
                        "ram=%.1f%% vram=%.0f/%.0fMiB free=%.0fMiB",
                        provider_name, snapshot.ram_used_pct,
                        snapshot.vram_used_mb, snapshot.vram_total_mb, free_now,
                    )
                    return ResourceDecision("xtts", reason, snapshot, ollama_unloaded=False)

                # A real emergency is the only resource-driven case allowed to
                # change voice. Free XTTS first so the fallback actually
                # recovers resources instead of merely speaking with Piper.
                try:
                    self.voice_engine.release_xtts_model()
                except Exception:
                    logger.warning("Voice Identity Lock emergency: XTTS release failed", exc_info=True)
                reason = (
                    f"Hybrid {provider_name.title()}: bascule Piper de sécurité critique "
                    f"(RAM={snapshot.ram_used_pct:.1f}%, VRAM libre={free_now:.0f} MiB)"
                )
                self._last_decision = reason
                self._last_backend = "fallback"
                logger.warning(
                    "Guardian before TTS decision=fallback provider=%s "
                    "voice_identity_emergency=True reason=%s",
                    provider_name, reason,
                )
                if strict_test:
                    raise ResourcePressureError(reason)
                return ResourceDecision("fallback", reason, snapshot, ollama_unloaded=False)

            # XTTS is cold: the existing safety envelope still decides whether
            # loading the CUDA model is allowed.
            predicted_xtts = self._xtts_estimate_mb()
            display_guard = self._display_gpu_guard_reason(snapshot, predicted_xtts_mb=predicted_xtts)
            if display_guard:
                reason = f"Hybrid {provider_name.title()}: {display_guard}"
                self._last_decision = reason
                self._last_backend = "fallback"
                logger.warning(
                    "Guardian before TTS decision=fallback provider=%s reason=%s",
                    provider_name, display_guard,
                )
                if strict_test:
                    raise ResourcePressureError(reason)
                return ResourceDecision("fallback", reason, snapshot, ollama_unloaded=False)
            safe = snapshot.ram_used_pct < settings.RESOURCE_RAM_CRITICAL_PCT
            if snapshot.vram_total_mb > 0:
                predicted_used = snapshot.vram_used_mb + predicted_xtts
                predicted_pct = 100.0 * predicted_used / snapshot.vram_total_mb
                free_after = snapshot.vram_total_mb - predicted_used
                safe = (
                    safe
                    and predicted_pct <= settings.DUAL_BRAIN_MAX_VRAM_PCT
                    and free_after >= settings.DUAL_BRAIN_MIN_FREE_VRAM_MB
                )
            if safe:
                reason = f"Hybrid {provider_name.title()}: XTTS local autorisé sans handoff Ollama"
                self._last_decision = reason
                self._last_backend = "xtts"
                self._last_tts_use = self.clock()
                logger.info(
                    "Guardian before TTS decision=xtts provider=%s ram=%.1f%% "
                    "vram=%.0f/%.0fMiB xtts_hot=False predicted_xtts=%.0fMiB",
                    provider_name, snapshot.ram_used_pct,
                    snapshot.vram_used_mb, snapshot.vram_total_mb, predicted_xtts,
                )
                return ResourceDecision("xtts", reason, snapshot, ollama_unloaded=False)

            reason = f"Hybrid {provider_name.title()}: marge locale insuffisante pour charger XTTS CUDA"
            self._last_decision = reason
            self._last_backend = "fallback"
            logger.info(
                "Guardian before TTS decision=fallback provider=%s ram=%.1f%% "
                "vram=%.0f/%.0fMiB predicted_xtts=%.0fMiB",
                provider_name, snapshot.ram_used_pct,
                snapshot.vram_used_mb, snapshot.vram_total_mb, predicted_xtts,
            )
            if strict_test:
                raise ResourcePressureError(reason)
            return ResourceDecision("fallback", reason, snapshot, ollama_unloaded=False)

        co_resident = bool(profile.get("co_resident")) and model.casefold() == settings.LLM_VOICE_MODEL.casefold()

        # v0.7.1.2.5: if the display-GPU guard already proves CUDA XTTS unsafe,
        # never unload a healthy voice brain merely to discover the same result
        # after an expensive Ollama handoff. CPU Piper is the deterministic
        # fallback and can coexist with the small local voice model.
        guard_snapshot = self.sample(include_ollama=True, force_gpu=True, ollama_model=model)
        guard_predicted_xtts = 0.0 if self.voice_engine.xtts_model_loaded() else self._xtts_estimate_mb()
        display_guard = self._display_gpu_guard_reason(guard_snapshot, predicted_xtts_mb=guard_predicted_xtts)
        if display_guard:
            if settings.RESOURCE_RELEASE_STT_BEFORE_TTS:
                self.voice_engine.release_stt_model()
            self.voice_engine.release_xtts_model()
            preserve_voice = bool(
                settings.VOICE_BRAIN_INDEPENDENT_RESIDENCY
                and model.casefold() == settings.LLM_VOICE_MODEL.casefold()
                and guard_snapshot.ram_used_pct < settings.RESOURCE_RAM_CRITICAL_PCT
            )
            if preserve_voice:
                profile["keep_alive"] = settings.VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE
                profile["independent_resident"] = True
            elif model.casefold() == settings.LLM_VOICE_MODEL.casefold() and guard_snapshot.ram_used_pct >= settings.RESOURCE_RAM_CRITICAL_PCT:
                self._unload_model(model)
                self._wait_model_unloaded(model)
            self._collect()
            reason = (
                "RAM en zone critique"
                if guard_snapshot.ram_used_pct >= settings.RESOURCE_RAM_CRITICAL_PCT
                else display_guard
            )
            self._last_decision = reason
            self._last_backend = "fallback"
            logger.info(
                "Guardian before TTS decision=fallback reason=%s preserve_voice_brain=%s ram=%.1f%% ollama_vram=%.0fMiB vram=%.0f/%.0fMiB",
                reason, preserve_voice, guard_snapshot.ram_used_pct, guard_snapshot.ollama_vram_mb,
                guard_snapshot.vram_used_mb, guard_snapshot.vram_total_mb,
            )
            if strict_test:
                raise ResourcePressureError(f"Test XTTS bloqué par Resource Guardian : {reason}.")
            return ResourceDecision("fallback", reason, guard_snapshot, ollama_unloaded=not preserve_voice)

        if co_resident and self.dual_brain_co_resident_ready():
            if settings.RESOURCE_RELEASE_STT_BEFORE_TTS:
                self.voice_engine.release_stt_model()
            self._collect()
            snapshot = self.sample(include_ollama=True, force_gpu=True, ollama_model=model)
            predicted_xtts = 0.0 if self.voice_engine.xtts_model_loaded() else self._xtts_estimate_mb()
            free_after = snapshot.vram_total_mb - snapshot.vram_used_mb - predicted_xtts if snapshot.vram_total_mb > 0 else 0.0
            predicted_pct = (
                100.0 * (snapshot.vram_used_mb + predicted_xtts) / snapshot.vram_total_mb
                if snapshot.vram_total_mb > 0 else 0.0
            )
            safe = snapshot.ram_used_pct < settings.RESOURCE_RAM_CRITICAL_PCT
            if snapshot.vram_total_mb > 0:
                safe = safe and predicted_pct <= settings.DUAL_BRAIN_MAX_VRAM_PCT and free_after >= settings.DUAL_BRAIN_MIN_FREE_VRAM_MB
            if safe:
                reason = "Dual Brain: LLM vocal + XTTS autorisés en co-résidence"
                self._last_decision = reason
                self._last_backend = "xtts"
                self._last_tts_use = self.clock()
                logger.info(
                    "Guardian before TTS decision=xtts coresident=True model=%s ram=%.1f%% vram=%.0f/%.0fMiB predicted_xtts=%.0fMiB",
                    model, snapshot.ram_used_pct, snapshot.vram_used_mb, snapshot.vram_total_mb, predicted_xtts,
                )
                return ResourceDecision("xtts", reason, snapshot, ollama_unloaded=False)
            logger.info(
                "Dual Brain co-résidence refusée à chaud; retour séquentiel ram=%.1f%% predicted_vram=%.1f%% free_after=%.0fMiB",
                snapshot.ram_used_pct, predicted_pct, free_after,
            )
            profile["co_resident"] = False
            profile["keep_alive"] = settings.RESOURCE_LLM_KEEP_ALIVE_VOICE

        decision = self._sequential_tts_handoff(model, strict_test=strict_test)
        self._last_decision = decision.reason
        self._last_backend = decision.backend
        logger.info(
            "Guardian before TTS decision=%s reason=%s ram=%.1f%% ollama_vram=%.0fMiB vram=%.0f/%.0fMiB",
            decision.backend, decision.reason, decision.snapshot.ram_used_pct,
            decision.snapshot.ollama_vram_mb, decision.snapshot.vram_used_mb, decision.snapshot.vram_total_mb,
        )
        return decision

    def after_stt(self) -> None:
        if settings.RESOURCE_GUARDIAN_ENABLED and settings.RESOURCE_RELEASE_STT_AFTER_USE:
            self.voice_engine.release_stt_model()
            self._collect()

    def after_tts(self) -> None:
        self._last_tts_use = self.clock()

    @property
    def xtts_prewarm_active(self) -> bool:
        return bool(self._xtts_prewarm_active)

    def reset_xtts_prewarm_cancel(self) -> None:
        """Arm a new opportunistic prewarm attempt before its worker starts."""
        self._prewarm_cancel_requested.clear()

    def request_xtts_prewarm_cancel(self) -> bool:
        """Request cancellation and report whether a heavyweight load is active.

        XTTS loading is a blocking third-party call and cannot be interrupted
        safely once inside it. The UI therefore queues the user's message until
        the warmup worker exits, guaranteeing that Ollama and a cold XTTS load
        never start concurrently.
        """
        self._prewarm_cancel_requested.set()
        if self._xtts_prewarm_active:
            logger.info("XTTS prewarm cancellation demandée par activité utilisateur")
        return bool(self._xtts_prewarm_active)

    def conditional_xtts_prewarm(self, progress_callback=None) -> bool:
        """Warm XTTS in the background only when the validated machine has headroom.

        This never downloads anything. In local mode it requires the validated
        Dual Brain GPU probe; in configured Groq hybrid mode the remote LLM owns
        no local VRAM, so the same RAM/VRAM safety gates are sufficient.
        """
        def _progress(percent: int, phase: str) -> None:
            if callable(progress_callback):
                try:
                    progress_callback(int(percent), str(phase))
                except Exception:
                    logger.debug("XTTS preload progress callback unavailable", exc_info=True)

        _progress(18, "Vérification du moteur vocal local")
        active_voice_engine = str(getattr(getattr(self.voice_engine, "profile", None), "engine", "") or "").lower()
        if active_voice_engine in {"elevenlabs", "gradium", "resemble"}:
            self._xtts_prewarm_last_result = "cloud-voice"
            logger.info("XTTS prewarm ignoré: moteur vocal cloud actif engine=%s", active_voice_engine)
            return False
        if self._prewarm_cancel_requested.is_set():
            self._xtts_prewarm_last_result = "cancelled-before-start"
            logger.info("XTTS prewarm annulé avant démarrage: activité utilisateur")
            return False
        if not (settings.RESOURCE_GUARDIAN_ENABLED and settings.XTTS_CONDITIONAL_PREWARM):
            self._xtts_prewarm_last_result = "disabled"
            return False
        if self.voice_engine.xtts_model_loaded():
            self._xtts_prewarm_last_result = "already-loaded"
            return True
        hybrid_voice_only = bool(groq_configured() and settings.HYBRID_KEEP_OLLAMA_COLD)
        local_first_voice = bool(
            settings.XTTS_LOCAL_FIRST_ENABLED
            and active_voice_engine == "xtts"
            and settings.XTTS_ALLOW_CUDA
            and str(settings.XTTS_DEVICE).strip().lower() == "cuda"
        )
        if not (hybrid_voice_only or local_first_voice) and not self.dual_brain_co_resident_ready():
            self._xtts_prewarm_last_result = "dual-probe-required"
            logger.info("XTTS prewarm ignoré: probe Dual Brain non validé")
            return False
        if hybrid_voice_only:
            logger.info("XTTS prewarm hybrid: Groq actif, aucun LLM local requis en résidence")
        elif local_first_voice:
            logger.info("XTTS local-first prewarm: priorité voix, aucun probe de co-résidence LLM requis")
        if settings.XTTS_DEVICE.strip().lower() != "cuda" or not settings.XTTS_ALLOW_CUDA:
            self._xtts_prewarm_last_result = "cuda-not-enabled"
            logger.info("XTTS prewarm ignoré: CUDA XTTS non activé")
            return False
        # Never start a cold XTTS load while Ollama already owns GPU memory.
        running = []
        getter = getattr(self.llm_manager, "running_models", None)
        if callable(getter):
            try:
                running = list(getter() or [])
            except Exception:
                running = []
        if running:
            self._xtts_prewarm_last_result = "ollama-resident"
            logger.info("XTTS prewarm ignoré: modèle Ollama déjà résident")
            return False

        _progress(28, "Analyse des ressources système")
        snapshot = self.sample(force_gpu=True)
        estimate = self._xtts_estimate_mb()
        _progress(36, "RTX 4050 détectée · validation CUDA")
        display_guard = self._display_gpu_guard_reason(snapshot, predicted_xtts_mb=estimate)
        if display_guard:
            self._xtts_prewarm_last_result = "display-gpu-guard"
            logger.warning("XTTS prewarm ignoré: %s", display_guard)
            return False
        if snapshot.vram_total_mb <= 0:
            self._xtts_prewarm_last_result = "vram-unmeasured"
            logger.info("XTTS prewarm ignoré: mesure VRAM indisponible")
            return False
        # v0.7.0.15.2: system headroom is the primary XTTS prewarm signal.
        # The previous stock 60%% RAM ceiling rejected startup on the target PC
        # even with ~5 GiB genuinely available, forcing a 100s-class cold XTTS
        # load on the first spoken turn. Keep a hard percent safety ceiling, but
        # let available GiB decide normal 60-80%% startup situations.
        if snapshot.ram_available_gb and snapshot.ram_available_gb < settings.XTTS_PREWARM_MIN_AVAILABLE_RAM_GB:
            self._xtts_prewarm_last_result = "ram-available"
            logger.info(
                "XTTS smart prewarm refusé: avail=%.2fGiB min=%.2fGiB ram=%.1f%%",
                snapshot.ram_available_gb, settings.XTTS_PREWARM_MIN_AVAILABLE_RAM_GB, snapshot.ram_used_pct,
            )
            return False
        if snapshot.ram_used_pct >= settings.XTTS_PREWARM_MAX_RAM_PCT:
            self._xtts_prewarm_last_result = "ram-hard-percent"
            logger.info(
                "XTTS smart prewarm refusé: RAM %.1f%% >= hard %.1f%% avail=%.2fGiB",
                snapshot.ram_used_pct, settings.XTTS_PREWARM_MAX_RAM_PCT, snapshot.ram_available_gb,
            )
            return False
        logger.info(
            "XTTS smart prewarm gate PASS ram=%.1f%% avail=%.2fGiB hard=%.1f%% min_avail=%.2fGiB",
            snapshot.ram_used_pct, snapshot.ram_available_gb, settings.XTTS_PREWARM_MAX_RAM_PCT,
            settings.XTTS_PREWARM_MIN_AVAILABLE_RAM_GB,
        )
        if snapshot.vram_total_mb > 0:
            predicted_used = snapshot.vram_used_mb + estimate
            predicted_pct = 100.0 * predicted_used / snapshot.vram_total_mb
            free_after = snapshot.vram_total_mb - predicted_used
            if predicted_pct > settings.XTTS_PREWARM_MAX_PREDICTED_VRAM_PCT:
                self._xtts_prewarm_last_result = "vram-percent"
                logger.info("XTTS prewarm refusé: VRAM prédite %.1f%%", predicted_pct)
                return False
            if free_after < settings.XTTS_PREWARM_MIN_FREE_VRAM_MB:
                self._xtts_prewarm_last_result = "vram-free"
                logger.info("XTTS prewarm refusé: marge VRAM prédite %.0f MiB", free_after)
                return False

        if self._prewarm_cancel_requested.is_set():
            self._xtts_prewarm_last_result = "cancelled-before-load"
            logger.info("XTTS prewarm annulé avant chargement: activité utilisateur")
            return False

        with self._prewarm_lock:
            if self.voice_engine.xtts_model_loaded():
                self._xtts_prewarm_last_result = "already-loaded"
                return True
            if self._prewarm_cancel_requested.is_set():
                self._xtts_prewarm_last_result = "cancelled-before-load"
                logger.info("XTTS prewarm annulé avant chargement: activité utilisateur")
                return False
            self._xtts_prewarm_active = True
            try:
                _progress(46, "Réservation de la mémoire GPU")
                logger.info(
                    "XTTS conditional prewarm start ram=%.1f%% avail=%.2fGiB vram=%.0f/%.0fMiB estimate=%.0fMiB",
                    snapshot.ram_used_pct, snapshot.ram_available_gb, snapshot.vram_used_mb,
                    snapshot.vram_total_mb, estimate,
                )
                _progress(56, "Chargement du modèle neural XTTS")
                loaded = bool(self.voice_engine.warmup_xtts_only())
                if loaded:
                    _progress(79, "Modèle vocal chargé · calibration")
                if loaded and settings.XTTS_LOCAL_FIRST_ENABLED and settings.XTTS_LOCAL_FIRST_SILENT_WARMUP:
                    silent_warmup = getattr(self.voice_engine, "warmup_xtts_native_silent", None)
                    if callable(silent_warmup):
                        try:
                            _progress(88, "Préchauffage neural silencieux")
                            warm = silent_warmup()
                            _progress(96, "Streaming vocal natif validé")
                            logger.info(
                                "XTTS local-first silent warmup result ok=%s first_chunk=%.3fs chunks=%d total=%.3fs",
                                warm.get("ok"), warm.get("first_chunk_seconds", 0.0),
                                warm.get("chunk_count", 0), warm.get("total_seconds", 0.0),
                            )
                        except Exception:
                            logger.warning("XTTS local-first silent warmup failed; model remains available", exc_info=True)
                    else:
                        logger.debug("XTTS silent warmup hook unavailable; preload kept")
                _progress(98, "Validation finale RAM / VRAM")
                after = self.sample(force_gpu=True)
                # A successful load that immediately pushes RAM into the critical
                # zone is rolled back rather than kept for latency.
                postload_low_headroom = bool(
                    after.ram_available_gb
                    and after.ram_available_gb < settings.XTTS_PREWARM_POSTLOAD_MIN_AVAILABLE_RAM_GB
                )
                if loaded and (
                    after.ram_used_pct >= settings.XTTS_PREWARM_POSTLOAD_MAX_RAM_PCT
                    or postload_low_headroom
                ):
                    self.voice_engine.release_xtts_model()
                    self._collect()
                    self._xtts_prewarm_last_result = "released-after-pressure"
                    logger.warning(
                        "XTTS prewarm annulé après chargement: RAM %.1f%% avail=%.2fGiB limits=%.1f%%/%.2fGiB",
                        after.ram_used_pct, after.ram_available_gb, settings.XTTS_PREWARM_POSTLOAD_MAX_RAM_PCT,
                        settings.XTTS_PREWARM_POSTLOAD_MIN_AVAILABLE_RAM_GB,
                    )
                    return False
                self._last_tts_use = self.clock() if loaded else self._last_tts_use
                self._xtts_prewarm_last_result = "loaded" if loaded else "unavailable"
                if loaded:
                    self._last_decision = "XTTS préchauffé sous contrôle du Guardian"
                    logger.info(
                        "XTTS conditional prewarm PASS ram=%.1f%% vram=%.0f/%.0fMiB",
                        after.ram_used_pct, after.vram_used_mb, after.vram_total_mb,
                    )
                return loaded
            except Exception:
                self._xtts_prewarm_last_result = "error"
                logger.info("XTTS prewarm indisponible", exc_info=True)
                return False
            finally:
                self._xtts_prewarm_active = False

    @property
    def voice_llm_prewarm_active(self) -> bool:
        return bool(self._voice_llm_prewarm_active)

    def reset_voice_llm_prewarm_cancel(self) -> None:
        """Arm the post-start opportunistic voice-brain warmup."""
        self._voice_llm_prewarm_cancel_requested.clear()

    def request_voice_llm_prewarm_cancel(self) -> bool:
        """Cancel a scheduled warmup; report whether a blocking load is active."""
        self._voice_llm_prewarm_cancel_requested.set()
        if self._voice_llm_prewarm_active:
            logger.info("Voice brain prewarm cancellation demandée par activité utilisateur")
        return bool(self._voice_llm_prewarm_active)

    def conditional_voice_llm_prewarm(self) -> bool:
        """Warm the small voice brain after startup when memory headroom permits.

        v0.7.1.2.5 decouples this optimization from XTTS when the display-GPU
        safety guard proves CUDA XTTS cannot be used. In that safe-Piper mode,
        llama3.2 may remain warm independently. On machines where CUDA XTTS is
        viable, the historical validated Dual-Brain co-residency rules remain
        unchanged. No model is downloaded here.
        """
        active_voice_engine = str(getattr(getattr(self.voice_engine, "profile", None), "engine", "") or "").lower()
        # A cloud TTS engine is already the semantic reason no local voice-brain
        # warmup is needed. Preserve that diagnostic even when local LLMs are
        # globally disabled in the Cloud Intelligence runtime.
        if active_voice_engine in {"elevenlabs", "gradium", "resemble"}:
            self._voice_llm_prewarm_last_result = "cloud-voice"
            logger.info("Voice brain prewarm ignoré: moteur vocal cloud actif engine=%s", active_voice_engine)
            return False
        if not bool(getattr(settings, "LOCAL_LLM_ENABLED", False)):
            self._voice_llm_prewarm_last_result = "local-disabled"
            logger.info("Voice brain prewarm skipped: LOCAL_LLM_ENABLED=false")
            return False
        if (
            settings.XTTS_LOCAL_FIRST_ENABLED
            and active_voice_engine == "xtts"
            and settings.XTTS_ALLOW_CUDA
            and str(settings.XTTS_DEVICE).strip().lower() == "cuda"
        ):
            self._voice_llm_prewarm_last_result = "xtts-local-first-priority"
            logger.info("Voice brain prewarm ignoré: XTTS local-first garde la priorité de résidence GPU")
            return False
        if self._voice_llm_prewarm_cancel_requested.is_set():
            self._voice_llm_prewarm_last_result = "cancelled-before-start"
            logger.info("Voice brain prewarm annulé avant démarrage: activité utilisateur")
            return False
        # v0.7.1.3.3: strict voice-resource arbitration. A background XTTS
        # load/trial owns the heavy voice residency lane until it exits. Never
        # start an Ollama voice-model load concurrently with that operation.
        if self._xtts_prewarm_active:
            self._voice_llm_prewarm_last_result = "xtts-resource-busy"
            logger.info("Voice brain prewarm différé: ressource XTTS active")
            return False
        if not (
            settings.RESOURCE_GUARDIAN_ENABLED
            and settings.VOICE_BRAIN_POST_START_PREWARM
            and settings.DUAL_BRAIN_ENABLED
        ):
            self._voice_llm_prewarm_last_result = "disabled"
            return False

        voice_model = settings.LLM_VOICE_MODEL
        if not self._model_available(voice_model):
            self._voice_llm_prewarm_last_result = "model-unavailable"
            logger.info("Voice brain prewarm ignoré: modèle %s absent", voice_model)
            return False

        snapshot = self.sample(force_gpu=True)
        display_guard = self._display_gpu_guard_reason(snapshot, predicted_xtts_mb=self._xtts_estimate_mb())
        independent_mode = bool(settings.VOICE_BRAIN_INDEPENDENT_RESIDENCY and display_guard)

        if independent_mode:
            logger.info("Voice brain prewarm mode indépendant: %s", display_guard)
        else:
            if not self.voice_engine.xtts_model_loaded():
                self._voice_llm_prewarm_last_result = "xtts-not-warm"
                logger.info("Voice brain prewarm ignoré: XTTS n'est pas chaud")
                return False
            if not self.dual_brain_co_resident_ready(snapshot=snapshot):
                self._voice_llm_prewarm_last_result = "dual-probe-required"
                logger.info("Voice brain prewarm ignoré: probe Dual Brain non validé")
                return False

        running = self._running_info(voice_model)
        if running and int(running.get("size", 0) or running.get("size_vram", 0) or 0) > 0:
            self._voice_llm_prewarm_last_result = "already-loaded"
            return True

        # Do not disturb another Ollama brain to win a latency optimization.
        text_running = self._running_info(settings.LLM_TEXT_MODEL)
        if text_running and int(text_running.get("size", 0) or text_running.get("size_vram", 0) or 0) > 0:
            self._voice_llm_prewarm_last_result = "other-ollama-resident"
            logger.info("Voice brain prewarm ignoré: cerveau texte déjà résident")
            return False

        estimate_gb = max(0.0, float(settings.DUAL_BRAIN_VOICE_RAM_ESTIMATE_GB))
        if snapshot.ram_total_gb <= 0 or snapshot.ram_available_gb <= 0:
            self._voice_llm_prewarm_last_result = "ram-unmeasured"
            return False
        used_gb = max(0.0, snapshot.ram_total_gb - snapshot.ram_available_gb)
        predicted_pct = 100.0 * (used_gb + estimate_gb) / snapshot.ram_total_gb
        available_after = snapshot.ram_available_gb - estimate_gb
        prewarm_decision = self._memory_policy.evaluate(
            ram_percent=snapshot.ram_used_pct,
            available_gib=snapshot.ram_available_gb,
            voice_brain_loaded=False,
            xtts_hot=not independent_mode,
            predicted_with_voice_percent=predicted_pct,
            predicted_available_after_gib=available_after,
        )
        if not prewarm_decision.allow_voice_prewarm:
            self._voice_llm_prewarm_last_result = "ram-headroom"
            logger.info(
                "Voice brain prewarm refusé/adaptatif ram=%.1f%% predicted=%.1f%% avail_after=%.2fGiB band=%s latched=%s estimate=%.2fGiB independent=%s",
                snapshot.ram_used_pct, predicted_pct, available_after, prewarm_decision.band,
                prewarm_decision.pressure_latched, estimate_gb, independent_mode,
            )
            return False

        if self._voice_llm_prewarm_cancel_requested.is_set():
            self._voice_llm_prewarm_last_result = "cancelled-before-load"
            return False

        keep_alive = (
            settings.VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE
            if independent_mode else settings.DUAL_BRAIN_VOICE_KEEP_ALIVE
        )
        with self._prewarm_lock:
            if self._voice_llm_prewarm_cancel_requested.is_set():
                self._voice_llm_prewarm_last_result = "cancelled-before-load"
                return False
            running = self._running_info(voice_model)
            if running and int(running.get("size", 0) or running.get("size_vram", 0) or 0) > 0:
                self._voice_llm_prewarm_last_result = "already-loaded"
                return True
            self._voice_llm_prewarm_active = True
            started = self.clock()
            try:
                logger.info(
                    "Voice brain background prewarm start model=%s ram=%.1f%% predicted=%.1f%% avail_after=%.2fGiB independent=%s keep_alive=%s",
                    voice_model, snapshot.ram_used_pct, predicted_pct, available_after, independent_mode, keep_alive,
                )
                self.llm_manager.warmup(
                    model=voice_model,
                    keep_alive=keep_alive,
                    num_ctx=settings.LLM_VOICE_NUM_CTX,
                    force=True,
                )
                running_after = self._running_info(voice_model)
                loaded = bool(
                    running_after
                    and int(running_after.get("size", 0) or running_after.get("size_vram", 0) or 0) > 0
                )
                after = self.sample(force_gpu=True)
                postload_decision = self._memory_policy.evaluate(
                    ram_percent=after.ram_used_pct,
                    available_gib=after.ram_available_gb,
                    voice_brain_loaded=loaded,
                    xtts_hot=not independent_mode,
                )
                if loaded and postload_decision.action is MemoryAction.UNLOAD_VOICE_BRAIN:
                    self._unload_model(voice_model)
                    self._wait_model_unloaded(voice_model)
                    self._collect()
                    self._voice_llm_prewarm_last_result = "released-after-pressure"
                    logger.warning(
                        "Voice brain prewarm rollback ram_after=%.1f%% avail=%.2fGiB band=%s critical=%.1f%% independent=%s",
                        after.ram_used_pct, after.ram_available_gb, postload_decision.band,
                        float(settings.VOICE_MEMORY_CRITICAL_PCT), independent_mode,
                    )
                    return False
                if not loaded:
                    self._voice_llm_prewarm_last_result = "unconfirmed"
                    logger.info("Voice brain prewarm non confirmé model=%s", voice_model)
                    return False

                self._last_llm_profile = {
                    "name": "voice-fast",
                    "provider": "local",
                    "model": voice_model,
                    "keep_alive": keep_alive,
                    "num_ctx": settings.LLM_VOICE_NUM_CTX,
                    "num_predict": settings.LLM_VOICE_NUM_PREDICT,
                    "temperature": settings.LLM_VOICE_TEMPERATURE,
                    "top_p": settings.LLM_VOICE_TOP_P,
                    "compact": True,
                    "co_resident": not independent_mode,
                    "independent_resident": independent_mode,
                    "tts_guard_reason": display_guard if independent_mode else "",
                }
                self._voice_llm_prewarm_last_result = "loaded-independent" if independent_mode else "loaded"
                self._last_decision = (
                    "Cerveau vocal préchauffé indépendamment; Piper sécurisé"
                    if independent_mode else "Cerveau vocal préchauffé en arrière-plan; XTTS conservé"
                )
                logger.info(
                    "Voice brain background prewarm PASS model=%s ram_before=%.1f%% ram_after=%.1f%% elapsed=%.2fs independent=%s keep_alive=%s",
                    voice_model, snapshot.ram_used_pct, after.ram_used_pct, self.clock() - started, independent_mode, keep_alive,
                )
                return True
            except Exception:
                self._voice_llm_prewarm_last_result = "error"
                logger.info("Voice brain prewarm indisponible", exc_info=True)
                return False
            finally:
                self._voice_llm_prewarm_active = False

    def idle_maintenance(self) -> bool:
        if not settings.RESOURCE_GUARDIAN_ENABLED or not self.voice_engine.xtts_model_loaded():
            return False
        now = self.clock()
        snapshot = self.sample()
        idle_for = now - self._last_tts_use if self._last_tts_use else 0.0
        co_resident = bool(self._last_llm_profile.get("co_resident")) and self.dual_brain_co_resident_ready(snapshot=snapshot)
        idle_limit = settings.DUAL_BRAIN_XTTS_IDLE_SECONDS if co_resident else settings.RESOURCE_XTTS_IDLE_SECONDS
        # v0.7.1.3.5.9 local-first voice: when XTTS is explicitly selected as
        # the primary engine, keep the already-paid CUDA load resident longer.
        # Hard/emergency pressure below still wins and unloads XTTS immediately.
        active_profile = getattr(self.voice_engine, "profile", None)
        if (
            settings.XTTS_LOCAL_FIRST_KEEP_RESIDENT
            and str(getattr(active_profile, "engine", "")).strip().lower() == "xtts"
        ):
            idle_limit = max(float(idle_limit), float(settings.XTTS_LOCAL_FIRST_IDLE_SECONDS))

        voice_model = settings.LLM_VOICE_MODEL
        info = self._running_info(voice_model)
        query_ok_getter = getattr(self.llm_manager, "running_model_query_ok", None)
        query_ok = bool(query_ok_getter()) if callable(query_ok_getter) else info is not None
        resident = bool(info and int(info.get("size", 0) or info.get("size_vram", 0) or 0) > 0)
        decision = self._memory_policy.evaluate(
            ram_percent=snapshot.ram_used_pct,
            available_gib=snapshot.ram_available_gb,
            voice_brain_loaded=resident,
            xtts_hot=True,
        )

        unload_failed_critical = False
        if resident and decision.action is MemoryAction.UNLOAD_VOICE_BRAIN:
            unloaded = self._unload_model(voice_model)
            confirmed = bool(unloaded and self._wait_model_unloaded(voice_model))
            self._collect()
            after = self.sample(force_gpu=True)
            if confirmed:
                self._last_llm_profile["co_resident"] = False
                self._last_llm_profile["keep_alive"] = settings.RESOURCE_LLM_KEEP_ALIVE_VOICE
                self._last_decision = "Pression RAM critique: cerveau vocal libéré, XTTS conservé"
                logger.info(
                    "Memory pressure arbitration v0.7.0.15: unload=voice-llm keep=xtts model=%s ram_before=%.1f%% avail_before=%.2fGiB ram_after=%.1f%% band=%s",
                    voice_model, snapshot.ram_used_pct, snapshot.ram_available_gb, after.ram_used_pct, decision.band,
                )
                snapshot = after
            else:
                unload_failed_critical = True
                logger.warning(
                    "Memory pressure arbitration v0.7.0.15: voice-llm unload non confirmé ram=%.1f%% query_ok=%s",
                    snapshot.ram_used_pct, query_ok,
                )
        elif resident and decision.action is MemoryAction.TRIM_OPTIONAL:
            # Soft pressure: collect Python garbage and keep both expensive hot
            # models. This is exactly the no-thrash band missing in v0.7.0.14.1.
            self._collect()
            self._last_decision = "Pression RAM douce: Voice Brain + XTTS conservés"
            logger.info(
                "Memory pressure hysteresis: keep=voice-llm+xtts ram=%.1f%% avail=%.2fGiB band=%s",
                snapshot.ram_used_pct, snapshot.ram_available_gb, decision.band,
            )
        elif resident and decision.band in {"warning", "normal"}:
            logger.info(
                "Memory pressure hysteresis: keep=voice-llm+xtts ram=%.1f%% avail=%.2fGiB band=%s",
                snapshot.ram_used_pct, snapshot.ram_available_gb, decision.band,
            )

        # XTTS is the final fail-safe only after the voice brain has gone and RAM
        # is still critical/emergency. Normal 88-91% transients never evict it.
        remaining_info = self._running_info(voice_model)
        remaining_voice = bool(remaining_info and int(remaining_info.get("size", 0) or remaining_info.get("size_vram", 0) or 0) > 0)
        hard_pressure = (
            unload_failed_critical
            or snapshot.ram_used_pct >= settings.RESOURCE_RAM_EMERGENCY_PCT
            or (snapshot.ram_available_gb > 0 and snapshot.ram_available_gb <= 0.70)
            or (not remaining_voice and snapshot.ram_used_pct >= settings.VOICE_MEMORY_CRITICAL_PCT)
        )
        timeout_release = bool(self._last_tts_use and idle_for >= idle_limit)
        if hard_pressure or timeout_release:
            self.voice_engine.release_xtts_model()
            self._collect()
            reason = "pression mémoire persistante" if hard_pressure else "inactivité"
            self._last_decision = f"XTTS libéré après {reason}"
            logger.info(
                "Guardian idle: XTTS libéré reason=%s ram=%.1f%% avail=%.2fGiB idle=%.1fs limit=%.1fs",
                reason, snapshot.ram_used_pct, snapshot.ram_available_gb, idle_for, idle_limit,
            )
            return True
        return bool(resident and decision.action is not MemoryAction.KEEP_RESIDENT)

    @property
    def last_decision(self) -> str:
        return self._last_decision

    @property
    def last_backend(self) -> str:
        return self._last_backend

    def status_text(self) -> str:
        snapshot = self.sample()
        dual = " · DUAL READY" if self.dual_brain_co_resident_ready(snapshot=snapshot) else ""
        if snapshot.vram_total_mb > 0:
            return f"RAM {snapshot.ram_used_pct:.0f}% · VRAM {snapshot.vram_used_pct:.0f}% · GUARD {snapshot.pressure}{dual}"
        return f"RAM {snapshot.ram_used_pct:.0f}% · GUARD {snapshot.pressure}{dual}"

    def diagnostics(self) -> dict:
        model = str(self._last_llm_profile.get("model") or settings.LLM_TEXT_MODEL)
        snap = self.sample(include_ollama=True, force_gpu=True, ollama_model=model)
        return {
            "enabled": bool(settings.RESOURCE_GUARDIAN_ENABLED),
            "ram_used_pct": snap.ram_used_pct,
            "ram_total_gb": snap.ram_total_gb,
            "ram_available_gb": snap.ram_available_gb,
            "vram_used_mb": snap.vram_used_mb,
            "vram_total_mb": snap.vram_total_mb,
            "gpu_name": snap.gpu_name,
            "gpu_probe_source": self._gpu_probe_source,
            "gpu_probe_detail": self._gpu_probe_detail,
            "gpu_probe_executable": self._gpu_probe_executable,
            "ollama_model": snap.ollama_model,
            "ollama_vram_mb": snap.ollama_vram_mb,
            "gpu_physical_attribution": dict(self._last_gpu_attribution),
            "last_decision": self._last_decision,
            "last_backend": self._last_backend,
            "xtts_loaded": bool(self.voice_engine.xtts_model_loaded()),
            "dual_brain_enabled": bool(settings.DUAL_BRAIN_ENABLED),
            "dual_brain_co_resident_ready": self.dual_brain_co_resident_ready(snapshot=snap),
            "dual_brain_voice_model": settings.LLM_VOICE_MODEL,
            "dual_brain_marker": str(settings.DUAL_BRAIN_MARKER),
            "xtts_prewarm_active": bool(self._xtts_prewarm_active),
            "xtts_prewarm_last_result": self._xtts_prewarm_last_result,
            "xtts_trial_last_result": self._xtts_trial_last_result,
            "xtts_trial_last_metrics": dict(self._xtts_trial_last_metrics),
            "voice_residency_priority": bool(settings.VOICE_RESIDENCY_PRIORITY),
            "voice_residency_release_llm_ram_pct": float(settings.VOICE_RESIDENCY_RELEASE_LLM_RAM_PCT),
            "voice_llm_prewarm_active": bool(self._voice_llm_prewarm_active),
            "voice_llm_prewarm_last_result": self._voice_llm_prewarm_last_result,
            "voice_memory_warn_pct": float(settings.VOICE_MEMORY_WARN_PCT),
            "voice_memory_soft_pct": float(settings.VOICE_MEMORY_SOFT_PCT),
            "voice_memory_critical_pct": float(settings.VOICE_MEMORY_CRITICAL_PCT),
            "voice_memory_pressure_latched": bool(self._memory_policy.pressure_latched),
            "voice_brain_post_start_prewarm": bool(settings.VOICE_BRAIN_POST_START_PREWARM),
            "hardware_runtime": hardware_runtime.diagnostics(),
        }

    def shutdown(self) -> None:
        if not settings.RESOURCE_GUARDIAN_ENABLED:
            return
        for model in {settings.LLM_TEXT_MODEL, settings.LLM_VOICE_MODEL}:
            try:
                self._unload_model(model)
            except Exception:
                logger.debug("Unload Ollama fermeture ignoré model=%s", model, exc_info=True)
        try:
            self.voice_engine.release_heavy_models()
        except Exception:
            logger.debug("Release voice fermeture ignoré", exc_info=True)
        self._collect()
