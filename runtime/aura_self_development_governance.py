
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import hashlib, json, re

from runtime.aura_patch_transaction_engine import apply_approved, rollback_receipt
from runtime.aura_audit_ledger import AuditLedger
from runtime.aura_developer_mode import developer_mode_enabled, brief_change_summary
from runtime.aura_developer_live_bridge import queue_spoken_summary

RANK = {"standard":0,"elevated":1,"critical":2,"constitutional":3,"forbidden":99}

FORBIDDEN_PREFIXES = (
    ".git/", ".aura_audit/", ".aura_transactions/", "_patch_backups/",
)
FORBIDDEN_BASENAMES = {
    ".env","credentials.json","secrets.json","id_rsa","id_ed25519",
}
CONSTITUTIONAL_PATHS = {
    "core/version.py",
    "ci/aura_developer_fabric_capability_charter.json",
}
CRITICAL_PATHS = {
    "runtime/aura_patch_transaction_engine.py",
    "runtime/aura_self_development_governance.py",
    "runtime/aura_audit_ledger.py",
    "runtime/aura_fabric_http_gateway.py",
    "aura_dev_fabric.py",
    "aura_self_develop.py",
}

class SelfDevelopmentDenied(RuntimeError): pass
class SelfDevelopmentApprovalRequired(RuntimeError): pass

def _norm(path: str) -> str:
    raw = str(path).replace("\\", "/").strip()
    while raw.startswith("./"):
        raw = raw[2:]
    while "//" in raw:
        raw = raw.replace("//", "/")
    p = Path(raw).as_posix()
    if not p or p in {".", ".."} or p.startswith("/") or p.startswith("../") or "/../" in p:
        raise SelfDevelopmentDenied("invalid self-development path")
    return p

def classify_path(path: str) -> str:
    p = _norm(path)
    base = Path(p).name.lower()
    low = p.lower()
    if any(low.startswith(x) for x in FORBIDDEN_PREFIXES):
        return "forbidden"
    if base in FORBIDDEN_BASENAMES or Path(base).suffix.lower() in {".pem",".key",".p12",".pfx"}:
        return "forbidden"
    if re.match(r"^aura_.*_(result|report)\.(json|txt)$", base):
        return "forbidden"
    if p in CONSTITUTIONAL_PATHS:
        return "constitutional"
    if p in CRITICAL_PATHS or p.startswith("tests/invariants/") or p.startswith("ci/aura_developer_fabric_adf_"):
        return "critical"
    if p.startswith("runtime/") or p.startswith("core/") or p.startswith("launchers/") or p.endswith(".bat") or p.endswith(".cmd"):
        return "elevated"
    return "standard"

def _challenge(proposal: dict[str, Any], risk: str, paths: list[str]) -> str:
    payload = {
        "policy":"aura.self-development-policy.v1",
        "proposal_digest":proposal["proposal_digest"],
        "transaction_id":proposal["transaction_id"],
        "risk":risk,
        "paths":sorted(paths),
    }
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def _aura_managed_ui_dist_r7212r4() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    candidate = (
        Path(local)
        / "AURA"
        / "ui"
        / "v0.7.2.2-rc4.2"
        / "dist"
    )
    try:
        return candidate.resolve(strict=True)
    except Exception:
        return None


def _aura_managed_workspace_scope_r7212r4(
    workspace: Path,
    aura_root: Path,
    proposal: dict[str, Any],
) -> str | None:
    try:
        ws = Path(workspace).resolve(strict=True)
        root = Path(aura_root).resolve(strict=True)
    except Exception:
        return None

    if ws == root:
        return "aura_root"

    managed_ui = _aura_managed_ui_dist_r7212r4()
    if managed_ui is None or ws != managed_ui:
        return None

    allowed_ext = {".js", ".mjs", ".css", ".html", ".json", ".svg"}
    edits = proposal.get("edits") or []
    if not edits:
        return None

    for edit in edits:
        raw = str(edit.get("path") or "").replace("\\", "/").strip()
        rel = Path(raw)
        if not raw or rel.is_absolute() or ".." in rel.parts:
            return None
        if rel.suffix.casefold() not in allowed_ext:
            return None
        try:
            target = (managed_ui / rel).resolve(strict=False)
            target.relative_to(managed_ui)
        except Exception:
            return None

    return "managed_ui_dist"


def assess_proposal(proposal: dict[str, Any], aura_root: Path | str, *, release_mode: bool=False) -> dict[str, Any]:
    root=Path(aura_root).resolve(strict=True)
    workspace=Path(proposal["workspace"]).resolve(strict=True)
    workspace_scope=_aura_managed_workspace_scope_r7212r4(workspace,root,proposal)
    if workspace_scope is None:
        raise SelfDevelopmentDenied("self-development workspace is not AURA-managed")
    items=[]
    max_risk="standard"
    for edit in proposal.get("edits") or []:
        p=_norm(edit["path"]); risk=classify_path(p)
        items.append({"path":p,"risk":risk})
        if risk=="forbidden":
            raise SelfDevelopmentDenied("forbidden self-development target: "+p)
        if RANK[risk] > RANK[max_risk]:
            max_risk=risk
    if max_risk=="constitutional" and not release_mode:
        raise SelfDevelopmentDenied("constitutional files require explicit release_mode")
    challenge=_challenge(proposal,max_risk,[x["path"] for x in items])
    required=[proposal["approval_phrase"]]
    if RANK[max_risk] >= RANK["critical"]:
        required.append(f"AUTHORIZE SELF {proposal['transaction_id']} {challenge}")
    if max_risk=="constitutional":
        required.append(f"AUTHORIZE RELEASE {proposal['transaction_id']} {challenge}")
    return {
        "schema":"aura.self-development-assessment.v1",
        "transaction_id":proposal["transaction_id"],
        "proposal_digest":proposal["proposal_digest"],
        "max_risk":max_risk,
        "challenge":challenge,
        "files":items,
        "required_approvals":required,
        "release_mode":release_mode,
    }

def _proof(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def apply_self_development(
    proposal: dict[str, Any], validation: dict[str, Any], *,
    aura_root: Path | str,
    approval_phrase: str,
    critical_approval: str | None=None,
    release_approval: str | None=None,
    release_mode: bool=False,
    post_test_commands=None,
) -> dict[str, Any]:
    if not developer_mode_enabled(aura_root):
        raise SelfDevelopmentDenied("developer mode is disabled")
    assessment=assess_proposal(proposal,aura_root,release_mode=release_mode)
    expected=assessment["required_approvals"]
    supplied=[approval_phrase]
    if len(expected)>=2: supplied.append(critical_approval or "")
    if len(expected)>=3: supplied.append(release_approval or "")
    if supplied != expected:
        raise SelfDevelopmentApprovalRequired("exact self-development approval hierarchy required")
    ledger=AuditLedger(aura_root)
    before={e["path"]:e.get("old_sha256") for e in proposal["edits"]}
    ledger.append("self_apply_authorized",{
        "transaction_id":proposal["transaction_id"],
        "proposal_digest":proposal["proposal_digest"],
        "risk":assessment["max_risk"],
        "paths":[e["path"] for e in proposal["edits"]],
        "approval_proofs":[_proof(x) for x in supplied],
    })
    try:
        base=apply_approved(
            proposal,validation,approval_phrase=approval_phrase,
            post_test_commands=post_test_commands,
        )
    except Exception as exc:
        ledger.append("self_apply_failed",{
            "transaction_id":proposal["transaction_id"],
            "proposal_digest":proposal["proposal_digest"],
            "error_type":type(exc).__name__,
        })
        raise
    spoken_summary=brief_change_summary(proposal,outcome="applied")
    receipt={
        "schema":"aura.self-development-receipt.v1",
        "transaction_id":proposal["transaction_id"],
        "proposal_digest":proposal["proposal_digest"],
        "workspace":str(Path(aura_root).resolve()),
        "risk_assessment":assessment,
        "approval_proofs":[_proof(x) for x in supplied],
        "before_sha256":before,
        "base_transaction_receipt":base,
        "rollback_phrase":f"ROLLBACK SELF {proposal['transaction_id']} {assessment['challenge']}",
        "spoken_summary":spoken_summary,
        "spoken_summary_policy":"brief-only",
    }
    receipt_path=ledger.write_receipt(proposal["transaction_id"],receipt)
    event=ledger.append("self_apply_committed",{
        "transaction_id":proposal["transaction_id"],
        "proposal_digest":proposal["proposal_digest"],
        "receipt_sha256":hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "risk":assessment["max_risk"],
        "spoken_summary":spoken_summary,
    })
    receipt["audit_receipt_path"]=str(receipt_path)
    receipt["audit_event_hash"]=event["event_hash"]
    queue_spoken_summary(spoken_summary, root=aura_root)
    return receipt

def rollback_self_development(receipt: dict[str, Any], *, approval_phrase: str) -> dict[str, Any]:
    if receipt.get("schema")!="aura.self-development-receipt.v1":
        raise SelfDevelopmentDenied("invalid self-development receipt")
    if approval_phrase != receipt.get("rollback_phrase"):
        raise SelfDevelopmentApprovalRequired("exact self-development rollback phrase required")
    base=rollback_receipt(receipt["base_transaction_receipt"])
    ledger=AuditLedger(receipt["workspace"])
    event=ledger.append("self_rollback_committed",{
        "transaction_id":receipt["transaction_id"],
        "proposal_digest":receipt["proposal_digest"],
        "restored_files":base.get("restored_files") or [],
        "rollback_approval_proof":_proof(approval_phrase),
    })
    restored=base.get("restored_files") or []
    rollback_summary="J’ai annulé la modification et restauré " + str(len(restored)) + " fichier" + ("" if len(restored)==1 else "s") + "."
    queue_spoken_summary(rollback_summary, root=receipt["workspace"])
    return {
        "schema":"aura.self-development-rollback-receipt.v1",
        "transaction_id":receipt["transaction_id"],
        "rolled_back":True,
        "restored_files":restored,
        "audit_event_hash":event["event_hash"],
        "spoken_summary":rollback_summary,
        "spoken_summary_policy":"brief-only",
    }

def capability_snapshot():
    return {
        "schema":"aura.self-development-capabilities.v1",
        "self_modification_default":"approval-gated",
        "workspace_must_equal_aura_root":False,
        "workspace_policy":"aura_root_or_exact_managed_ui_dist",
        "managed_external_workspace_arbitrary":False,
        "managed_ui_extensions":[".js",".mjs",".css",".html",".json",".svg"],
        "risk_levels":["standard","elevated","critical","constitutional","forbidden"],
        "critical_dual_gate":True,
        "constitutional_release_gate":True,
        "certification_result_files_forbidden":True,
        "audit_ledger_forbidden_as_patch_target":True,
        "cryptographic_patch_bound_challenge":True,
        "exact_approval_phrases":True,
        "transaction_engine_reused":True,
        "automatic_rollback_guard_inherited":True,
        "manual_self_rollback_approval":True,
        "developer_mode_required_for_apply":True,
        "brief_spoken_summary_after_apply":True,
    }


# AURA ROADMAP RM26-2 — automatic post-apply Roadmap certification hook
_rm26_apply_self_development_base = apply_self_development
_rm26_rollback_self_development_base = rollback_self_development


def apply_self_development(
    proposal: dict[str, Any],
    validation: dict[str, Any],
    *,
    aura_root: Path | str,
    approval_phrase: str,
    critical_approval: str | None = None,
    release_approval: str | None = None,
    post_test_commands=None,
    release_mode: bool = False,
) -> dict[str, Any]:
    receipt = _rm26_apply_self_development_base(
        proposal,
        validation,
        aura_root=aura_root,
        approval_phrase=approval_phrase,
        critical_approval=critical_approval,
        release_approval=release_approval,
        post_test_commands=post_test_commands,
        release_mode=release_mode,
    )

    from runtime.aura_roadmap_developer_certifier_rm26 import (
        certify_after_post_apply,
    )

    try:
        roadmap_result = certify_after_post_apply(
            proposal,
            receipt,
            root=aura_root,
        )
    except Exception:
        # Source APPLY already succeeded. A failed Roadmap certification must not
        # leave a half-committed source transaction.
        try:
            _rm26_rollback_self_development_base(
                receipt,
                approval_phrase=receipt["rollback_phrase"],
            )
        finally:
            raise

    receipt["proposal_metadata"] = (
        dict(proposal.get("metadata"))
        if isinstance(proposal.get("metadata"), dict)
        else None
    )
    receipt["roadmap_certification"] = roadmap_result
    return receipt


def rollback_self_development(
    receipt: dict[str, Any],
    *,
    approval_phrase: str,
) -> dict[str, Any]:
    result = _rm26_rollback_self_development_base(
        receipt,
        approval_phrase=approval_phrase,
    )

    if result.get("rolled_back") is True:
        from runtime.aura_roadmap_developer_certifier_rm26 import (
            reconcile_rollback_from_receipt,
        )
        reconciliation = reconcile_rollback_from_receipt(
            receipt,
            result,
            root=receipt.get("workspace") or DEFAULT_AURA_ROOT,
        )
        result["roadmap_reconciliation"] = reconciliation

    return result
