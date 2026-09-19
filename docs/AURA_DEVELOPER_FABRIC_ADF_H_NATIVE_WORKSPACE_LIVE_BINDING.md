# AURA Developer Fabric — ADF-H

ADF-H binds Developer Mode to the real AURA conversation path.

Voice already converges through `MainWindow._on_stt_finished(text) -> MainWindow._on_user_message(text)`.
ADF-H tags that origin as voice and intercepts Developer Mode commands at the start of `_on_user_message`, before intents, tools or LLM routing.

AURA keeps using its existing `MainWindow._speak_text()` TTS path. No second STT/TTS stack is created.

A native PySide6 Developer Workspace shows Developer Mode state, safety gates, recent transactions and audit-chain state. It is operational/read-only and cannot bypass ADF-F/G approvals.

Self-development receipts queue only their short spoken summary; the existing resource-status timer forwards it to native TTS.

Automated installation is followed by one manual microphone/TTS live acceptance before the Developer Fabric overlay is fully closed.


## R2 — Distinct Developer Mode visual identity

When Developer Mode is active, the normal AURA shell keeps its layout but gains a persistent amber-electric safety identity:

- floating `AURA // DEV` badge
- `DEV ACTIVE · WRITE GATED · AUDIT ON` status
- thin amber frame around the application
- optional composer placeholder `AURA DEV // Que veux-tu modifier ?` when the real composer can be identified safely
- a dynamic `auraDeveloperMode` property is exposed to a detected orb widget for future shader-specific reactions

The identity is removed when Developer Mode is disabled. No critical layout widget is renamed or replaced.
