"""AURA v0.7.0.15.6 adaptive RAM hysteresis for the Dual Brain hot path.

The old 88% one-shot threshold caused llama3.2:3b to be evicted immediately
although the machine was still stable.  The policy below separates warning,
soft pressure and critical pressure and uses an availability floor as a second
safety signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from config.settings import settings


class MemoryAction(str, Enum):
    KEEP_RESIDENT = "keep-resident"
    TRIM_OPTIONAL = "trim-optional"
    UNLOAD_VOICE_BRAIN = "unload-voice-brain"


@dataclass(frozen=True)
class MemoryPressureDecision:
    action: MemoryAction
    band: str
    allow_voice_prewarm: bool
    pressure_latched: bool
    reason: str


class MemoryPressureStateMachine:
    """Small hysteretic state machine owned for the ResourceGuardian lifetime."""

    def __init__(self):
        self.pressure_latched = False

    @staticmethod
    def _known_low(available_gib: float, floor: float) -> bool:
        return available_gib > 0 and available_gib <= floor

    def evaluate(
        self,
        *,
        ram_percent: float,
        available_gib: float,
        voice_brain_loaded: bool,
        xtts_hot: bool,
        predicted_with_voice_percent: float | None = None,
        predicted_available_after_gib: float | None = None,
    ) -> MemoryPressureDecision:
        ram = max(0.0, float(ram_percent))
        avail = float(available_gib)
        predicted_ram = ram if predicted_with_voice_percent is None else max(0.0, float(predicted_with_voice_percent))
        predicted_avail = avail if predicted_available_after_gib is None else float(predicted_available_after_gib)

        critical = (
            ram >= float(settings.VOICE_MEMORY_CRITICAL_PCT)
            or self._known_low(avail, float(settings.VOICE_MEMORY_HARD_MIN_AVAILABLE_GB))
        )
        predicted_critical = (
            predicted_ram >= float(settings.VOICE_MEMORY_CRITICAL_PCT)
            or self._known_low(predicted_avail, float(settings.VOICE_MEMORY_HARD_MIN_AVAILABLE_GB))
        )

        # Pixel Fidelity RC: background prewarm is a latency optimization, never
        # a reason to enter the eviction zone.  Once XTTS is hot, use a stricter
        # two-zone prediction than the emergency runtime thresholds.
        adaptive_prewarm_blocked = False
        if predicted_with_voice_percent is not None and not voice_brain_loaded and xtts_hot:
            current_soft = float(settings.VOICE_BRAIN_PREWARM_CURRENT_SOFT_PCT)
            current_cutoff = float(settings.VOICE_BRAIN_PREWARM_CURRENT_CUTOFF_PCT)
            if ram >= current_cutoff:
                adaptive_prewarm_blocked = True
            elif ram >= current_soft:
                adaptive_prewarm_blocked = (
                    predicted_ram > float(settings.VOICE_BRAIN_PREWARM_PREDICTED_SOFT_MAX_PCT)
                    or self._known_low(predicted_avail, float(settings.VOICE_BRAIN_PREWARM_SOFT_MIN_AVAILABLE_GB))
                )
            else:
                adaptive_prewarm_blocked = (
                    predicted_ram > float(settings.VOICE_BRAIN_PREWARM_PREDICTED_LOW_MAX_PCT)
                    or self._known_low(predicted_avail, float(settings.VOICE_BRAIN_PREWARM_LOW_MIN_AVAILABLE_GB))
                )

        if self.pressure_latched:
            recovered = (
                ram <= float(settings.VOICE_MEMORY_RECOVER_PCT)
                and (avail <= 0 or avail >= float(settings.VOICE_MEMORY_RECOVER_AVAILABLE_GB))
            )
            if recovered:
                self.pressure_latched = False

        if critical:
            self.pressure_latched = True
            return MemoryPressureDecision(
                MemoryAction.UNLOAD_VOICE_BRAIN if voice_brain_loaded else MemoryAction.TRIM_OPTIONAL,
                "critical",
                False,
                True,
                f"RAM critique {ram:.1f}% / disponible {avail:.2f} GiB",
            )

        if ram >= float(settings.VOICE_MEMORY_SOFT_PCT):
            action = MemoryAction.TRIM_OPTIONAL if voice_brain_loaded else MemoryAction.KEEP_RESIDENT
            return MemoryPressureDecision(
                action,
                "soft",
                bool(not self.pressure_latched and not predicted_critical and not adaptive_prewarm_blocked),
                self.pressure_latched,
                f"pression douce {ram:.1f}%",
            )

        band = "warning" if ram >= float(settings.VOICE_MEMORY_WARN_PCT) else "normal"
        allow = bool(not self.pressure_latched and not predicted_critical and not adaptive_prewarm_blocked)
        return MemoryPressureDecision(
            MemoryAction.KEEP_RESIDENT,
            band,
            allow,
            self.pressure_latched,
            f"{band} {ram:.1f}%",
        )
