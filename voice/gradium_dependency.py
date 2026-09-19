"""Safe, user-triggered installer for Gradium's optional WebSocket dependency.

This module intentionally does *not* expose arbitrary command execution.  It can
only invoke the Python interpreter currently running AURA with the fixed pip /
ensurepip commands required for the pinned ``websockets`` package.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

logger = logging.getLogger("aura.voice.gradium_dependency")

PINNED_WEBSOCKETS = "16.1.1"


@dataclass(frozen=True)
class GradiumDependencyStatus:
    ready: bool
    interpreter: str
    version: str = ""
    detail: str = ""


def _interpreter() -> str:
    return str(Path(sys.executable).resolve())


def probe_websockets() -> GradiumDependencyStatus:
    """Return the status of the dependency in AURA's *current* interpreter."""
    interpreter = _interpreter()
    try:
        module = importlib.import_module("websockets")
        importlib.import_module("websockets.sync.client")
        version = str(getattr(module, "__version__", "unknown"))
        return GradiumDependencyStatus(True, interpreter, version, "WebSocket temps réel prêt")
    except Exception as exc:
        return GradiumDependencyStatus(False, interpreter, "", f"{type(exc).__name__}: {exc}")


def _run_fixed(args: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    """Run one of our fixed interpreter commands without a shell."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    return subprocess.run(
        [*_fixed_prefix(), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
        creationflags=flags,
        check=False,
    )


def _fixed_prefix() -> list[str]:
    return [_interpreter()]


def install_websockets_for_current_aura(*, timeout: float = 120.0) -> GradiumDependencyStatus:
    """Install the pinned dependency into the exact interpreter running AURA.

    The operation is deliberately narrow and deterministic.  It never accepts a
    package name, command, shell fragment, or Python snippet from the caller.
    """
    before = probe_websockets()
    if before.ready and before.version == PINNED_WEBSOCKETS:
        return before

    interpreter = before.interpreter
    logger.info("Gradium dependency setup start interpreter=%r target=websockets==%s", interpreter, PINNED_WEBSOCKETS)

    try:
        pip_probe = _run_fixed(["-m", "pip", "--version"], timeout=min(timeout, 30.0))
    except Exception as exc:
        return GradiumDependencyStatus(False, interpreter, "", f"Impossible de lancer pip avec le Python d'AURA : {exc}")

    if pip_probe.returncode != 0:
        logger.warning("pip absent from AURA interpreter; trying ensurepip")
        try:
            ensure = _run_fixed(["-m", "ensurepip", "--upgrade"], timeout=min(timeout, 60.0))
        except Exception as exc:
            return GradiumDependencyStatus(False, interpreter, "", f"pip absent et ensurepip a échoué : {exc}")
        if ensure.returncode != 0:
            detail = (ensure.stdout or "").strip()[-600:]
            return GradiumDependencyStatus(False, interpreter, "", f"pip absent et ensurepip a échoué. {detail}")

    try:
        result = _run_fixed(
            ["-m", "pip", "install", "--disable-pip-version-check", f"websockets=={PINNED_WEBSOCKETS}"],
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return GradiumDependencyStatus(False, interpreter, "", "Installation WebSocket expirée (timeout).")
    except Exception as exc:
        return GradiumDependencyStatus(False, interpreter, "", f"Installation impossible : {exc}")

    if result.returncode != 0:
        detail = (result.stdout or "").strip()[-800:]
        logger.warning("Gradium dependency setup failed rc=%s detail=%s", result.returncode, detail)
        return GradiumDependencyStatus(False, interpreter, "", f"pip a retourné le code {result.returncode}. {detail}")

    importlib.invalidate_caches()
    # A failed import can be cached in sys.modules only if a partially imported
    # module survived. Remove those entries before the verification import.
    for name in tuple(sys.modules):
        if name == "websockets" or name.startswith("websockets."):
            sys.modules.pop(name, None)
    after = probe_websockets()
    if after.ready:
        logger.info("Gradium dependency setup PASS interpreter=%r version=%s", interpreter, after.version)
        return after
    logger.warning("Gradium dependency setup installed but import still failed: %s", after.detail)
    return GradiumDependencyStatus(False, interpreter, "", "Installation terminée mais import impossible : " + after.detail)
