
from __future__ import annotations
import sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import AURA_VERSION
from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations import IntegrationRegistry, IntegrationRequest
from integrations.email import *

assert AURA_VERSION=='0.9.4', AURA_VERSION
assert len(EMAIL_CAPABILITIES)==11
assert len(READ_CAPABILITIES)==4
assert len(CONFIRMATION_CAPABILITIES)==6

class Security:
    def authorize(self,action,params,user_confirmed=False):
        if action in CONFIRMATION_CAPABILITIES and not user_confirmed: return "REQUIRE_CONFIRMATION"
        return "ALLOW"

sender=EmailAddress("alice@example.invalid","Alice")
recipient=EmailAddress("boris@example.invalid","Boris")
att=EmailAttachment("att-1","report.pdf","application/pdf",2048)
msg=EmailMessage("msg-1","thr-1","Quarterly report",sender,(recipient,),"2026-08-26T10:00:00+00:00","Synthetic body",labels=("INBOX","UNREAD"),attachments=(att,))

with tempfile.TemporaryDirectory(prefix="aura_v091_email_") as td:
    db=Path(td)/"receipts.db"
    receipts=ActionReceiptService(store=ActionReceiptStore(db))
    backend=SyntheticEmailBackend((msg,))
    provider=EmailProvider(backend)
    registry=IntegrationRegistry(security_engine=Security(),receipt_service=receipts)
    registry.register_provider(provider)
    caps={c.capability_id:c for c in provider.manifest.capabilities}
    for cid in READ_CAPABILITIES: assert not caps[cid].requires_confirmation
    for cid in CONFIRMATION_CAPABILITIES: assert caps[cid].requires_confirmation

    for cid,params in [
        ("email.search",{"query":{"text":"report"}}),
        ("email.read",{"message_id":"msg-1"}),
        ("email.read_thread",{"thread_id":"thr-1"}),
        ("email.list_attachments",{"message_id":"msg-1"}),
        ("email.create_draft",{"to":["alice@example.invalid"],"subject":"Draft","body_text":"Body"}),
    ]:
        r=registry.execute_integration(IntegrationRequest.create(provider_id="email.provider",capability_id=cid,params=params,origin="test"))
        assert r.status=="succeeded", (cid,r.status,r.error)

    writes=[
        ("email.send",{"to":["alice@example.invalid"],"subject":"Send","body_text":"Body"}),
        ("email.reply",{"message_id":"msg-1","body_text":"Reply"}),
        ("email.forward",{"message_id":"msg-1","to":["carol@example.invalid"],"body_text":"Forward"}),
        ("email.archive",{"message_id":"msg-1"}),
        ("email.trash",{"message_id":"msg-1"}),
        ("email.label",{"message_id":"msg-1","add":["STARRED"]}),
    ]
    for cid,params in writes:
        req=IntegrationRequest.create(provider_id="email.provider",capability_id=cid,params=params,origin="test-write")
        before=len(backend.calls)
        waiting=registry.execute_integration(req)
        assert waiting.status=="waiting_confirmation"
        assert len(backend.calls)==before
        confirmed=registry.execute_integration(req,user_confirmed=True)
        assert confirmed.status=="succeeded"
        assert confirmed.receipt_id==waiting.receipt_id
        assert len(backend.calls)==before+1

    missing=registry.execute_integration(IntegrationRequest.create(provider_id="email.provider",capability_id="email.read",params={"message_id":"missing"},origin="test"))
    assert missing.status=="failed" and missing.output is None and missing.error=="EmailLookupError"

    unknown=registry.execute_integration(IntegrationRequest.create(provider_id="email.provider",capability_id="email.delete_forever",params={},origin="test"))
    assert unknown.status=="denied"

    secret="EMAIL-TOKEN-SECRET-987"
    s=registry.execute_integration(IntegrationRequest.create(provider_id="email.provider",capability_id="email.search",params={"query":{"text":"report"},"token":secret,"credential":secret},origin="secret"))
    assert s.status=="succeeded"
    assert secret.encode() not in db.read_bytes()

    db.unlink(); assert not db.exists()

print("[PASS] Email Provider v0.9.1 synthetic lifecycle invariant")
