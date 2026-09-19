
from __future__ import annotations

from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_latency_evidence_v220 import (
    LatencyMetric,
    LatencyTargets,
    LiveVoiceLatencyEvidence,
)


def add_complete_sample(
    collector,
    *,
    turn_id,
    base,
    stt_ms,
    turn_end_ms,
    first_audio_ms,
    barge_stop_ms,
    state_ms,
):
    collector.observe_turn_event(
        turn_id=turn_id,
        event="speech_started",
        at_ms=base,
    )
    collector.observe_turn_event(
        turn_id=turn_id,
        event="stt_partial",
        at_ms=base + stt_ms,
    )

    speech_end = base + 1000
    collector.observe_turn_event(
        turn_id=turn_id,
        event="speech_ended_candidate",
        at_ms=speech_end,
    )
    collector.observe_turn_event(
        turn_id=turn_id,
        event="turn_end_ready",
        at_ms=speech_end + turn_end_ms,
    )

    commit_at = speech_end + turn_end_ms + 1
    collector.observe_turn_event(
        turn_id=turn_id,
        event="turn_committed",
        at_ms=commit_at,
    )
    collector.observe_turn_event(
        turn_id=turn_id,
        event="audio_output_started",
        at_ms=commit_at + first_audio_ms,
    )

    # Keep turn evidence monotonic even when the synthetic first-audio delay is
    # large: barge-in occurs after first audio has started.
    barge_at = commit_at + first_audio_ms + 100
    collector.observe_turn_event(
        turn_id=turn_id,
        event="barge_in_detected",
        at_ms=barge_at,
    )
    collector.observe_turn_event(
        turn_id=turn_id,
        event="playback_cancelled",
        at_ms=barge_at + barge_stop_ms,
    )

    correlation_id = f"{turn_id}:transition"
    collector.observe_transition_requested(
        correlation_id=correlation_id,
        at_ms=base + 10,
    )
    collector.observe_state_changed(
        correlation_id=correlation_id,
        at_ms=base + 10 + state_ms,
    )


targets = LatencyTargets()
assert targets.first_partial_stt_ms == 500
assert targets.turn_end_decision_ms == 500
assert targets.first_audio_ms == 1500
assert targets.barge_in_stop_ms == 250
assert targets.state_event_ms == 50

# ------------------------------------------------------------------
# PASS dataset: 20 complete synthetic samples, all inside contract targets.
# ------------------------------------------------------------------
good = LiveVoiceLatencyEvidence(
    targets=targets,
    max_samples_per_metric=64,
)

for idx in range(20):
    add_complete_sample(
        good,
        turn_id=f"GOOD-{idx:02d}",
        base=idx * 10000,
        stt_ms=180 + (idx % 3),
        turn_end_ms=420,
        first_audio_ms=900 + (idx % 5),
        barge_stop_ms=120 + (idx % 4),
        state_ms=10 + (idx % 2),
    )

evaluations = good.evaluate_all(min_samples=20)
for metric_name, evaluation in evaluations.items():
    assert evaluation.ready is True, metric_name
    assert evaluation.passed is True, metric_name

assert evaluations["first_partial_stt_ms"].p95_ms <= 500
assert evaluations["turn_end_decision_ms"].p95_ms == 420
assert evaluations["first_audio_ms"].p95_ms <= 1500
assert evaluations["barge_in_stop_ms"].p95_ms <= 250
assert evaluations["state_event_ms"].p95_ms <= 50
assert good.all_ready_and_passing(min_samples=20) is True

# First milestone wins: duplicate STT partial must not rewrite latency.
before = good.samples(LatencyMetric.FIRST_PARTIAL_STT)[0]
accepted = good.observe_turn_event(
    turn_id="GOOD-00",
    event="stt_partial",
    at_ms=999999,
)
after = good.samples(LatencyMetric.FIRST_PARTIAL_STT)[0]
assert accepted is False
assert after == before

# ------------------------------------------------------------------
# Missing evidence must never produce a false PASS.
# ------------------------------------------------------------------
incomplete = LiveVoiceLatencyEvidence()
incomplete.observe_turn_event(
    turn_id="INC-1",
    event="speech_started",
    at_ms=0,
)
incomplete.observe_turn_event(
    turn_id="INC-1",
    event="stt_partial",
    at_ms=200,
)

partial_eval = incomplete.evaluate(
    LatencyMetric.FIRST_PARTIAL_STT,
    min_samples=20,
)
assert partial_eval.ready is False
assert partial_eval.passed is False
assert partial_eval.reason == "insufficient_samples"
assert incomplete.all_ready_and_passing(min_samples=20) is False

# ------------------------------------------------------------------
# FAIL dataset proves evaluator detects real threshold breaches.
# ------------------------------------------------------------------
bad = LiveVoiceLatencyEvidence(
    targets=targets,
    max_samples_per_metric=64,
)

for idx in range(20):
    add_complete_sample(
        bad,
        turn_id=f"BAD-{idx:02d}",
        base=idx * 20000,
        stt_ms=650,
        turn_end_ms=700,
        first_audio_ms=1900,
        barge_stop_ms=400,
        state_ms=90,
    )

bad_eval = bad.evaluate_all(min_samples=20)
for metric_name, evaluation in bad_eval.items():
    assert evaluation.ready is True, metric_name
    assert evaluation.passed is False, metric_name
    assert evaluation.reason == "target_exceeded", metric_name
assert bad.all_ready_and_passing(min_samples=20) is False

# ------------------------------------------------------------------
# Nearest-rank P95 semantics: one extreme outlier in 20 samples is the 20th
# value, so the 95th percentile remains the 19th ordered value.
# ------------------------------------------------------------------
p95_probe = LiveVoiceLatencyEvidence(max_samples_per_metric=64)
for idx in range(20):
    value = 100 if idx < 19 else 9999
    turn_id = f"P95-{idx:02d}"
    p95_probe.observe_turn_event(
        turn_id=turn_id,
        event="speech_started",
        at_ms=idx * 20000,
    )
    p95_probe.observe_turn_event(
        turn_id=turn_id,
        event="stt_partial",
        at_ms=idx * 20000 + value,
    )

probe_eval = p95_probe.evaluate(
    LatencyMetric.FIRST_PARTIAL_STT,
    min_samples=20,
)
assert probe_eval.ready is True
assert probe_eval.p95_ms == 100
assert probe_eval.passed is True

# ------------------------------------------------------------------
# Out-of-order evidence must fail closed.
# ------------------------------------------------------------------
ordering = LiveVoiceLatencyEvidence()
ordering.observe_turn_event(
    turn_id="ORDER-1",
    event="speech_started",
    at_ms=100,
)
ordering.observe_turn_event(
    turn_id="ORDER-1",
    event="stt_partial",
    at_ms=200,
)
try:
    ordering.observe_turn_event(
        turn_id="ORDER-1",
        event="turn_committed",
        at_ms=150,
    )
except ValueError:
    pass
else:
    raise AssertionError("out-of-order turn evidence accepted")

ordering.observe_transition_requested(
    correlation_id="transition-1",
    at_ms=1000,
)
try:
    ordering.observe_state_changed(
        correlation_id="transition-1",
        at_ms=999,
    )
except ValueError:
    pass
else:
    raise AssertionError("out-of-order transition evidence accepted")

# ------------------------------------------------------------------
# Static authority guard: no clocks/sleeps/provider/audio/network imports and
# no duplicate session-state ownership.
# ------------------------------------------------------------------
module_path = ROOT / "voice" / "live_voice_latency_evidence_v220.py"
source = module_path.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(source, filename=str(module_path))

imports = set()
call_names = set()
class_names = set()
self_attrs = set()

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.add(node.module.split(".", 1)[0].casefold())
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            call_names.add(node.func.id.casefold())
        elif isinstance(node.func, ast.Attribute):
            call_names.add(node.func.attr.casefold())
    elif isinstance(node, ast.ClassDef):
        class_names.add(node.name)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                self_attrs.add(target.attr)

for forbidden_import in (
    "time",
    "asyncio",
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "whisper",
    "subprocess",
    "socket",
):
    assert forbidden_import not in imports, forbidden_import

assert "sleep" not in call_names
assert "monotonic" not in call_names
assert "perf_counter" not in call_names
assert "LiveVoiceSession" not in class_names

for forbidden_attr in (
    "state",
    "_state",
    "_active_turn",
    "_turn_counter",
    "cancellation",
):
    assert forbidden_attr not in self_attrs, forbidden_attr

print("[PASS] AURA v2.2 R7 synthetic latency/evidence invariant")
print("[PASS] R2 latency thresholds encoded exactly")
print("[PASS] 20-sample good dataset passes every P95 target")
print("[PASS] 20-sample bad dataset fails every P95 target")
print("[PASS] incomplete evidence cannot produce a false PASS")
print("[PASS] duplicate milestone cannot rewrite first latency sample")
print("[PASS] nearest-rank P95 calculation verified")
print("[PASS] out-of-order timestamps fail closed")
print("[PASS] collector owns evidence only, not LiveVoiceSession state")
print("[PASS] no real clock/sleep/microphone/audio/network/model/provider I/O")
