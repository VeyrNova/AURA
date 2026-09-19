
from __future__ import annotations
from typing import Any
import hashlib, json

def build_development_plan(task: str, context_pack: dict[str, Any]) -> dict[str, Any]:
    task=(task or "").strip()
    if not task:
        raise ValueError("task is required")
    files=[f["path"] for f in context_pack.get("files",[])]
    fingerprint=hashlib.sha256(json.dumps({
        "task":task,
        "workspace":context_pack.get("workspace"),
        "files":[(f.get("path"),f.get("sha256")) for f in context_pack.get("files",[])],
    },sort_keys=True).encode()).hexdigest()[:20]
    return {
        "schema":"aura.developer-plan.v1",
        "plan_id":"plan_"+fingerprint,
        "task":task,
        "workspace":context_pack.get("workspace"),
        "context_files":files,
        "stages":[
            {"id":"inspect","write":False,"description":"Inspect bounded repository context and current hashes."},
            {"id":"propose","write":False,"description":"Produce explicit file edits with unified diffs and expected pre-image hashes."},
            {"id":"stage","write":False,"description":"Apply proposed edits only inside an isolated staging copy."},
            {"id":"test","write":False,"description":"Run allowlisted test commands without shell expansion in staging."},
            {"id":"diff_review","write":False,"description":"Review exact before/after unified diffs and staging results."},
            {"id":"approval_gate","write":False,"description":"Require exact explicit approval phrase bound to transaction id."},
            {"id":"transaction_apply","write":True,"description":"Backup target files then atomically write approved changes."},
            {"id":"post_apply_test","write":False,"description":"Re-run approved tests; rollback automatically on failure."},
            {"id":"rollback_guard","write":True,"description":"Restore exact pre-image files from transaction backup if required."},
        ],
        "guardrails":{
            "read_only_default":True,
            "outside_workspace_denied":True,
            "staging_required_before_apply":True,
            "tests_required_before_apply":True,
            "explicit_approval_required":True,
            "backup_required":True,
            "automatic_rollback_on_post_test_failure":True,
            "shell_execution":False,
        },
    }

def capability_snapshot() -> dict[str, Any]:
    return {
        "schema":"aura.developer-planner-capabilities.v1",
        "deterministic_plan":True,
        "context_hash_binding":True,
        "staging_before_apply":True,
        "explicit_approval_gate":True,
        "post_apply_rollback_guard":True,
    }
