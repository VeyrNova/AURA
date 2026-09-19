"""Read-only physical GPU attribution for the Ollama server.

No environment mutation, process restart, shell=True, or arbitrary command input.
The module only executes fixed diagnostic commands when available.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import io
import os
import shutil
import subprocess
from typing import Iterable


@dataclass(frozen=True)
class OllamaGpuDiagnostic:
    nvidia_smi_available: bool = False
    nvidia_gpu_name: str = ""
    nvidia_used_mb: float = 0.0
    nvidia_total_mb: float = 0.0
    nvidia_util_pct: float = 0.0
    ollama_pids: tuple[int, ...] = ()
    nvidia_compute_pids: tuple[int, ...] = ()
    ollama_on_nvidia: bool = False
    cuda_visible_devices: str = ""
    ggml_vk_visible_devices: str = ""
    ollama_vulkan: str = ""
    verdict: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


def _run_fixed(args: list[str], timeout: float = 4.0) -> str:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _parse_csv_lines(text: str) -> list[list[str]]:
    if not text.strip():
        return []
    return [row for row in csv.reader(io.StringIO(text)) if row]


def _ollama_pids_windows() -> tuple[int, ...]:
    if os.name != "nt":
        return ()
    tasklist = shutil.which("tasklist.exe") or shutil.which("tasklist")
    if not tasklist:
        return ()
    text = _run_fixed([tasklist, "/FI", "IMAGENAME eq ollama.exe", "/FO", "CSV", "/NH"])
    pids: list[int] = []
    for row in _parse_csv_lines(text):
        if len(row) < 2 or "ollama" not in row[0].casefold():
            continue
        try:
            pids.append(int(row[1]))
        except ValueError:
            continue
    return tuple(sorted(set(pids)))


def _nvidia_snapshot() -> tuple[bool, str, float, float, float, tuple[int, ...]]:
    exe = shutil.which("nvidia-smi.exe") or shutil.which("nvidia-smi")
    if not exe:
        return False, "", 0.0, 0.0, 0.0, ()
    gpu = _run_fixed([
        exe,
        "--query-gpu=name,memory.used,memory.total,utilization.gpu",
        "--format=csv,noheader,nounits",
    ])
    rows = _parse_csv_lines(gpu)
    name = ""; used = total = util = 0.0
    if rows and len(rows[0]) >= 4:
        name = rows[0][0].strip()
        try:
            used = float(rows[0][1]); total = float(rows[0][2]); util = float(rows[0][3])
        except ValueError:
            pass
    apps = _run_fixed([
        exe,
        "--query-compute-apps=pid",
        "--format=csv,noheader,nounits",
    ])
    pids: list[int] = []
    for row in _parse_csv_lines(apps):
        if not row:
            continue
        try:
            pids.append(int(row[0].strip()))
        except ValueError:
            continue
    return True, name, used, total, util, tuple(sorted(set(pids)))


def collect_ollama_gpu_diagnostic() -> OllamaGpuDiagnostic:
    available, name, used, total, util, compute_pids = _nvidia_snapshot()
    ollama_pids = _ollama_pids_windows()
    intersection = set(ollama_pids).intersection(compute_pids)
    on_nvidia = bool(intersection)
    if on_nvidia:
        verdict = "nvidia-process-confirmed"
    elif available and ollama_pids and not intersection:
        verdict = "ollama-not-seen-on-nvidia"
    elif not available:
        verdict = "nvidia-smi-unavailable"
    elif not ollama_pids:
        verdict = "ollama-process-not-found"
    else:
        verdict = "unknown"
    return OllamaGpuDiagnostic(
        nvidia_smi_available=available,
        nvidia_gpu_name=name,
        nvidia_used_mb=used,
        nvidia_total_mb=total,
        nvidia_util_pct=util,
        ollama_pids=ollama_pids,
        nvidia_compute_pids=compute_pids,
        ollama_on_nvidia=on_nvidia,
        cuda_visible_devices=os.getenv("CUDA_VISIBLE_DEVICES", ""),
        ggml_vk_visible_devices=os.getenv("GGML_VK_VISIBLE_DEVICES", ""),
        ollama_vulkan=os.getenv("OLLAMA_VULKAN", ""),
        verdict=verdict,
    )


def format_ollama_gpu_diagnostic(diag: OllamaGpuDiagnostic) -> str:
    gpu = diag.nvidia_gpu_name or "RTX/NVIDIA non détectée"
    ollama = ", ".join(map(str, diag.ollama_pids)) or "aucun"
    nvidia_pids = ", ".join(map(str, diag.nvidia_compute_pids)) or "aucun"
    return (
        f"GPU NVIDIA : {gpu}\n"
        f"VRAM NVIDIA : {diag.nvidia_used_mb:.0f}/{diag.nvidia_total_mb:.0f} MiB · utilisation {diag.nvidia_util_pct:.0f}%\n"
        f"PID Ollama : {ollama}\n"
        f"PID compute NVIDIA : {nvidia_pids}\n"
        f"Ollama vu sur NVIDIA : {'OUI' if diag.ollama_on_nvidia else 'NON'}\n"
        f"Verdict : {diag.verdict}\n"
        f"CUDA_VISIBLE_DEVICES : {diag.cuda_visible_devices or '(non défini)'}\n"
        f"GGML_VK_VISIBLE_DEVICES : {diag.ggml_vk_visible_devices or '(non défini)'}\n"
        f"OLLAMA_VULKAN : {diag.ollama_vulkan or '(non défini)'}"
    )
