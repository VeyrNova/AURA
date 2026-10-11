# Voice local PreparedAction — Lot 007

## Root cause

The PTT transcript path previously delivered only the transcript text to `NativeCoreBridge.dispatchLocalTranscript`. A local deterministic intent could create a PreparedAction, but no trusted `voice_request_id` was associated with its `action_id`. Terminal `pending_action.*` events therefore cleared the UI card without releasing the originating `VoiceController`, which remained in `THINKING`.

## Correction

The native voice bridge now emits a correlated `(transcript, voice_request_id)` signal for the production local-command path. The core bridge keeps an action-to-voice map and emits one terminal signal for `executed`, `cancelled`, `error`, or `expired`. `NativeVoiceBridge.onLocalActionTerminal` is idempotent and releases the controller to `IDLE`. Keyboard actions have no voice binding. Confirmation remains UI-only.

No STT, audio, Whisper, Piper, Gemini, Memory, System Control, temporal parser, Google, or QML redesign was made.

## Automated validation

- `tests/native/test_voice_local_prepared_action_007.py`: 12 tests covering correlation, cancel, execute, error, expiry, duplicate terminal events, keyboard isolation, wrong IDs, cross-action isolation, distinct IDs, no Gemini fallback, and signal shape.
- Voice + local command + Text Command 006 regression: **92/92 PASS**.
- Lot 1 strict: **53/53 PASS**.
- QML self-check: **PASS**.
- Controlled runs used `-B` and `PYTHONDONTWRITEBYTECODE=1`; no new bytecode observed.

## Lot 007B — production-shared transcript path (2026-10-10)

The diagnostic-only `--voice-transcript-probe` entry is enabled only with
`AURA_PTT_DIAGNOSTICS=1`; it emits the same correlated
`localTranscriptReady(text, voice_request_id)` signal as the STT worker and
does not open a microphone.

Computer Use validated the real Native QML surface:

- Voice transcript probe → local note PreparedAction → **ANNULER**: action
  `cancelled`, no note persisted, Voice returned to `IDLE`.
- Voice transcript probe → local note PreparedAction → **CONFIRMER**: exactly
  one note persisted, action `executed`, Voice returned to `IDLE`.
- The exact note was then deleted through the UI after explicit authorization;
  stable ID `d0c64f22-9c2b-4e32-a047-c4bb85c7ad32` is absent by ID and title.
- Keyboard-origin note action was cancelled in the real UI; no note persisted
  and Voice remained `IDLE`.

`LIVE_VOICE_LOCAL_CANCEL=PASS_LIVE_TRANSCRIPT_PATH`
`LIVE_VOICE_LOCAL_CONFIRM=PASS_LIVE_TRANSCRIPT_PATH`
`LIVE_TEST_DATA_CLEANUP=PASS`
`LIVE_KEYBOARD_VOICE_ISOLATION=PASS`
`VOICE_LOCAL_PREPARED_ACTION_PARITY=PASS_NATIVE_LIVE_PRODUCT_PATH`
`VOICE_LOCAL_TERMINALIZATION_BLOCKER=false`

## Live Computer Use evidence

The real native AURA window launched and remained responsive. Sounddevice devices exist, but Computer Use cannot inject controllable physical microphone audio into the production capture path: `VOICE_MIC_INPUT_CONTROLLABLE_BY_CODEX=false`, therefore `VOICE_MIC_LIVE=NOT_AVAILABLE`. No microphone PASS is claimed. No destructive live object was created during this lot.

The physical microphone remains outside Computer Use control:
`VOICE_MIC_DEVICE_PRESENT=true`, `VOICE_MIC_INPUT_CONTROLLABLE_BY_CODEX=false`,
`VOICE_MIC_LIVE=NOT_AVAILABLE`,
`VOICE_MICROPHONE_VALIDATION_GATE=NOT_AVAILABLE_EXTERNAL_CAPABILITY`.
Lot 008 has not started.
