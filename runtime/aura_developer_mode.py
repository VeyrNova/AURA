
from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import os
import re
import time
import unicodedata

DEFAULT_ROOT = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1])
MAX_SPOKEN_SUMMARY_CHARS = 150

ACTIVATE_PHRASES = (
    "active le mode developpeur",
    "active mode developpeur",
    "passe en mode developpeur",
    "lance le mode developpeur",
    "mode developpeur on",
    "enable developer mode",
    "developer mode on",
)
DEACTIVATE_PHRASES = (
    "desactive le mode developpeur",
    "desactive mode developpeur",
    "quitte le mode developpeur",
    "sors du mode developpeur",
    "repasse en mode normal",
    "mode developpeur off",
    "disable developer mode",
    "developer mode off",
)

def _root(root: Path | str | None = None) -> Path:
    return Path(root or DEFAULT_ROOT).resolve()

def state_path(root: Path | str | None = None) -> Path:
    return _root(root) / "runtime" / "developer_fabric" / "developer_mode_state.json"

def _normalize_phrase(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def _default_state() -> dict[str, Any]:
    return {
        "schema": "aura.developer-mode-state.v1",
        "enabled": False,
        "updated_at": None,
        "source": "default",
        "last_command": None,
        "voice_confirmation": "Mode développeur désactivé.",
    }

def state_snapshot(root: Path | str | None = None) -> dict[str, Any]:
    path = state_path(root)
    if not path.exists():
        return _default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_state()
    state = _default_state()
    state.update({k: v for k, v in raw.items() if k in state})
    state["enabled"] = bool(state["enabled"])
    return state

def developer_mode_enabled(root: Path | str | None = None) -> bool:
    return bool(state_snapshot(root).get("enabled"))

def set_developer_mode(
    enabled: bool,
    *,
    source: str = "text",
    command: str | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    confirmation = "Mode développeur activé." if enabled else "Mode développeur désactivé."
    state = {
        "schema": "aura.developer-mode-state.v1",
        "enabled": bool(enabled),
        "updated_at": int(time.time()),
        "source": str(source),
        "last_command": str(command)[:240] if command else None,
        "voice_confirmation": confirmation,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return state

def handle_developer_mode_command(
    text: str,
    *,
    channel: str = "text",
    root: Path | str | None = None,
) -> dict[str, Any]:
    normalized = _normalize_phrase(text)
    action = None
    # Deactivation is tested first so "désactive" can never be confused
    # with the substring "active".
    if any(phrase in normalized for phrase in DEACTIVATE_PHRASES):
        action = False
    elif any(phrase in normalized for phrase in ACTIVATE_PHRASES):
        action = True

    if action is None:
        return {
            "schema": "aura.developer-mode-command.v1",
            "recognized": False,
            "enabled": developer_mode_enabled(root),
            "channel": channel,
            "speak": None,
        }

    state = set_developer_mode(action, source=channel, command=text, root=root)
    return {
        "schema": "aura.developer-mode-command.v1",
        "recognized": True,
        "enabled": state["enabled"],
        "channel": channel,
        "speak": state["voice_confirmation"],
    }

def brief_change_summary(proposal: dict[str, Any], *, outcome: str = "applied") -> str:
    edits = proposal.get("edits") or []
    names = [Path(str(edit.get("path") or "")).name for edit in edits if edit.get("path")]
    if outcome == "rolled_back":
        text = "J’ai annulé la modification et restauré " + str(len(names)) + " fichier" + ("" if len(names) == 1 else "s") + "."
    elif not names:
        text = "Modification terminée. Les tests sont passés."
    elif len(names) == 1:
        text = f"J’ai modifié {names[0]}. Les tests sont passés."
    elif len(names) == 2:
        text = f"J’ai modifié {names[0]} et {names[1]}. Les tests sont passés."
    else:
        text = f"J’ai modifié {len(names)} fichiers. Les tests sont passés."

    if len(text) > MAX_SPOKEN_SUMMARY_CHARS:
        text = text[: MAX_SPOKEN_SUMMARY_CHARS - 1].rstrip(" ,.;:") + "…"
    return text

def capability_snapshot(root: Path | str | None = None) -> dict[str, Any]:
    return {
        "schema": "aura.developer-mode-capabilities.v1",
        "default_enabled": False,
        "current_enabled": developer_mode_enabled(root),
        "text_command_toggle": True,
        "voice_command_toggle": True,
        "activation_examples": [
            "Aura, active le mode développeur",
            "Aura, passe en mode développeur",
        ],
        "deactivation_examples": [
            "Aura, désactive le mode développeur",
            "Aura, repasse en mode normal",
        ],
        "activation_requires_write_approval": False,
        "self_development_apply_requires_mode_enabled": True,
        "brief_spoken_summary_after_apply": True,
        "spoken_summary_max_chars": MAX_SPOKEN_SUMMARY_CHARS,
        "spoken_output_policy": "brief-change-summary-only",
        "tts_contract": "ADF-H forwards speak/spoken_summary to the existing AURA TTS layer.",
    }
