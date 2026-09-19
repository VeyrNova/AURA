
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import difflib, hashlib, json, os, shutil, subprocess, sys, tempfile, time, uuid

from runtime.aura_repository_context import WorkspaceBoundary, WorkspaceBoundaryError, DEFAULT_IGNORED_DIRS, sha256_bytes

ALLOWED_TEST_EXECUTABLES={
    "python","python.exe","python3","python3.exe","py","py.exe","pytest","pytest.exe",
    "node","node.exe","npm","npm.cmd","pnpm","pnpm.cmd","yarn","yarn.cmd",
    "cargo","cargo.exe","go","go.exe","dotnet","dotnet.exe","mvn","mvn.cmd",
    "gradle","gradle.bat","gradlew","gradlew.bat",
}

class TransactionError(RuntimeError): pass
class ApprovalRequired(TransactionError): pass
class StaleWorkspace(TransactionError): pass
class TestCommandDenied(TransactionError): pass

def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _proposal_digest(payload: dict[str, Any]) -> str:
    stable={k:v for k,v in payload.items() if k not in {"proposal_digest"}}
    return hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()

def _read_utf8(path: Path) -> tuple[bool,str]:
    if not path.exists():
        return False,""
    if not path.is_file():
        raise TransactionError(f"target is not a file: {path}")
    data=path.read_bytes()
    if b"\x00" in data[:4096]:
        raise TransactionError(f"binary target denied: {path}")
    return True,data.decode("utf-8")

def propose_edits(workspace: Path | str, edits: Iterable[dict[str, Any]], *, task: str="", metadata: dict[str, Any] | None=None) -> dict[str, Any]:
    boundary=WorkspaceBoundary(workspace)
    normalized=[]
    for raw in edits:
        rel=Path(str(raw.get("path") or "")).as_posix()
        if not rel or rel==".":
            raise TransactionError("edit path is required")
        target=boundary.resolve(rel,must_exist=False)
        existed,old=_read_utf8(target)
        old_sha=_sha_text(old) if existed else None
        expected=raw.get("expected_sha256")
        if expected is not None and expected!=old_sha:
            raise StaleWorkspace(f"pre-image hash mismatch for {rel}")
        new_text=raw.get("new_text")
        if not isinstance(new_text,str):
            raise TransactionError(f"new_text must be a string for {rel}")
        diff="".join(difflib.unified_diff(
            old.splitlines(True),new_text.splitlines(True),
            fromfile="a/"+rel,tofile="b/"+rel,n=3,
        ))
        normalized.append({
            "path":rel,"existed_before":existed,"old_sha256":old_sha,
            "new_sha256":_sha_text(new_text),"new_text":new_text,
            "reason":str(raw.get("reason") or ""),"diff":diff,
        })
    if not normalized:
        raise TransactionError("at least one edit is required")
    txn_id="txn_"+uuid.uuid4().hex[:20]
    proposal={
        "schema":"aura.patch-proposal.v1","transaction_id":txn_id,"workspace":str(boundary.root),
        "task":task,"created_at":int(time.time()),"edits":normalized,
        "approval_phrase":"APPLY "+txn_id,
        "guardrails":{"write_performed":False,"staging_required":True,"tests_required":True,"explicit_approval_required":True},
    }
    if metadata:
        if not isinstance(metadata,dict):
            raise TransactionError("proposal metadata must be a dict")
        proposal["metadata"]=dict(metadata)
    proposal["proposal_digest"]=_proposal_digest(proposal)
    return proposal

def _verify_proposal(proposal: dict[str, Any]) -> None:
    if proposal.get("schema")!="aura.patch-proposal.v1":
        raise TransactionError("unsupported proposal schema")
    expected=proposal.get("proposal_digest")
    if not isinstance(expected,str) or expected!=_proposal_digest(proposal):
        raise TransactionError("proposal digest mismatch")

def _copy_workspace(src: Path, dst: Path) -> None:
    for root,dirs,files in os.walk(src,topdown=True,followlinks=False):
        rootp=Path(root)
        relroot=rootp.relative_to(src)
        dirs[:]=[d for d in dirs if d not in DEFAULT_IGNORED_DIRS and not (rootp/d).is_symlink()]
        target_root=dst/relroot
        target_root.mkdir(parents=True,exist_ok=True)
        for name in files:
            p=rootp/name
            if p.is_symlink():
                continue
            rel=p.relative_to(src)
            if any(part in DEFAULT_IGNORED_DIRS for part in rel.parts):
                continue
            try:
                if p.stat().st_size>5*1024*1024:
                    continue
                shutil.copy2(p,dst/rel)
            except OSError:
                continue

def _apply_edits_to_root(root: Path, edits: list[dict[str, Any]]) -> None:
    for edit in edits:
        target=(root/edit["path"]).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise WorkspaceBoundaryError(f"staging path escapes workspace: {edit['path']}") from exc
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(edit["new_text"],encoding="utf-8",newline="")

def _normalize_commands(commands: Iterable[Iterable[str]]) -> list[list[str]]:
    out=[]
    for command in commands:
        cmd=[str(x) for x in command]
        if not cmd:
            raise TestCommandDenied("empty test command")
        exe=Path(cmd[0]).name.lower()
        if exe not in ALLOWED_TEST_EXECUTABLES:
            # Allow the exact interpreter running AURA certification/runtime.
            try:
                exact=Path(cmd[0]).resolve()==Path(sys.executable).resolve()
            except Exception:
                exact=False
            if not exact:
                raise TestCommandDenied(f"test executable denied: {cmd[0]}")
        out.append(cmd)
    if not out:
        raise TransactionError("at least one test command is required")
    return out

def _run_tests(root: Path, commands: list[list[str]], *, timeout_s: int=120) -> list[dict[str, Any]]:
    results=[]
    for cmd in commands:
        started=time.monotonic()
        try:
            cp=subprocess.run(cmd,cwd=str(root),capture_output=True,text=True,errors="replace",timeout=timeout_s,shell=False)
            item={"command":cmd,"exit":cp.returncode,"passed":cp.returncode==0,
                  "duration_ms":round((time.monotonic()-started)*1000,3),
                  "stdout":(cp.stdout or "")[-12000:],"stderr":(cp.stderr or "")[-12000:]}
        except subprocess.TimeoutExpired as exc:
            item={"command":cmd,"exit":None,"passed":False,"timed_out":True,
                  "duration_ms":round((time.monotonic()-started)*1000,3),
                  "stdout":str(exc.stdout or "")[-12000:],"stderr":str(exc.stderr or "")[-12000:]}
        results.append(item)
        if not item["passed"]:
            break
    return results

def validate_in_staging(proposal: dict[str, Any], test_commands: Iterable[Iterable[str]], *, timeout_s: int=120) -> dict[str, Any]:
    _verify_proposal(proposal)
    commands=_normalize_commands(test_commands)
    workspace=Path(proposal["workspace"]).resolve(strict=True)
    boundary=WorkspaceBoundary(workspace)
    # Verify pre-images before spending test time.
    for edit in proposal["edits"]:
        target=boundary.resolve(edit["path"],must_exist=False)
        existed,old=_read_utf8(target)
        live_sha=_sha_text(old) if existed else None
        if live_sha!=edit["old_sha256"]:
            raise StaleWorkspace(f"workspace changed since proposal: {edit['path']}")
    with tempfile.TemporaryDirectory(prefix="aura_adf_stage_") as td:
        stage=Path(td)/"workspace"
        stage.mkdir()
        _copy_workspace(workspace,stage)
        _apply_edits_to_root(stage,proposal["edits"])
        tests=_run_tests(stage,commands,timeout_s=timeout_s)
        passed=bool(tests) and all(t["passed"] for t in tests)
        return {
            "schema":"aura.patch-staging-validation.v1","transaction_id":proposal["transaction_id"],
            "proposal_digest":proposal["proposal_digest"],"passed":passed,
            "tests":tests,"staging_ephemeral":True,"workspace_written":False,
            "test_commands":commands,
        }

def _backup_targets(workspace: Path, txn_id: str, edits: list[dict[str, Any]]) -> tuple[Path,list[dict[str,Any]]]:
    backup_root=workspace/".aura_transactions"/"backups"/txn_id
    backup_root.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for edit in edits:
        rel=Path(edit["path"])
        src=workspace/rel
        dst=backup_root/rel
        existed=src.exists()
        if existed:
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
        manifest.append({"path":rel.as_posix(),"existed_before":existed})
    (backup_root/"_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return backup_root,manifest

def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".aura_tmp_"+uuid.uuid4().hex[:8])
    temp.write_text(text,encoding="utf-8",newline="")
    os.replace(temp,path)

def _restore(workspace: Path, backup_root: Path, manifest: list[dict[str,Any]]) -> None:
    for item in manifest:
        target=workspace/item["path"]
        backup=backup_root/item["path"]
        if item["existed_before"]:
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(backup,target)
        elif target.exists():
            target.unlink()

def apply_approved(
    proposal: dict[str, Any],
    validation: dict[str, Any],
    *,
    approval_phrase: str,
    post_test_commands: Iterable[Iterable[str]] | None=None,
    timeout_s: int=120,
) -> dict[str, Any]:
    _verify_proposal(proposal)
    if validation.get("schema")!="aura.patch-staging-validation.v1":
        raise TransactionError("invalid staging validation")
    if validation.get("transaction_id")!=proposal["transaction_id"] or validation.get("proposal_digest")!=proposal["proposal_digest"]:
        raise TransactionError("validation is not bound to proposal")
    if validation.get("passed") is not True:
        raise TransactionError("staging tests must pass before apply")
    if approval_phrase!=proposal["approval_phrase"]:
        raise ApprovalRequired("exact approval phrase required")
    workspace=Path(proposal["workspace"]).resolve(strict=True)
    boundary=WorkspaceBoundary(workspace)
    for edit in proposal["edits"]:
        target=boundary.resolve(edit["path"],must_exist=False)
        existed,old=_read_utf8(target)
        if (_sha_text(old) if existed else None)!=edit["old_sha256"]:
            raise StaleWorkspace(f"workspace changed since staging: {edit['path']}")

    backup_root,manifest=_backup_targets(workspace,proposal["transaction_id"],proposal["edits"])
    applied=False
    rolled_back=False
    tests=[]
    try:
        for edit in proposal["edits"]:
            _atomic_write(boundary.resolve(edit["path"],must_exist=False),edit["new_text"])
        applied=True
        commands=_normalize_commands(post_test_commands or validation.get("test_commands") or [])
        tests=_run_tests(workspace,commands,timeout_s=timeout_s)
        if not tests or not all(t["passed"] for t in tests):
            raise TransactionError("post-apply tests failed")
    except Exception:
        _restore(workspace,backup_root,manifest)
        rolled_back=True
        raise
    receipt={
        "schema":"aura.patch-transaction-receipt.v1","transaction_id":proposal["transaction_id"],
        "proposal_digest":proposal["proposal_digest"],"workspace":str(workspace),
        "approval_phrase_matched":True,"backup_root":str(backup_root),
        "files":manifest,"diffs":[e["diff"] for e in proposal["edits"]],
        "post_apply_tests":tests,"applied":applied,"rolled_back":rolled_back,
        "created_at":int(time.time()),
    }
    receipt_path=backup_root/"_receipt.json"
    receipt_path.write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding="utf-8")
    receipt["receipt_path"]=str(receipt_path)
    return receipt

def rollback_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema")!="aura.patch-transaction-receipt.v1":
        raise TransactionError("invalid receipt")
    workspace=Path(receipt["workspace"]).resolve(strict=True)
    backup_root=Path(receipt["backup_root"]).resolve(strict=True)
    boundary=WorkspaceBoundary(workspace)
    try:
        backup_root.relative_to(workspace)
    except ValueError as exc:
        raise WorkspaceBoundaryError("backup root outside workspace") from exc
    manifest=list(receipt.get("files") or [])
    _restore(workspace,backup_root,manifest)
    return {"schema":"aura.patch-rollback-receipt.v1","transaction_id":receipt["transaction_id"],"rolled_back":True,"restored_files":[x["path"] for x in manifest]}

def capability_snapshot() -> dict[str, Any]:
    return {
        "schema":"aura.patch-transaction-capabilities.v1",
        "unified_diff":True,"preimage_hash_binding":True,"ephemeral_staging":True,
        "allowlisted_test_commands":True,"shell_execution":False,"explicit_approval_phrase":True,
        "transaction_backup":True,"atomic_file_replace":True,"post_apply_tests":True,
        "automatic_rollback_on_post_test_failure":True,"manual_receipt_rollback":True,
        "outside_workspace_denied":True,
    }
