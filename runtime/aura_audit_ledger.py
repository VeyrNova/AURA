
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, json, os, time

def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()

class AuditLedgerError(RuntimeError):
    pass

class AuditLedger:
    def __init__(self, workspace: Path | str):
        self.workspace = Path(workspace).resolve(strict=True)
        self.root = self.workspace / ".aura_audit"
        self.ledger = self.root / "events.jsonl"
        self.head = self.root / "head.json"
        self.receipts = self.root / "receipts"

    def verify(self) -> dict[str, Any]:
        if not self.ledger.exists():
            return {"ok": True, "count": 0, "head_hash": None}
        prev = None
        count = 0
        for raw in self.ledger.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            event = json.loads(raw)
            expected = event.get("event_hash")
            body = dict(event); body.pop("event_hash", None)
            if event.get("sequence") != count + 1:
                raise AuditLedgerError("audit sequence mismatch")
            if event.get("prev_hash") != prev:
                raise AuditLedgerError("audit previous-hash mismatch")
            actual = _hash(body)
            if actual != expected:
                raise AuditLedgerError("audit event hash mismatch")
            prev = expected
            count += 1
        if self.head.exists():
            head = json.loads(self.head.read_text(encoding="utf-8"))
            if head.get("count") != count or head.get("head_hash") != prev:
                raise AuditLedgerError("audit head anchor mismatch")
        return {"ok": True, "count": count, "head_hash": prev}

    def append(self, event_type: str, payload: dict[str, Any], *, actor: str="aura-developer-fabric") -> dict[str, Any]:
        state = self.verify()
        self.root.mkdir(parents=True, exist_ok=True)
        self.receipts.mkdir(parents=True, exist_ok=True)
        event = {
            "schema": "aura.audit-event.v1",
            "sequence": state["count"] + 1,
            "timestamp": int(time.time()),
            "event_type": event_type,
            "actor": actor,
            "prev_hash": state["head_hash"],
            "payload": payload,
        }
        event["event_hash"] = _hash(event)
        with self.ledger.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp = self.head.with_suffix(".tmp")
        tmp.write_text(json.dumps({"schema":"aura.audit-head.v1","count":event["sequence"],"head_hash":event["event_hash"]}, indent=2), encoding="utf-8")
        os.replace(tmp, self.head)
        return event

    def write_receipt(self, txn_id: str, receipt: dict[str, Any]) -> Path:
        self.receipts.mkdir(parents=True, exist_ok=True)
        path = self.receipts / (txn_id + ".json")
        if path.exists():
            raise AuditLedgerError("self-development receipt already exists")
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
        return path

def capability_snapshot():
    return {
        "schema":"aura.audit-ledger-capabilities.v1",
        "sha256_hash_chain":True,
        "head_anchor":True,
        "append_only_intent":True,
        "tamper_detection":True,
        "immutable_receipt_path_policy":True,
    }
