# Native Voice foundation (audit and bounded implementation)

## Legacy evidence

The read-only audit of `C:\AURA GPT version` found the active facade in
`voice/voice_engine.py`, constructed by `core/aura_core.py`. It composes
`MicrophoneRecorder` (PortAudio/sounddevice, configured sample rate/channels),
`HybridSpeechToText` (local Whisper with optional Groq fallback), and local
XTTS/Piper output with additional cloud fallbacks. Recording is explicit
push-to-talk (`start_listening`/`stop_listening`); the automatic VAD runtime is
optional and separate. `IntentManager` and `ActionRouter` are the Legacy
routing boundary. Full live barge-in proof is **UNPROVEN** in this audit.

No Legacy file was executed or changed.

## Native lot boundary

Added a stdlib-only, offline-safe `VoiceController` with states
`IDLE → LISTENING → TRANSCRIBING → THINKING → SPEAKING` and `ERROR` recovery.
Audio/STT/TTS are injected contracts; constructors do not open devices, load
models, read credentials, start processes, or use network. `FakeAudioInput`,
`FakeSTT`, and `FakeTTS` support deterministic tests. Transcripts reuse the
existing `NativeIntentRouter`; destructive intents are parsed but dispatch is
deferred until explicit `confirm()`.

Real microphone, real STT/TTS wiring, barge-in, wake word, and Qt/QML exposure
remain deferred. The lazy `SoundDeviceAudioInput`, `WhisperSTTProvider`,
`PiperTTSProvider`, `XTTSProvider`, and `NativeVoiceBridge` contracts now
fail closed when dependencies/models are absent. `manual_voice_smoke.py` does
nothing without `--record`; no automatic hardware test was run. No cutover is
authorized.

## Local development models

The approved local-only development assets are stored outside the repository:

- `%LOCALAPPDATA%\AURA-NATIVE\models\voice\stt\Systran--faster-whisper-small`
  (`model.bin` 483,546,902 bytes plus config/tokenizer/vocabulary).
- `%LOCALAPPDATA%\AURA-NATIVE\models\voice\tts\fr_FR-siwis-medium` with
  `fr_FR-siwis-medium.onnx` (63,201,294 bytes), its JSON metadata and
  `MODEL_CARD`.

The Whisper provider uses CPU/int8 and a local path; runtime startup never
downloads models. Piper 1.8.0 (`piper-tts`) is used only as a local development
backend. Its runtime is GPL-3.0-or-later, therefore
`PIPER_DISTRIBUTION_REVIEW_REQUIRED=true`; Piper must not be bundled in a
commercial AURA installer in this lot. The Siwis model metadata reports
`fr_FR`, one speaker and 22,050 Hz; its model card attribution is retained.

`NativeVoiceBridge` is registered by the Native `app/main.py` composition and
exposed as `voiceBridge` to QML. The existing Composer microphone control uses
it only in Native mode; Legacy keeps its existing bridge. A lazy `QThread`
worker owns capture/STT/TTS calls and is closed by the Native shutdown hook.
No thread starts and no device opens at startup. Live microphone and speaker
acceptance remain manual and pending.
