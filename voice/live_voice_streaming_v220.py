
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator, Optional

from voice.live_voice_session_v220 import (
    InvalidVoiceTransition,
    LiveVoiceSession,
    StaleVoiceTurn,
    VoiceState,
)


@dataclass(frozen=True)
class StreamDecision:
    accepted: bool
    reason: str
    turn_id: Optional[str] = None
    queue: Optional[str] = None


@dataclass(frozen=True)
class StreamItem:
    turn_id: str
    sequence: int
    text: str
    kind: str


class BoundedStreamQueue:
    """Small deterministic non-blocking queue with explicit backpressure.

    The queue never silently drops new data and never blocks. Producers receive
    a False result when capacity is reached, so upstream work can pause rather
    than being consumed into an unbounded buffer.
    """

    def __init__(self, *, name: str, capacity: int) -> None:
        capacity = int(capacity)
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.name = str(name)
        self.capacity = capacity
        self._items: deque[StreamItem] = deque()
        self.high_watermark = 0
        self.rejected_puts = 0

    def __len__(self) -> int:
        return len(self._items)

    @property
    def full(self) -> bool:
        return len(self._items) >= self.capacity

    def put(self, item: StreamItem) -> bool:
        if self.full:
            self.rejected_puts += 1
            return False
        self._items.append(item)
        if len(self._items) > self.high_watermark:
            self.high_watermark = len(self._items)
        return True

    def peek(self) -> Optional[StreamItem]:
        return self._items[0] if self._items else None

    def get(self) -> Optional[StreamItem]:
        return self._items.popleft() if self._items else None

    def discard_turn(self, turn_id: str) -> int:
        kept = deque()
        removed = 0
        while self._items:
            item = self._items.popleft()
            if item.turn_id == turn_id:
                removed += 1
            else:
                kept.append(item)
        self._items = kept
        return removed

    def snapshot(self) -> tuple[StreamItem, ...]:
        return tuple(self._items)


CanonicalStreamingIngress = Callable[
    [str, str, str, Any],
    Iterable[str],
]


class LiveVoiceStreamingPipeline:
    """Bounded streaming coordinator subordinate to LiveVoiceSession.

    This object owns only ephemeral queues and iterators. Session state, active
    turn identity, cancellation truth and legal transitions remain exclusively
    owned by LiveVoiceSession.

    R5 deliberately performs no real provider, device, model or network I/O.
    """

    def __init__(
        self,
        *,
        session: LiveVoiceSession,
        canonical_streaming_ingress: CanonicalStreamingIngress,
        stt_capacity: int = 4,
        llm_capacity: int = 4,
        tts_capacity: int = 3,
    ) -> None:
        if not isinstance(session, LiveVoiceSession):
            raise TypeError("session must be LiveVoiceSession")
        if not callable(canonical_streaming_ingress):
            raise TypeError("canonical_streaming_ingress must be callable")

        self.session = session
        self._canonical_streaming_ingress = canonical_streaming_ingress

        self.stt_queue = BoundedStreamQueue(name="stt", capacity=stt_capacity)
        self.llm_queue = BoundedStreamQueue(name="llm", capacity=llm_capacity)
        self.tts_queue = BoundedStreamQueue(name="tts", capacity=tts_capacity)

        self._stream_iterators: dict[str, Iterator[str]] = {}
        self._stream_exhausted: set[str] = set()
        self._llm_first_token_seen: set[str] = set()
        self._tts_first_chunk_seen: set[str] = set()
        self._playback_started_seen: set[str] = set()
        self._item_sequence = 0

    def _next_item(
        self,
        *,
        turn_id: str,
        text: str,
        kind: str,
    ) -> StreamItem:
        self._item_sequence += 1
        return StreamItem(
            turn_id=turn_id,
            sequence=self._item_sequence,
            text=str(text),
            kind=str(kind),
        )

    def _active_turn(self, turn_id: str):
        turn = self.session.active_turn
        if turn is None or turn.turn_id != turn_id:
            raise StaleVoiceTurn(
                f"stale turn {turn_id}; no matching active turn"
            )
        if turn.cancellation.cancelled:
            raise StaleVoiceTurn(f"turn {turn_id} is cancelled")
        return turn

    def begin_user_turn(self) -> str:
        return self.session.speech_started()

    def push_stt_partial(
        self,
        turn_id: str,
        text: str,
    ) -> StreamDecision:
        try:
            self._active_turn(turn_id)
            if self.session.state is not VoiceState.TRANSCRIBING:
                raise InvalidVoiceTransition(
                    "STT partial requires TRANSCRIBING"
                )
            item = self._next_item(
                turn_id=turn_id,
                text=text,
                kind="stt_partial",
            )
            if not self.stt_queue.put(item):
                return StreamDecision(
                    False,
                    "stt_backpressure",
                    turn_id,
                    "stt",
                )
            self.session.stt_partial(text, turn_id=turn_id)
            return StreamDecision(
                True,
                "stt_partial_buffered",
                turn_id,
                "stt",
            )
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return StreamDecision(
                False,
                "stale_or_invalid_stt_partial",
                turn_id,
                "stt",
            )

    def consume_stt_partial(
        self,
        turn_id: str,
    ) -> Optional[StreamItem]:
        item = self.stt_queue.peek()
        if item is None:
            return None
        if item.turn_id != turn_id:
            return None
        return self.stt_queue.get()

    def commit_stt_final(
        self,
        turn_id: str,
        text: str,
    ) -> StreamDecision:
        try:
            turn = self._active_turn(turn_id)
            final_text = self.session.stt_final(text, turn_id=turn_id)
            committed_text = self.session.commit_turn(turn_id=turn_id)

            iterable = self._canonical_streaming_ingress(
                committed_text,
                self.session.session_id,
                turn_id,
                turn.cancellation,
            )
            self._stream_iterators[turn_id] = iter(iterable)
            self._stream_exhausted.discard(turn_id)
            return StreamDecision(
                True,
                "canonical_stream_opened",
                turn_id,
                "llm",
            )
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return StreamDecision(
                False,
                "stale_or_duplicate_stt_final",
                turn_id,
                "llm",
            )
        except Exception as exc:
            try:
                self.session.recover(
                    reason=f"canonical_stream_error:{type(exc).__name__}",
                    resume_listening=True,
                )
            except Exception:
                pass
            self._clear_turn_buffers(turn_id)
            return StreamDecision(
                False,
                "canonical_stream_error",
                turn_id,
                "llm",
            )

    def pump_llm_once(
        self,
        turn_id: str,
    ) -> StreamDecision:
        try:
            self._active_turn(turn_id)
        except StaleVoiceTurn:
            return StreamDecision(
                False,
                "stale_llm_turn",
                turn_id,
                "llm",
            )

        if self.session.state not in {
            VoiceState.THINKING,
            VoiceState.SPEAKING,
        }:
            return StreamDecision(
                False,
                "invalid_llm_state",
                turn_id,
                "llm",
            )

        if self.llm_queue.full:
            return StreamDecision(
                False,
                "llm_backpressure",
                turn_id,
                "llm",
            )

        iterator = self._stream_iterators.get(turn_id)
        if iterator is None:
            return StreamDecision(
                False,
                "no_canonical_stream",
                turn_id,
                "llm",
            )

        if turn_id in self._stream_exhausted:
            return StreamDecision(
                False,
                "llm_stream_exhausted",
                turn_id,
                "llm",
            )

        try:
            chunk = next(iterator)
        except StopIteration:
            self._stream_exhausted.add(turn_id)
            return StreamDecision(
                True,
                "llm_stream_eof",
                turn_id,
                "llm",
            )
        except Exception as exc:
            try:
                self.session.recover(
                    reason=f"llm_stream_error:{type(exc).__name__}",
                    resume_listening=True,
                )
            except Exception:
                pass
            self._clear_turn_buffers(turn_id)
            return StreamDecision(
                False,
                "llm_stream_error",
                turn_id,
                "llm",
            )

        text = str(chunk or "")
        if not text:
            return StreamDecision(
                True,
                "empty_llm_chunk_ignored",
                turn_id,
                "llm",
            )

        item = self._next_item(
            turn_id=turn_id,
            text=text,
            kind="llm_text",
        )
        if not self.llm_queue.put(item):
            # Defensive only; full was checked before advancing upstream.
            return StreamDecision(
                False,
                "llm_backpressure",
                turn_id,
                "llm",
            )

        if turn_id not in self._llm_first_token_seen:
            self.session.llm_first_token(turn_id=turn_id)
            self._llm_first_token_seen.add(turn_id)

        return StreamDecision(
            True,
            "llm_chunk_buffered",
            turn_id,
            "llm",
        )

    def promote_llm_to_tts(
        self,
        turn_id: str,
    ) -> StreamDecision:
        try:
            self._active_turn(turn_id)
        except StaleVoiceTurn:
            return StreamDecision(
                False,
                "stale_tts_turn",
                turn_id,
                "tts",
            )

        item = self.llm_queue.peek()
        if item is None:
            return StreamDecision(
                False,
                "llm_queue_empty",
                turn_id,
                "llm",
            )
        if item.turn_id != turn_id:
            return StreamDecision(
                False,
                "llm_head_belongs_to_other_turn",
                turn_id,
                "llm",
            )
        if self.tts_queue.full:
            # Crucial: do not pop the LLM queue when downstream is full.
            return StreamDecision(
                False,
                "tts_backpressure",
                turn_id,
                "tts",
            )

        item = self.llm_queue.get()
        assert item is not None
        tts_item = StreamItem(
            turn_id=item.turn_id,
            sequence=item.sequence,
            text=item.text,
            kind="tts_text",
        )
        accepted = self.tts_queue.put(tts_item)
        if not accepted:
            raise RuntimeError("tts queue changed after capacity check")

        if self.session.state is VoiceState.THINKING:
            self.session.begin_speaking(turn_id=turn_id)

        return StreamDecision(
            True,
            "llm_promoted_to_tts",
            turn_id,
            "tts",
        )

    def consume_tts_chunk(
        self,
        turn_id: str,
    ) -> Optional[StreamItem]:
        try:
            self._active_turn(turn_id)
        except StaleVoiceTurn:
            return None

        item = self.tts_queue.peek()
        if item is None or item.turn_id != turn_id:
            return None

        item = self.tts_queue.get()
        assert item is not None

        if turn_id not in self._tts_first_chunk_seen:
            self.session.tts_first_chunk(turn_id=turn_id)
            self._tts_first_chunk_seen.add(turn_id)

        return item

    def mark_playback_started(
        self,
        turn_id: str,
    ) -> StreamDecision:
        try:
            self._active_turn(turn_id)
            if turn_id in self._playback_started_seen:
                return StreamDecision(
                    True,
                    "playback_already_started",
                    turn_id,
                    "tts",
                )
            self.session.playback_started(turn_id=turn_id)
            self._playback_started_seen.add(turn_id)
            return StreamDecision(
                True,
                "playback_started",
                turn_id,
                "tts",
            )
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return StreamDecision(
                False,
                "stale_or_invalid_playback_start",
                turn_id,
                "tts",
            )

    def complete_if_drained(
        self,
        turn_id: str,
    ) -> StreamDecision:
        try:
            self._active_turn(turn_id)
        except StaleVoiceTurn:
            return StreamDecision(
                False,
                "stale_completion",
                turn_id,
                "tts",
            )

        if turn_id not in self._stream_exhausted:
            return StreamDecision(
                False,
                "llm_stream_not_finished",
                turn_id,
                "llm",
            )
        if any(x.turn_id == turn_id for x in self.llm_queue.snapshot()):
            return StreamDecision(
                False,
                "llm_queue_not_drained",
                turn_id,
                "llm",
            )
        if any(x.turn_id == turn_id for x in self.tts_queue.snapshot()):
            return StreamDecision(
                False,
                "tts_queue_not_drained",
                turn_id,
                "tts",
            )

        if self.session.state is VoiceState.THINKING:
            self.session.recover(
                reason="empty_stream_response",
                resume_listening=True,
            )
            self._clear_turn_buffers(turn_id)
            return StreamDecision(
                False,
                "empty_stream_response",
                turn_id,
                "llm",
            )

        if self.session.state is not VoiceState.SPEAKING:
            return StreamDecision(
                False,
                "invalid_completion_state",
                turn_id,
                "tts",
            )

        self.session.response_completed(turn_id=turn_id)
        self._clear_turn_buffers(turn_id)
        return StreamDecision(
            True,
            "streaming_turn_completed",
            turn_id,
            "tts",
        )

    def request_barge_in(
        self,
        *,
        reason: str = "user_speech",
    ) -> StreamDecision:
        active = self.session.active_turn
        if active is None:
            return StreamDecision(
                False,
                "no_active_turn_for_barge_in",
                None,
                None,
            )
        turn_id = active.turn_id
        try:
            interrupted = self.session.request_barge_in(reason=reason)
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return StreamDecision(
                False,
                "barge_in_rejected",
                turn_id,
                None,
            )

        self._clear_turn_buffers(interrupted)
        return StreamDecision(
            True,
            "barge_in_streams_cancelled",
            interrupted,
            None,
        )

    def _clear_turn_buffers(self, turn_id: str) -> dict[str, int]:
        removed = {
            "stt": self.stt_queue.discard_turn(turn_id),
            "llm": self.llm_queue.discard_turn(turn_id),
            "tts": self.tts_queue.discard_turn(turn_id),
        }
        self._stream_iterators.pop(turn_id, None)
        self._stream_exhausted.discard(turn_id)
        self._llm_first_token_seen.discard(turn_id)
        self._tts_first_chunk_seen.discard(turn_id)
        self._playback_started_seen.discard(turn_id)
        return removed

    def stop(self, *, reason: str = "session_stop") -> None:
        active = self.session.active_turn
        if active is not None:
            self._clear_turn_buffers(active.turn_id)
        self.session.stop(reason=reason)
