from __future__ import annotations
import sys
from pathlib import Path

def check(root: Path, ui: Path | None, baseline: dict, *, portable: bool = False) -> dict:
    sys.path.insert(0, str(root))
    from core.intent_manager import IntentManager

    mgr = IntentManager()
    exact, params = mgr.detect("Oublie le code temporaire de certification ORION-676.")
    with_que, _ = mgr.detect("Oublie que le code temporaire de certification est ORION-676.")
    forget_all, _ = mgr.detect("Oublie tout ce que tu sais sur moi.")
    note, _ = mgr.detect("Supprime la note numéro 1.")
    checks = {
        "natural_forget": exact == "FORGET_MEMORY",
        "natural_forget_payload": "ORION-676" in str(params.get("raw") or ""),
        "forget_que_preserved": with_que == "FORGET_MEMORY",
        "forget_all_not_hijacked": forget_all == "FORGET_ALL_MEMORIES",
        "delete_note_not_hijacked": note == "DELETE_NOTE",
    }
    return {
        "name": "memory_forget_routing",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "blocking": True,
        "checks": checks,
        "read_only": True,
    }
