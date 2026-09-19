# AURA v0.5 — Voice Foundation

## Architecture

```text
Explicit push-to-talk
        |
MicrophoneRecorder (sounddevice, 16 kHz float32)
        |
FasterWhisperSTT (local model)
        |
Existing intent/router/LLM pipeline
        |
AURA response
        |
PiperTTS (local neural voice)
        |
Windows audio output
```

## Security / privacy invariants

- No wake word in v0.5.
- No continuous listening.
- Microphone capture begins only from the UI button.
- Captured microphone audio is kept in RAM and discarded after transcription.
- Runtime STT model auto-download is disabled by default.
- TTS model is loaded from a local path.
- Voice is a presentation/input layer; it cannot bypass ActionRouter or SecurityPolicyEngine.
- Pressing push-to-talk stops current TTS playback before opening the microphone.
