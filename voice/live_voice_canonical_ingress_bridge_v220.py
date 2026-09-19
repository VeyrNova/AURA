
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SESSION_METHOD = "stt_final"
SESSION_TURN_PARAM = "turn_id"
SESSION_TEXT_PARAM = "text"
CORE_METHOD = "try_handle_intent"
CORE_TEXT_PARAM = "text"


@dataclass(frozen=True)
class CanonicalIngressDelivery:
    text: str
    turn_id: str
    session_result: Any
    core_result: Any


class LiveVoiceCanonicalIngressBridge:
    """Stateless final-text router.

    Authority boundary:
    - owns no microphone device,
    - owns no STT provider,
    - owns no LiveVoiceSession state,
    - owns no AuraCore state,
    - persists nothing,
    - routes one already-final transcript first through the
      LiveVoiceSession final-text boundary and then to the
      resolved AuraCore text-ingress boundary.
    """

    def __init__(self, *, live_session: Any, aura_core: Any) -> None:
        self._live_session = live_session
        self._aura_core = aura_core

    def deliver_final_text(
        self,
        *,
        turn_id: str,
        text: str,
    ) -> CanonicalIngressDelivery:
        normalized = str(text or "").strip()
        if not normalized:
            raise ValueError("final text must be non-empty")

        session_method = getattr(self._live_session, SESSION_METHOD)
        core_method = getattr(self._aura_core, CORE_METHOD)

        session_result = session_method(
            **{
                SESSION_TURN_PARAM: str(turn_id),
                SESSION_TEXT_PARAM: normalized,
            }
        )

        core_result = core_method(
            **{
                CORE_TEXT_PARAM: normalized,
            }
        )

        return CanonicalIngressDelivery(
            text=normalized,
            turn_id=str(turn_id),
            session_result=session_result,
            core_result=core_result,
        )
