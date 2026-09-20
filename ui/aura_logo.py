"""AURA vector brand geometry loader.

Patch 13 keeps the approved curved AURA geometry and renders it as the final hollow neon outline inside the orb.
The SVG in ``ui/assets/branding/aura_symbol_master.svg`` is parsed directly
into a QPainterPath.  Both the OpenGL and QPainter orb backends use the same
QWidget overlay, so there is no second hand-drawn approximation of the logo.

The master SVG intentionally uses only M/L/Q/Z commands.  Keeping the parser
small avoids a runtime dependency on QtSvg while preserving true vector
scaling on every display DPI.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

BRANDING_DIR = Path(__file__).resolve().parent / "assets" / "branding"
MASTER_SYMBOL = BRANDING_DIR / "aura_symbol_master.svg"
BOOT_SYMBOL = BRANDING_DIR / "aura_symbol_boot_reveal.svg"
NEON_SYMBOL = BRANDING_DIR / "aura_symbol_neon.svg"
SIDEBAR_BRAND = BRANDING_DIR / "aura_sidebar_master.svg"

_TOKEN_RE = re.compile(r"[MLQZmlqz]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _first_path_d(svg_path: Path) -> str:
    root = ET.parse(svg_path).getroot()
    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1] == "path" and elem.attrib.get("d"):
            return elem.attrib["d"]
    raise ValueError(f"Aucun path vectoriel dans {svg_path}")


def _path_from_d(data: str) -> QPainterPath:
    tokens = _TOKEN_RE.findall(data.replace(",", " "))
    path = QPainterPath()
    i = 0
    command = ""
    current_x = 0.0
    current_y = 0.0
    start_x = 0.0
    start_y = 0.0

    def number() -> float:
        nonlocal i
        if i >= len(tokens):
            raise ValueError("Path SVG tronqué")
        value = float(tokens[i])
        i += 1
        return value

    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            command = token
            i += 1
        if not command:
            raise ValueError("Commande SVG manquante")

        relative = command.islower()
        upper = command.upper()
        if upper == "Z":
            path.closeSubpath()
            current_x, current_y = start_x, start_y
            command = ""
            continue

        if upper in {"M", "L"}:
            x, y = number(), number()
            if relative:
                x += current_x
                y += current_y
            if upper == "M":
                path.moveTo(x, y)
                start_x, start_y = x, y
                # Subsequent coordinate pairs after M are implicit L in SVG.
                command = "l" if relative else "L"
            else:
                path.lineTo(x, y)
            current_x, current_y = x, y
            continue

        if upper == "Q":
            cx, cy, x, y = number(), number(), number(), number()
            if relative:
                cx += current_x
                cy += current_y
                x += current_x
                y += current_y
            path.quadTo(cx, cy, x, y)
            current_x, current_y = x, y
            continue

        raise ValueError(f"Commande SVG non supportée dans le logo AURA: {command}")
    return path


@lru_cache(maxsize=1)
def master_symbol_path() -> QPainterPath:
    """Return the immutable master AURA geometry in its 1000×1000 artboard."""
    return _path_from_d(_first_path_d(MASTER_SYMBOL))


@lru_cache(maxsize=1)
def master_symbol_bounds() -> QRectF:
    return QRectF(master_symbol_path().boundingRect())


def branding_asset_health() -> dict[str, bool]:
    """Lightweight diagnostic used by the patch verification script."""
    return {
        "master": MASTER_SYMBOL.is_file(),
        "boot": BOOT_SYMBOL.is_file(),
        "neon": NEON_SYMBOL.is_file(),
        "sidebar": SIDEBAR_BRAND.is_file(),
    }
