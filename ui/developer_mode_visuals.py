
from __future__ import annotations
from pathlib import Path
import os

from runtime.aura_developer_mode import developer_mode_enabled
from ui.developer_mode_web_surface import apply_web_developer_mode

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel, QFrame, QLineEdit, QTextEdit, QPlainTextEdit
    PYSIDE_AVAILABLE = True
except Exception:
    PYSIDE_AVAILABLE = False
    Qt = None
    QLabel = QFrame = QLineEdit = QTextEdit = QPlainTextEdit = object

ROOT = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).resolve()
DEV_ACCENT = "#F0A23A"
DEV_ACCENT_SOFT = "rgba(240, 162, 58, 0.20)"
DEV_PANEL = "rgba(13, 16, 24, 0.94)"
DEV_PLACEHOLDER = "AURA DEV // Que veux-tu modifier ?"


def _set_transparent(widget):
    try:
        widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    except Exception:
        pass


def _repolish(widget):
    try:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
    except Exception:
        pass


def _find_composer(window):
    chat = getattr(window, "chat_panel", None)
    if chat is None or not hasattr(chat, "findChildren"):
        return None
    candidates = []
    for cls in (QLineEdit, QTextEdit, QPlainTextEdit):
        try:
            candidates.extend(chat.findChildren(cls))
        except Exception:
            pass
    ranked = []
    for widget in candidates:
        try:
            name = str(widget.objectName() or "").lower()
        except Exception:
            name = ""
        try:
            placeholder = str(widget.placeholderText() or "").lower()
        except Exception:
            placeholder = ""
        haystack = name + " " + placeholder
        score = 0
        for token in ("input", "message", "composer", "prompt", "chat", "aura", "demande", "écri", "ecri"):
            if token in haystack:
                score += 1
        if score:
            ranked.append((score, widget))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return ranked[0][1] if ranked else None


def ensure_developer_mode_visuals(window):
    if not PYSIDE_AVAILABLE or window is None:
        return {"available": False, "created": False}

    badge = getattr(window, "_aura_dev_badge", None)
    if badge is None:
        badge = QLabel("AURA // DEV", window)
        badge.setObjectName("auraDeveloperModeBadge")
        badge.setStyleSheet(
            "QLabel#auraDeveloperModeBadge {"
            "background: rgba(18, 20, 29, 235);"
            "color: #F6B85F; border: 1px solid #F0A23A;"
            "border-radius: 8px; padding: 5px 11px;"
            "font-size: 12px; font-weight: 800; letter-spacing: 1px;"
            "}"
        )
        badge.adjustSize()
        _set_transparent(badge)
        window._aura_dev_badge = badge

    status = getattr(window, "_aura_dev_status_badge", None)
    if status is None:
        status = QLabel("DEV ACTIVE · WRITE GATED · AUDIT ON", window)
        status.setObjectName("auraDeveloperModeStatus")
        status.setStyleSheet(
            "QLabel#auraDeveloperModeStatus {"
            "background: rgba(13, 16, 24, 225);"
            "color: #D9A45B; border: 1px solid rgba(240,162,58,0.40);"
            "border-radius: 7px; padding: 4px 9px;"
            "font-size: 10px; font-weight: 650;"
            "}"
        )
        status.adjustSize()
        _set_transparent(status)
        window._aura_dev_status_badge = status

    border = getattr(window, "_aura_dev_border", None)
    if border is None:
        border = QFrame(window)
        border.setObjectName("auraDeveloperModeBorder")
        border.setStyleSheet(
            "QFrame#auraDeveloperModeBorder {"
            "background: transparent; border: 2px solid rgba(240,162,58,0.72);"
            "border-radius: 10px;"
            "}"
        )
        _set_transparent(border)
        window._aura_dev_border = border

    _position_visuals(window)
    return {"available": True, "created": True}


def _position_visuals(window):
    if not PYSIDE_AVAILABLE or window is None:
        return
    try:
        badge = getattr(window, "_aura_dev_badge", None)
        status = getattr(window, "_aura_dev_status_badge", None)
        border = getattr(window, "_aura_dev_border", None)
        width = max(1, int(window.width()))
        height = max(1, int(window.height()))
        if border is not None:
            border.setGeometry(2, 2, max(1, width - 4), max(1, height - 4))
        if badge is not None:
            badge.adjustSize()
            badge.move(max(14, width - badge.width() - 22), 18)
        if status is not None:
            status.adjustSize()
            status.move(max(14, width - status.width() - 22), 18 + (badge.height() if badge is not None else 28) + 7)
        for widget in (border, badge, status):
            if widget is not None:
                widget.raise_()
    except Exception:
        pass


def _set_composer_identity(window, enabled: bool):
    composer = _find_composer(window)
    if composer is None:
        return False
    try:
        if composer.property("auraDevOriginalPlaceholder") is None:
            composer.setProperty("auraDevOriginalPlaceholder", str(composer.placeholderText() or ""))
        original = str(composer.property("auraDevOriginalPlaceholder") or "")
        composer.setPlaceholderText(DEV_PLACEHOLDER if enabled else original)
        composer.setProperty("auraDeveloperMode", bool(enabled))
        if enabled:
            composer.setStyleSheet(
                str(composer.styleSheet() or "")
                + "\nQLineEdit[auraDeveloperMode=\"true\"], QTextEdit[auraDeveloperMode=\"true\"], QPlainTextEdit[auraDeveloperMode=\"true\"] {"
                  "border: 1px solid rgba(240,162,58,0.72);"
                  "background: rgba(24,19,15,0.30);"
                "}"
            )
        _repolish(composer)
        return True
    except Exception:
        return False


def apply_developer_mode_visuals(window, enabled: bool):
    # AURA v1.3.0 visible surface is the QWebEngine/Three.js shell.
    # Apply there first; native Qt badges remain a fallback only.
    try:
        web_result = apply_web_developer_mode(window, enabled)
    except Exception:
        web_result = {"webviews_applied": 0, "webviews_found": 0}
    if not PYSIDE_AVAILABLE or window is None:
        return {"available": False, "enabled": bool(enabled), "composer": False}
    ensure_developer_mode_visuals(window)
    enabled = bool(enabled)
    try:
        window.setProperty("auraDeveloperMode", enabled)
    except Exception:
        pass

    for attr in ("_aura_dev_badge", "_aura_dev_status_badge", "_aura_dev_border"):
        widget = getattr(window, attr, None)
        if widget is not None:
            widget.setVisible(enabled)
    _position_visuals(window)

    # Expose the state to the orb if a known orb widget exists. This is a safe
    # dynamic property only; existing shaders continue to own their rendering.
    for attr in ("orb_widget", "opengl_orb", "orb", "aura_orb"):
        widget = getattr(window, attr, None)
        if widget is not None:
            try:
                widget.setProperty("auraDeveloperMode", enabled)
                _repolish(widget)
            except Exception:
                pass

    composer_changed = _set_composer_identity(window, enabled)
    return {"available": True, "enabled": enabled, "composer": composer_changed}


def sync_developer_mode_visuals(window, *, root: Path | str | None = None):
    try:
        enabled = developer_mode_enabled(root or ROOT)
    except Exception:
        enabled = False
    return apply_developer_mode_visuals(window, enabled)


def capability_snapshot():
    return {
        "schema": "aura.developer-mode-visual-capabilities.v1",
        "pyside_available": PYSIDE_AVAILABLE,
        "persistent_dev_badge": True,
        "persistent_write_gated_audit_status": True,
        "amber_window_border": True,
        "composer_identity_when_detectable": True,
        "orb_dynamic_property_when_detectable": True,
        "normal_mode_restores_clean_ui": True,
        "layout_mutation_required": False,
        "accent": "amber-electric",
    }
