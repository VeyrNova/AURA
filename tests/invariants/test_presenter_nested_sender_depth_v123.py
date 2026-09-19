from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.personal_result_presenter_v123 import (
    build_personal_result_payload_v123,
    _plain,
)

reply = SimpleNamespace(
    provider_id="email.provider",
    capability_id="email.search",
    status="succeeded",
    text="",
    payload={
        "messages": [
            {
                "subject": "fixture subject",
                "sender": {
                    "display_name": "Fixture Sender",
                    "address": "fixture@example.test",
                    "email": "fixture@example.test",
                },
                "date": "2026-08-29",
            }
        ]
    },
)
request = SimpleNamespace(
    provider_id="email.provider",
    capability_id="email.search",
)

payload = build_personal_result_payload_v123(reply, request)
assert payload["kind"] == "mail", payload
assert payload["source"] == "reply_object", payload
assert payload["count"] == 1, payload

sender = payload["items"][0]["sender"]
assert isinstance(sender, dict), sender
assert sender.get("display_name") == "Fixture Sender", sender
assert sender.get("address") == "fixture@example.test", sender
assert sender.get("email") == "fixture@example.test", sender

# The safety/depth guard still rejects a CONTAINER that itself starts
# beyond the accepted depth. The patch only changes primitive ordering.
deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": "too-deep"}}}}}}}
plain = _plain(deep)
node = plain
for key in ("a", "b", "c", "d", "e"):
    assert isinstance(node, dict), plain
    node = node.get(key)
assert isinstance(node, dict), plain
assert node.get("f") is None, plain

print("[PASS] presenter nested sender primitive depth invariant")