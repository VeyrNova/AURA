
from __future__ import annotations

from pathlib import Path
import re

def detect_command_prefix(text: str) -> dict:
    raw=text.strip()
    prefixes=("git ","pytest","python ","py ","npm ","pnpm ","yarn ","cargo ","go ","dotnet ","docker ","kubectl ","powershell ","cmd ")
    low=raw.lower()
    match=next((p.strip() for p in prefixes if low.startswith(p)),None)
    return {"matched":match is not None,"prefix":match,"provider_called":False}

def session_title(text: str, max_len: int=60) -> dict:
    one=" ".join(text.strip().split())
    one=re.sub(r"(?i)\b(sk-[A-Za-z0-9_-]+|bearer\s+\S+)\b","<redacted>",one)
    title=one[:max_len].rstrip()
    return {"title":title or "AURA Developer Session","provider_called":False}

def normalize_filepath(value: str, workspace: str | Path | None=None) -> dict:
    p=Path(value).expanduser()
    if workspace is not None:
        try: normalized=str(p.resolve().relative_to(Path(workspace).resolve()))
        except Exception: normalized=str(p.resolve())
    else:
        normalized=str(p)
    return {"path":normalized,"provider_called":False}

def suggest_next_action(command: str, exit_code: int, output: str="") -> dict:
    low=(output or "").lower()
    if exit_code==0:
        suggestion="review_diff" if command.strip().startswith("git") else "continue"
    elif "permission" in low or "access is denied" in low:
        suggestion="check_permissions"
    elif "not found" in low or "not recognized" in low:
        suggestion="check_dependency_or_path"
    elif "test" in command.lower() or "assert" in low or "failed" in low:
        suggestion="inspect_failing_test"
    else:
        suggestion="inspect_error"
    return {"suggestion":suggestion,"provider_called":False}

def quota_probe_local(summary: dict) -> dict:
    return {
        "reference_headline_tokens_per_month":summary.get("reference_headline_tokens_per_month"),
        "known_token_equivalent_reference_floor_per_month":summary.get("known_token_equivalent_reference_floor_per_month"),
        "stale":summary.get("reference_headline_stale"),
        "provider_called":False,
    }

def capability_snapshot() -> dict:
    return {
        "schema":"aura.fabric.local-optimizations.v1",
        "provider_called":False,
        "optimizations":[
            "quota_probe_local",
            "command_prefix_detection",
            "session_title",
            "suggest_next_action",
            "filepath_normalization",
        ],
    }
