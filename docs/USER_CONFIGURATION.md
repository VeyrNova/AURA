# User configuration

## API providers

AURA must not ship with the developer's credentials.

Each user configures their own API keys in AURA Settings / onboarding. Provider configuration should expose:

- enabled / disabled state
- configured / not configured state
- connection test
- masked credential display
- local removal/replacement of the credential

Full keys must never be printed in logs, diagnostics, screenshots, profile exports or GitHub files.

## Voice

Voice is user-selectable.

The public repository contains the voice-engine logic, but private developer voice samples/reference audio are excluded by default. Users may choose a bundled redistributable voice, XTTS voice, Chatterbox, Piper, or their own authorized voice reference where supported.

Language and voice identity are separate settings.
