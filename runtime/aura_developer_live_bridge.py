
from __future__ import annotations
from pathlib import Path
from typing import Any
import json, os, time
from runtime.aura_developer_mode import developer_mode_enabled, handle_developer_mode_command, state_snapshot

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
QUEUE_LIMIT = 8
SPEAK_LIMIT = 150

def _queue_path(root=None):
    base = Path(root).resolve() if root is not None else ROOT
    return base / "runtime" / "developer_fabric" / "spoken_summary_queue.json"

def _safe_spoken(text):
    value = " ".join(str(text or "").split()).strip()
    if len(value) > SPEAK_LIMIT:
        value = value[: SPEAK_LIMIT - 1].rstrip(" ,.;:") + "…"
    return value

def queue_spoken_summary(text, *, root=None):
    value = _safe_spoken(text)
    if not value:
        return {"queued": False, "reason": "empty"}
    path = _queue_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    items = []
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                items = raw
        except Exception:
            items = []
    items.append({"text": value, "created_at": int(time.time())})
    items = items[-QUEUE_LIMIT:]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return {"queued": True, "count": len(items), "text": value}

def dequeue_spoken_summary(*, root=None):
    path = _queue_path(root)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else []
    except Exception:
        items = []
    if not items:
        try:
            path.unlink()
        except Exception:
            pass
        return None
    first = _safe_spoken(items[0].get("text", ""))
    remaining = items[1:]
    if remaining:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(remaining, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    else:
        try:
            path.unlink()
        except Exception:
            pass
    return first or None

def is_developer_workspace_command(text):
    from runtime.aura_developer_mode import _normalize_phrase
    value = _normalize_phrase(text)
    phrases = (
        "ouvre espace developpeur",
        "ouvre l espace developpeur",
        "affiche espace developpeur",
        "affiche l espace developpeur",
        "ouvre developer workspace",
        "affiche developer workspace",
    )
    return any(p in value for p in phrases)

def handle_live_developer_input(text, *, channel="text", root=None):
    result = handle_developer_mode_command(text, channel=channel, root=root)
    if result.get("recognized"):
        return {**result, "route":"developer-mode-toggle", "consume":True, "forward_to_llm":False, "open_workspace":False}
    if developer_mode_enabled(root) and is_developer_workspace_command(text):
        return {
            "schema":"aura.developer-live-command.v1",
            "recognized":True, "enabled":True, "channel":channel,
            "route":"developer-workspace-open", "consume":True,
            "forward_to_llm":False, "speak":"Espace développeur ouvert.",
            "open_workspace":True,
        }
    return {
        "schema":"aura.developer-live-command.v1",
        "recognized":False, "enabled":developer_mode_enabled(root),
        "channel":channel, "route":"conversation", "consume":False,
        "forward_to_llm":True, "speak":None, "open_workspace":False,
    }

def workspace_snapshot(root=None):
    base = Path(root).resolve() if root is not None else ROOT
    audit_head = base / ".aura_audit" / "head.json"
    transaction_root = base / ".aura_transactions"
    transactions = []
    if transaction_root.is_dir():
        candidates = []
        for path in transaction_root.rglob("receipt.json"):
            try:
                candidates.append((path.stat().st_mtime, path))
            except Exception:
                pass
        for _, path in sorted(candidates, reverse=True)[:12]:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            transactions.append({
                "transaction_id": raw.get("transaction_id"),
                "receipt": str(path.relative_to(base)),
                "tests_passed": raw.get("tests_passed"),
                "rolled_back": raw.get("rolled_back"),
            })
    audit = None
    if audit_head.is_file():
        try:
            audit = json.loads(audit_head.read_text(encoding="utf-8"))
        except Exception:
            audit = {"error":"unreadable"}
    return {
        "schema":"aura.developer-workspace-snapshot.v1",
        "developer_mode":state_snapshot(base),
        "audit_head":audit,
        "recent_transactions":transactions,
        "safety":{
            "staging_required":True, "tests_required":True,
            "explicit_apply_required":True, "critical_dual_gate":True,
            "constitutional_release_gate":True, "rollback_guard":True,
        },
    }

def capability_snapshot():
    return {
        "schema":"aura.developer-live-bridge-capabilities.v1",
        "text_intercept_before_llm":True,
        "voice_transcript_same_route":True,
        "stt_channel_tagging":True,
        "native_tts_confirmation":True,
        "brief_summary_queue":True,
        "workspace_open_by_conversation":True,
        "does_not_bypass_write_approval":True,
        "spoken_limit_chars":SPEAK_LIMIT,
    }
