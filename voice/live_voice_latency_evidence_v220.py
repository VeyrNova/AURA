
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil
from typing import Any, Optional


class LatencyMetric(str, Enum):
    FIRST_PARTIAL_STT = "first_partial_stt_ms"
    TURN_END_DECISION = "turn_end_decision_ms"
    FIRST_AUDIO = "first_audio_ms"
    BARGE_IN_STOP = "barge_in_stop_ms"
    STATE_EVENT = "state_event_ms"


@dataclass(frozen=True)
class LatencyTargets:
    first_partial_stt_ms: int = 500
    turn_end_decision_ms: int = 500
    first_audio_ms: int = 1500
    barge_in_stop_ms: int = 250
    state_event_ms: int = 50

    def threshold_for(self, metric: LatencyMetric) -> int:
        return {
            LatencyMetric.FIRST_PARTIAL_STT: int(self.first_partial_stt_ms),
            LatencyMetric.TURN_END_DECISION: int(self.turn_end_decision_ms),
            LatencyMetric.FIRST_AUDIO: int(self.first_audio_ms),
            LatencyMetric.BARGE_IN_STOP: int(self.barge_in_stop_ms),
            LatencyMetric.STATE_EVENT: int(self.state_event_ms),
        }[LatencyMetric(metric)]


@dataclass(frozen=True)
class LatencySample:
    metric: str
    value_ms: int
    turn_id: Optional[str]
    correlation_id: Optional[str]
    start_event: str
    end_event: str


@dataclass(frozen=True)
class MetricEvaluation:
    metric: str
    sample_count: int
    p95_ms: Optional[int]
    threshold_ms: int
    ready: bool
    passed: bool
    reason: str


class LiveVoiceLatencyEvidence:
    """External-timestamp latency evidence collector.

    This component never reads a clock and never sleeps. Runtime callers must
    supply monotonic timestamps taken at the actual milestone boundaries.

    It owns evidence only. It does not own LiveVoiceSession state, active turn
    identity, cancellation, provider lifecycle, audio devices or model state.
    """

    _TURN_EVENT_NAMES = {
        "speech_started",
        "stt_partial",
        "speech_ended_candidate",
        "turn_end_ready",
        "turn_committed",
        "audio_output_started",
        "barge_in_detected",
        "playback_cancelled",
    }

    def __init__(
        self,
        *,
        targets: Optional[LatencyTargets] = None,
        max_samples_per_metric: int = 512,
    ) -> None:
        max_samples_per_metric = int(max_samples_per_metric)
        if max_samples_per_metric < 20:
            raise ValueError("max_samples_per_metric must be >= 20")

        self.targets = targets or LatencyTargets()
        self.max_samples_per_metric = max_samples_per_metric
        self._turn_events: dict[str, dict[str, int]] = {}
        self._transition_events: dict[str, dict[str, int]] = {}
        self._samples: dict[LatencyMetric, list[LatencySample]] = {
            metric: [] for metric in LatencyMetric
        }

    @staticmethod
    def _validate_timestamp(at_ms: int) -> int:
        at_ms = int(at_ms)
        if at_ms < 0:
            raise ValueError("at_ms must be >= 0")
        return at_ms

    def _append_sample(
        self,
        metric: LatencyMetric,
        *,
        value_ms: int,
        turn_id: Optional[str],
        correlation_id: Optional[str],
        start_event: str,
        end_event: str,
    ) -> None:
        value_ms = int(value_ms)
        if value_ms < 0:
            raise ValueError(
                f"negative latency for {metric.value}: {value_ms} ms"
            )
        bucket = self._samples[metric]
        bucket.append(
            LatencySample(
                metric=metric.value,
                value_ms=value_ms,
                turn_id=turn_id,
                correlation_id=correlation_id,
                start_event=start_event,
                end_event=end_event,
            )
        )
        if len(bucket) > self.max_samples_per_metric:
            del bucket[: len(bucket) - self.max_samples_per_metric]

    def _record_turn_event(
        self,
        *,
        turn_id: str,
        event: str,
        at_ms: int,
    ) -> bool:
        turn_id = str(turn_id)
        event = str(event)
        at_ms = self._validate_timestamp(at_ms)

        if event not in self._TURN_EVENT_NAMES:
            raise ValueError(f"unsupported turn latency event: {event}")

        events = self._turn_events.setdefault(turn_id, {})

        # First milestone wins. Retries/duplicates cannot rewrite latency history.
        if event in events:
            return False

        # Per-turn timestamps may be sparse, but a newly observed milestone may
        # never precede an already recorded milestone in the same turn.
        if events and at_ms < max(events.values()):
            raise ValueError(
                f"non-monotonic latency evidence for turn {turn_id}: "
                f"{event}@{at_ms} < previous@{max(events.values())}"
            )

        events[event] = at_ms
        self._derive_turn_samples(turn_id, event)
        return True

    def observe_turn_event(
        self,
        *,
        turn_id: str,
        event: str,
        at_ms: int,
    ) -> bool:
        return self._record_turn_event(
            turn_id=turn_id,
            event=event,
            at_ms=at_ms,
        )

    def observe_transition_requested(
        self,
        *,
        correlation_id: str,
        at_ms: int,
    ) -> bool:
        correlation_id = str(correlation_id)
        at_ms = self._validate_timestamp(at_ms)
        events = self._transition_events.setdefault(correlation_id, {})
        if "requested" in events:
            return False
        if "changed" in events and at_ms > events["changed"]:
            raise ValueError("transition request cannot follow state_changed")
        events["requested"] = at_ms
        self._derive_transition_sample(correlation_id)
        return True

    def observe_state_changed(
        self,
        *,
        correlation_id: str,
        at_ms: int,
    ) -> bool:
        correlation_id = str(correlation_id)
        at_ms = self._validate_timestamp(at_ms)
        events = self._transition_events.setdefault(correlation_id, {})
        if "changed" in events:
            return False
        if "requested" in events and at_ms < events["requested"]:
            raise ValueError("state_changed precedes transition request")
        events["changed"] = at_ms
        self._derive_transition_sample(correlation_id)
        return True

    def _derive_turn_samples(self, turn_id: str, event: str) -> None:
        events = self._turn_events[turn_id]

        if event == "stt_partial" and "speech_started" in events:
            self._append_sample(
                LatencyMetric.FIRST_PARTIAL_STT,
                value_ms=events["stt_partial"] - events["speech_started"],
                turn_id=turn_id,
                correlation_id=None,
                start_event="speech_started",
                end_event="stt_partial",
            )

        if event == "turn_end_ready" and "speech_ended_candidate" in events:
            self._append_sample(
                LatencyMetric.TURN_END_DECISION,
                value_ms=(
                    events["turn_end_ready"]
                    - events["speech_ended_candidate"]
                ),
                turn_id=turn_id,
                correlation_id=None,
                start_event="speech_ended_candidate",
                end_event="turn_end_ready",
            )

        if event == "audio_output_started" and "turn_committed" in events:
            self._append_sample(
                LatencyMetric.FIRST_AUDIO,
                value_ms=(
                    events["audio_output_started"]
                    - events["turn_committed"]
                ),
                turn_id=turn_id,
                correlation_id=None,
                start_event="turn_committed",
                end_event="audio_output_started",
            )

        if event == "playback_cancelled" and "barge_in_detected" in events:
            self._append_sample(
                LatencyMetric.BARGE_IN_STOP,
                value_ms=(
                    events["playback_cancelled"]
                    - events["barge_in_detected"]
                ),
                turn_id=turn_id,
                correlation_id=None,
                start_event="barge_in_detected",
                end_event="playback_cancelled",
            )

    def _derive_transition_sample(self, correlation_id: str) -> None:
        events = self._transition_events[correlation_id]
        if "requested" not in events or "changed" not in events:
            return
        if events.get("_sampled"):
            return
        self._append_sample(
            LatencyMetric.STATE_EVENT,
            value_ms=events["changed"] - events["requested"],
            turn_id=None,
            correlation_id=correlation_id,
            start_event="state_transition_requested",
            end_event="state_changed",
        )
        events["_sampled"] = 1

    def samples(self, metric: LatencyMetric) -> tuple[LatencySample, ...]:
        return tuple(self._samples[LatencyMetric(metric)])

    @staticmethod
    def _nearest_rank_p95(values: list[int]) -> Optional[int]:
        if not values:
            return None
        ordered = sorted(int(v) for v in values)
        rank = max(1, ceil(0.95 * len(ordered)))
        return ordered[rank - 1]

    def evaluate(
        self,
        metric: LatencyMetric,
        *,
        min_samples: int = 20,
    ) -> MetricEvaluation:
        metric = LatencyMetric(metric)
        min_samples = int(min_samples)
        if min_samples < 1:
            raise ValueError("min_samples must be >= 1")

        bucket = self._samples[metric]
        threshold = self.targets.threshold_for(metric)
        p95 = self._nearest_rank_p95([s.value_ms for s in bucket])
        ready = len(bucket) >= min_samples

        if not ready:
            return MetricEvaluation(
                metric=metric.value,
                sample_count=len(bucket),
                p95_ms=p95,
                threshold_ms=threshold,
                ready=False,
                passed=False,
                reason="insufficient_samples",
            )

        assert p95 is not None
        passed = p95 <= threshold
        return MetricEvaluation(
            metric=metric.value,
            sample_count=len(bucket),
            p95_ms=p95,
            threshold_ms=threshold,
            ready=True,
            passed=passed,
            reason="within_target" if passed else "target_exceeded",
        )

    def evaluate_all(
        self,
        *,
        min_samples: int = 20,
    ) -> dict[str, MetricEvaluation]:
        return {
            metric.value: self.evaluate(metric, min_samples=min_samples)
            for metric in LatencyMetric
        }

    def all_ready_and_passing(
        self,
        *,
        min_samples: int = 20,
    ) -> bool:
        evaluations = self.evaluate_all(min_samples=min_samples)
        return all(item.ready and item.passed for item in evaluations.values())

    def snapshot(self) -> dict[str, Any]:
        return {
            "targets_ms": {
                metric.value: self.targets.threshold_for(metric)
                for metric in LatencyMetric
            },
            "sample_counts": {
                metric.value: len(self._samples[metric])
                for metric in LatencyMetric
            },
            "p95_ms": {
                metric.value: self._nearest_rank_p95(
                    [s.value_ms for s in self._samples[metric]]
                )
                for metric in LatencyMetric
            },
        }
