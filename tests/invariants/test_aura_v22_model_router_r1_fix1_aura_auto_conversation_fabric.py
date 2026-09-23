from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import runtime.aura_conversation_fabric_bridge as bridge
from runtime.aura_conversation_fabric_bridge import (
    AUTO_ALIAS,
    build_canonical_request,
    generate_conversation_fabric,
    should_use_conversation_fabric_auto,
)
from runtime.aura_fabric_http_gateway import PROTOCOL_MAP

MAIN = ROOT / "ui" / "main_window.py"
text = MAIN.read_text(encoding="utf-8-sig")

assert "AURA_V22_MODEL_ROUTER_R1_AUTO_PROFILE_MARKER" in text
assert "AURA_V22_MODEL_ROUTER_R1_FABRIC_STREAM" in text
assert "AURA_V22_MODEL_ROUTER_R1_FABRIC_METRICS" in text
assert "from runtime.aura_conversation_fabric_bridge import (" in text

assert should_use_conversation_fabric_auto(
    {"provider": "gemini", "name": "text-brain"},
    "Explique-moi la relativité."
)
assert should_use_conversation_fabric_auto(
    {"provider": "groq", "name": "voice-brain"},
    "Quelle est la capitale du Japon ?"
)
assert not should_use_conversation_fabric_auto(
    {"provider": "gemini", "route_reason": "preferred-gemini"},
    "Explique-moi la relativité."
)
assert not should_use_conversation_fabric_auto(
    {"provider": "groq", "route_reason": "preferred-groq"},
    "Explique-moi la relativité."
)
assert not should_use_conversation_fabric_auto(
    {"provider": "local", "route_reason": "privacy-local"},
    "Réponds en local."
)
assert not should_use_conversation_fabric_auto(
    {"provider": "gemini", "name": "text-brain"},
    "Utilise Gemini uniquement pour cette réponse."
)
assert not should_use_conversation_fabric_auto(
    {"provider": "gemini", "document_context": True},
    "Analyse ce PDF."
)

request = build_canonical_request(
    [
        {"role": "system", "content": "Tu es AURA."},
        {"role": "user", "content": "bonjour fabric"},
    ],
    profile={"num_predict": 64, "temperature": 0.2, "top_p": 0.8},
)
assert request.model == AUTO_ALIAS
assert request.protocol in PROTOCOL_MAP
assert request.stream is False
assert len(request.messages) == 2

class FakeService:
    def __init__(self):
        self.failovers_total = 7
        self.last_route = {}
        self.requests = []
    def execute(self, request):
        self.requests.append(request)
        self.failovers_total += 1
        self.last_route = {
            "failover_used": True,
            "attempts": [
                {"provider_id": "gemini", "ok": False},
                {"provider_id": "groq", "ok": True},
            ],
        }
        return SimpleNamespace(
            text="réponse fabric test",
            provider_id="groq",
            routed_model="groq/test-model",
            requested_model=AUTO_ALIAS,
            finish_reason="stop",
            input_tokens=12,
            output_tokens=4,
            metadata={},
        )

fake = FakeService()
old_service = bridge._service
try:
    bridge._service = fake
    result = generate_conversation_fabric(
        [{"role": "user", "content": "test"}],
        profile={"num_predict": 32, "temperature": 0.2},
    )
finally:
    bridge._service = old_service

assert result["text"] == "réponse fabric test"
assert result["provider_id"] == "groq"
assert result["failover_used"] is True
assert result["failover_count"] == 1
assert len(result["attempts"]) == 2
assert len(fake.requests) == 1
assert fake.requests[0].model == AUTO_ALIAS

print("[PASS] AUTO eligibility preserves explicit/local/document routes")
print("[PASS] CanonicalRequest uses a current PROTOCOL_MAP key")
print("[PASS] buffered Fabric execute path is compatible with existing stream loop adaptation")
print("[PASS] failover telemetry is recovered from GatewayService counters/last_route")
print("[PASS] no external provider/network call is used by this invariant")
