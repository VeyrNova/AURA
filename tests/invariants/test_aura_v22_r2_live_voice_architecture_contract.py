
from __future__ import annotations
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "data" / "roadmap" / "AURA_V2_2_LIVE_VOICE_ARCHITECTURE_CONTRACT.json"

data = json.loads(CONTRACT.read_text(encoding="utf-8"))

assert data["schema"] == "aura.v2.2.live-voice.architecture-contract.v1"
assert data["status"] == "ARCHITECTURE_FROZEN"
assert data["canonical_authority"]["future_module"] == "voice/live_voice_session_v220.py"
assert data["canonical_authority"]["class"] == "LiveVoiceSession"
assert data["canonical_authority"]["must_not_be_duplicated"] is True

states = set(data["state_machine"]["states"])
required_states = {
    "STOPPED","IDLE","LISTENING","TRANSCRIBING","THINKING",
    "SPEAKING","INTERRUPTING","RECOVERING","ERROR"
}
assert required_states.issubset(states)

transitions = {tuple(x) for x in data["state_machine"]["legal_transitions"]}
for edge in (
    ("STOPPED","IDLE"),
    ("IDLE","LISTENING"),
    ("LISTENING","TRANSCRIBING"),
    ("TRANSCRIBING","THINKING"),
    ("THINKING","SPEAKING"),
    ("SPEAKING","INTERRUPTING"),
    ("INTERRUPTING","LISTENING"),
    ("RECOVERING","LISTENING"),
):
    assert edge in transitions, edge

assert data["turn_contract"]["only_one_active_response_turn"] is True
assert data["turn_contract"]["cancellation_token_per_turn"] is True
assert data["turn_contract"]["final_user_transcript_must_use_canonical_text_ingress"] is True
assert data["turn_contract"]["voice_must_not_bypass_memory_v2_1_1"] is True

assert data["barge_in_contract"]["required"] is True
assert data["barge_in_contract"]["playback_cancel_required"] is True
assert data["barge_in_contract"]["pending_tts_cancel_required"] is True
assert data["barge_in_contract"]["stale_audio_must_not_resume"] is True

assert data["turn_end_contract"]["required"] is True
assert data["turn_end_contract"]["must_not_rely_only_on_fixed_sleep"] is True

assert data["echo_and_duplex_contract"]["aec_textual_evidence_present_in_r1"] is False
assert data["echo_and_duplex_contract"]["must_not_claim_full_duplex_without_evidence"] is True

assert data["privacy_and_permissions"]["microphone_permission_required"] is True
assert data["privacy_and_permissions"]["privacy_mode_must_disable_capture"] is True
assert data["privacy_and_permissions"]["no_background_capture_when_session_stopped"] is True
assert data["privacy_and_permissions"]["no_raw_audio_persistence_by_default"] is True

targets = data["latency_targets"]
assert 0 < targets["barge_in_playback_stop_p95_ms"] <= 250
assert 0 < targets["vad_or_turn_end_decision_p95_ms_after_speech_end"] <= 500
assert 0 < targets["first_partial_stt_p95_ms_after_speech_start"] <= 500
assert 0 < targets["first_audible_tts_p95_ms_after_turn_commit"] <= 1500

events = set(data["observability"]["required_events"])
for event in (
    "state_changed","stt_partial","stt_final","turn_committed",
    "playback_started","barge_in_detected","playback_cancelled",
    "recovery_started","voice_error"
):
    assert event in events

legacy = data["legacy_boundaries"]
assert "voice/voice_engine.py" in legacy
assert "ui/main_window.py" in legacy
assert "core/aura_core.py" in legacy
assert "memory/kernel_v2.py" in legacy

assert data["competitive_target"]["whole_product_superiority_claim"] is False
assert "working STT" in data["r2_does_not_certify"]
assert data["recommended_next"].startswith("R3 LiveVoiceSession")

print("[PASS] AURA v2.2 R2 architecture contract invariant")
print("[PASS] single LiveVoiceSession authority frozen")
print("[PASS] streaming/barge-in/turn-end/recovery/privacy contracts frozen")
print("[PASS] typed and voice conversation ingress must converge")
print("[PASS] memory v2.1.1 authority cannot be bypassed")
print("[PASS] full duplex cannot be claimed before echo rejection/AEC evidence")
print("[PASS] latency targets are explicit but not falsely certified")
