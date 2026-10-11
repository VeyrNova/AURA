# Changelog

## 0.1.0 — AURA Native release candidate

- Replaced the desktop shell with the Native Qt/QML and PySide runtime.
- Added local Music playback and Documents search/open parity.
- Added local persistence, reminders, notifications, background ownership, system-tray policy, and lifecycle-safe shutdown.
- Added explicit Native defaulting with `--core-mode legacy` rollback support.
- Added provider adapters with truthful unavailable, authentication, and scope states.
- Added psutil to the documented desktop UI installation so Diagnostics reports real CPU, memory, and disk metrics.
- Validated the release gate with 32 passing tests and 1 legitimate expected skip.
