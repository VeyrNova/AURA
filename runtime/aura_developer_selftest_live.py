
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import re
import sys
import tempfile
import time
import unicodedata

ROOT = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).resolve()
STATE_DIR = ROOT / "runtime" / "developer_fabric"
STATE_FILE = STATE_DIR / "live_selftest_transaction_state.json"
TARGET_REL = "runtime/developer_fabric/selftest_dev_patch.py"
TARGET = ROOT / TARGET_REL

CREATE_TEXT = 'AURA_DEV_SELFTEST = "PASS"\n\ndef status():\n    return AURA_DEV_SELFTEST\n'

from runtime.aura_developer_mode import developer_mode_enabled
from runtime.aura_patch_transaction_engine import propose_edits, validate_in_staging
from runtime.aura_self_development_governance import (
    assess_proposal,
    apply_self_development,
    rollback_self_development,
)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.is_file():
        return {
            "schema": "aura.adf-h-r6-1.live-selftest-state.v1",
            "pending": None,
            "last_receipt": None,
            "last_rollback": None,
        }
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("schema", "aura.adf-h-r6-1.live-selftest-state.v1")
            data.setdefault("pending", None)
            data.setdefault("last_receipt", None)
            data.setdefault("last_rollback", None)
            return data
    except Exception:
        pass
    return {
        "schema": "aura.adf-h-r6-1.live-selftest-state.v1",
        "pending": None,
        "last_receipt": None,
        "last_rollback": None,
    }


def _save_state(data: dict[str, Any]) -> None:
    data["schema"] = "aura.adf-h-r6-1.live-selftest-state.v1"
    data["updated_at"] = int(time.time())
    _atomic_json(STATE_FILE, data)


def _fold(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value.lower()).strip()


def _is_target_mentioned(text: str) -> bool:
    n = _fold(text)
    return (
        "selftest_dev_patch.py" in n
        or "micro-test de developpement" in n
        or "micro test de developpement" in n
        or "micro-test developpeur" in n
        or "micro test developpeur" in n
    )


def _request_kind(text: str) -> str | None:
    n = _fold(text)
    if not _is_target_mentioned(text):
        return None
    if "pass_edited" in n or re.search(r"\b(remplace|remplacer|modifie|modifier|edit|edite)\b", n):
        return "edit"
    if re.search(r"\b(cree|creer|creation|micro-test|micro test)\b", n):
        return "create"
    return "help"


def _test_commands() -> list[list[str]]:
    return [[sys.executable, "-m", "py_compile", TARGET_REL]]


def _prepare_create(user_text: str) -> dict[str, Any]:
    proposal = propose_edits(
        ROOT,
        [{
            "path": TARGET_REL,
            "new_text": CREATE_TEXT,
            "reason": "ADF-H R6.1 live self-development micro-test creation",
        }],
        task=user_text,
    )
    validation = validate_in_staging(proposal, _test_commands())
    assessment = assess_proposal(proposal, ROOT)
    return {
        "proposal": proposal,
        "validation": validation,
        "assessment": assessment,
        "approvals_received": [],
        "operation": "create",
        "created_at": int(time.time()),
    }


def _prepare_edit(user_text: str) -> dict[str, Any]:
    if not TARGET.is_file():
        raise RuntimeError(
            "Le fichier selftest_dev_patch.py n'existe pas encore. "
            "Lance d'abord le micro-test de création."
        )
    current = TARGET.read_text(encoding="utf-8")
    if 'AURA_DEV_SELFTEST = "PASS_EDITED"' in current:
        raise RuntimeError("Le micro-test est déjà dans l'état PASS_EDITED.")
    needle = 'AURA_DEV_SELFTEST = "PASS"'
    if needle not in current:
        raise RuntimeError(
            "Le contenu attendu PASS n'est pas présent. "
            "AURA refuse de modifier un état inattendu."
        )
    new_text = current.replace(needle, 'AURA_DEV_SELFTEST = "PASS_EDITED"', 1)
    proposal = propose_edits(
        ROOT,
        [{
            "path": TARGET_REL,
            "new_text": new_text,
            "reason": "ADF-H R6.1 live self-development micro-test edit PASS -> PASS_EDITED",
        }],
        task=user_text,
    )
    validation = validate_in_staging(proposal, _test_commands())
    assessment = assess_proposal(proposal, ROOT)
    return {
        "proposal": proposal,
        "validation": validation,
        "assessment": assessment,
        "approvals_received": [],
        "operation": "edit",
        "created_at": int(time.time()),
    }


def _proposal_display(pending: dict[str, Any]) -> str:
    proposal = pending["proposal"]
    validation = pending["validation"]
    assessment = pending["assessment"]
    edits = proposal.get("edits") or []
    diff = edits[0].get("diff") if edits else ""
    tests = validation.get("tests") or []
    test_state = "PASS" if validation.get("passed") is True else "FAIL"
    required = assessment.get("required_approvals") or []
    lines = [
        "AURA Developer Fabric — micro-test préparé",
        f"Fichier : {TARGET_REL}",
        f"Risque : {assessment.get('max_risk', 'unknown')}",
        f"Staging / tests : {test_state}",
    ]
    if tests:
        lines.append(
            "Test : "
            + " ".join(str(x) for x in tests[0].get("command") or [])
            + f"  [exit={tests[0].get('exit')}]"
        )
    lines += ["", "DIFF", diff.rstrip() or "(aucune différence)", ""]
    if validation.get("passed") is True:
        lines.append("Aucune écriture n'a encore été effectuée.")
        lines.append("Pour appliquer, saisis exactement :")
        lines.extend(required)
    else:
        lines.append("Le patch n'est pas applicable : les tests de staging ont échoué.")
    return "\n".join(lines).strip()


def _handle_approval(text: str, state: dict[str, Any]) -> dict[str, Any] | None:
    pending = state.get("pending")
    if not isinstance(pending, dict):
        return None
    raw = str(text or "").strip()
    required = list(pending.get("assessment", {}).get("required_approvals") or [])
    if raw not in required:
        return None

    received = list(pending.get("approvals_received") or [])
    if raw not in received:
        received.append(raw)
    pending["approvals_received"] = received
    state["pending"] = pending
    _save_state(state)

    remaining = [x for x in required if x not in received]
    if remaining:
        return {
            "consumed": True,
            "display": (
                "Autorisation enregistrée. Il reste l'autorisation exacte suivante :\n"
                + "\n".join(remaining)
            ),
            "spoken": "Autorisation enregistrée. Une validation supplémentaire est requise.",
            "event": "approval_partial",
        }

    proposal = pending["proposal"]
    validation = pending["validation"]
    approval = required[0]
    critical = required[1] if len(required) >= 2 else None
    release = required[2] if len(required) >= 3 else None

    receipt = apply_self_development(
        proposal,
        validation,
        aura_root=ROOT,
        approval_phrase=approval,
        critical_approval=critical,
        release_approval=release,
        release_mode=(len(required) >= 3),
        post_test_commands=_test_commands(),
    )

    state["last_receipt"] = receipt
    state["pending"] = None
    _save_state(state)

    rollback_phrase = receipt.get("rollback_phrase") or ""
    display = [
        "Modification appliquée par AURA Developer Fabric.",
        f"Transaction : {receipt.get('transaction_id')}",
        f"Fichier : {TARGET_REL}",
        "Tests post-application : PASS",
    ]
    if rollback_phrase:
        display += ["", "Rollback disponible avec la phrase exacte :", rollback_phrase]
    return {
        "consumed": True,
        "display": "\n".join(display),
        "spoken": receipt.get("spoken_summary") or "La modification a été appliquée. Les tests sont passés.",
        "event": "applied",
    }


def _handle_rollback(text: str, state: dict[str, Any]) -> dict[str, Any] | None:
    receipt = state.get("last_receipt")
    if not isinstance(receipt, dict):
        return None
    expected = str(receipt.get("rollback_phrase") or "")
    raw = str(text or "").strip()
    if not expected or raw != expected:
        return None

    rollback = rollback_self_development(receipt, approval_phrase=raw)
    state["last_rollback"] = rollback
    state["last_receipt"] = None
    state["pending"] = None
    _save_state(state)
    return {
        "consumed": True,
        "display": (
            "Rollback AURA Developer Fabric terminé.\n"
            f"Transaction : {rollback.get('transaction_id')}\n"
            "Fichiers restaurés : "
            + ", ".join(rollback.get("restored_files") or [])
        ),
        "spoken": rollback.get("spoken_summary") or "La modification a été annulée.",
        "event": "rollback",
    }


def handle_developer_selftest_live(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    if not developer_mode_enabled(ROOT):
        return None

    state = _load_state()

    approval = _handle_approval(raw, state)
    if approval is not None:
        return approval

    rollback = _handle_rollback(raw, state)
    if rollback is not None:
        return rollback

    kind = _request_kind(raw)
    if kind is None:
        return None

    if kind == "help":
        return {
            "consumed": True,
            "display": (
                "Micro-test ADF-H R6.1 reconnu. "
                "Demande soit la création de selftest_dev_patch.py, "
                "soit son édition PASS -> PASS_EDITED."
            ),
            "spoken": "Le micro-test développeur est prêt.",
            "event": "help",
        }

    try:
        pending = _prepare_create(raw) if kind == "create" else _prepare_edit(raw)
    except Exception as exc:
        return {
            "consumed": True,
            "display": f"Micro-test refusé avant écriture : {type(exc).__name__}: {exc}",
            "spoken": "Le micro-test a été refusé avant toute écriture.",
            "event": "prepare_failed",
        }

    state["pending"] = pending
    _save_state(state)

    validation = pending["validation"]
    if validation.get("passed") is not True:
        return {
            "consumed": True,
            "display": _proposal_display(pending),
            "spoken": "Le patch de test a échoué en staging. Rien n'a été modifié.",
            "event": "staging_failed",
        }

    return {
        "consumed": True,
        "display": _proposal_display(pending),
        "spoken": "Le patch de test est prêt. Les tests sont passés. J'attends ton autorisation.",
        "event": "proposal_ready",
    }


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": "aura.adf-h-r6-1.live-selftest-capability.v1",
        "developer_mode_required": True,
        "intercept_before_normal_routing": True,
        "target": TARGET_REL,
        "deterministic_creation": True,
        "deterministic_edit_pass_to_pass_edited": True,
        "adf_f_propose_edits": True,
        "adf_f_staging_tests": True,
        "adf_g_assessment": True,
        "exact_approval_required": True,
        "adf_g_apply_self_development": True,
        "post_apply_tests": True,
        "audit_receipt": True,
        "exact_rollback_phrase": True,
        "unrelated_dev_requests_fall_through": True,
        "general_natural_language_code_generation": False,
    }
