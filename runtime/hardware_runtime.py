"""Read-only heterogeneous GPU diagnostics for AURA v0.7.1.3.0.

This module never changes Windows GPU preferences and never enables CUDA/XTTS.
It only correlates the active OpenGL renderer with the NVIDIA compute adapter
already measured by ResourceGuardian. Shared/system GPU memory is deliberately
excluded from the CUDA VRAM budget.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import threading

logger = logging.getLogger("aura.runtime.hardware")


@dataclass(frozen=True)
class HardwareGpuSnapshot:
    gl_vendor: str = ""
    gl_renderer: str = ""
    gl_version: str = ""
    compute_gpu: str = ""
    compute_vram_used_mb: float = 0.0
    compute_vram_total_mb: float = 0.0
    display_compute_separated: bool | None = None
    topology: str = "unknown"
    shared_memory_counted_for_cuda: bool = False


def classify_gpu_topology(gl_renderer: str, compute_gpu: str) -> tuple[bool | None, str]:
    """Classify renderer/compute separation without guessing from GPU numbering."""
    renderer = (gl_renderer or "").casefold()
    compute = (compute_gpu or "").casefold()
    if not renderer or not compute:
        return None, "unknown"
    renderer_intel = "intel" in renderer or "iris" in renderer
    renderer_nvidia = "nvidia" in renderer or "geforce" in renderer or "rtx" in renderer
    compute_nvidia = "nvidia" in compute or "geforce" in compute or "rtx" in compute
    if renderer_intel and compute_nvidia:
        return True, "intel-display+nvidia-compute"
    if renderer_nvidia and compute_nvidia:
        return False, "nvidia-shared-display+compute"
    if renderer.casefold() == compute.casefold():
        return False, "same-adapter"
    return None, "mixed-unclassified"


class HardwareRuntimeDiagnostics:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._gl_vendor = ""
        self._gl_renderer = ""
        self._gl_version = ""
        self._compute_gpu = ""
        self._compute_vram_used_mb = 0.0
        self._compute_vram_total_mb = 0.0
        self._last_logged_signature: tuple = ()

    def register_gl(self, *, vendor: str = "", renderer: str = "", version: str = "") -> HardwareGpuSnapshot:
        with self._lock:
            self._gl_vendor = str(vendor or "").strip()
            self._gl_renderer = str(renderer or "").strip()
            self._gl_version = str(version or "").strip()
            snapshot = self.snapshot()
            self._log_if_changed(snapshot)
            return snapshot

    def register_compute(self, *, name: str = "", used_mb: float = 0.0, total_mb: float = 0.0) -> HardwareGpuSnapshot:
        with self._lock:
            self._compute_gpu = str(name or "").strip()
            self._compute_vram_used_mb = max(0.0, float(used_mb or 0.0))
            self._compute_vram_total_mb = max(0.0, float(total_mb or 0.0))
            snapshot = self.snapshot()
            self._log_if_changed(snapshot)
            return snapshot

    def snapshot(self) -> HardwareGpuSnapshot:
        with self._lock:
            separated, topology = classify_gpu_topology(self._gl_renderer, self._compute_gpu)
            return HardwareGpuSnapshot(
                gl_vendor=self._gl_vendor,
                gl_renderer=self._gl_renderer,
                gl_version=self._gl_version,
                compute_gpu=self._compute_gpu,
                compute_vram_used_mb=self._compute_vram_used_mb,
                compute_vram_total_mb=self._compute_vram_total_mb,
                display_compute_separated=separated,
                topology=topology,
                shared_memory_counted_for_cuda=False,
            )

    def diagnostics(self) -> dict:
        return asdict(self.snapshot())

    def _log_if_changed(self, snapshot: HardwareGpuSnapshot) -> None:
        signature = (
            snapshot.gl_renderer,
            snapshot.compute_gpu,
            round(snapshot.compute_vram_total_mb),
            snapshot.topology,
        )
        if signature == self._last_logged_signature:
            return
        self._last_logged_signature = signature
        if snapshot.gl_renderer:
            logger.info(
                "OpenGL renderer probe vendor='%s' renderer='%s' version='%s'",
                snapshot.gl_vendor or "unknown", snapshot.gl_renderer, snapshot.gl_version or "unknown",
            )
        if snapshot.compute_gpu and snapshot.compute_vram_total_mb > 0:
            logger.info(
                "CUDA compute probe gpu='%s' dedicated_vram=%.0fMiB used=%.0fMiB shared_memory_for_cuda=ignored",
                snapshot.compute_gpu, snapshot.compute_vram_total_mb, snapshot.compute_vram_used_mb,
            )
        if snapshot.gl_renderer and snapshot.compute_gpu:
            logger.info(
                "Hybrid GPU topology=%s display_compute_separated=%s gl='%s' compute='%s'",
                snapshot.topology, snapshot.display_compute_separated,
                snapshot.gl_renderer, snapshot.compute_gpu,
            )


hardware_runtime = HardwareRuntimeDiagnostics()
