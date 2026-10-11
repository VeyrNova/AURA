# AURA

AURA is a Native Windows AI assistant built with Qt/QML and PySide. It is local-first and provides a desktop shell for conversation, Music, Documents, reminders, diagnostics, local productivity, and selected provider integrations.

## Status

Version 0.1.0 is the current published Native release. The current architecture uses a Native Qt/QML runtime and Python services; the explicit `--core-mode legacy` option remains available for rollback comparison. This release is distributed as source; no Windows executable or installer is included.

## Requirements

- Windows 10/11
- Python 3.11+
- PySide6 6.11.2 for the desktop UI

The supported desktop target is Windows 10/11. The project requires Python 3.11 or newer.

Install the project and UI dependencies in an isolated virtual environment, then run the self-check. The `.[ui]` extra includes PySide6 and the psutil-backed Diagnostics collector; no separate psutil install is required:

```powershell
python -m pip install -e ".[ui]"
python -m aura_native --self-check --state-dir "$env:TEMP\\aura-native-selfcheck"
```

Launch the desktop shell with:

```powershell
python app/main.py --windowed
```

Use `--core-mode legacy` only for an explicit rollback comparison. Native mode is the default. Runtime state is stored under `%LOCALAPPDATA%\AURA-NATIVE` unless an isolated `--state-dir` is supplied.

## Capabilities

- Native Qt/QML desktop UI with Python service composition
- Local Music playback and Documents search/open flows
- Local reminders, notifications, background ownership, and system-tray policy
- Local persistence with lifecycle and rollback safety
- Diagnostics with CPU, memory, and disk metrics when the desktop dependencies are installed
- Provider adapters with explicit unavailable, authentication, and scope states

External provider access and optional telemetry depend on local configuration and credentials; no credentials are included in this repository.

## Validation

The `tests/native` suite covers runtime wiring, QML/PySide bridges, Music, Documents, provider policy, persistence, notifications, tray ownership, and lifecycle safety. Tests that need credentials or external services are explicitly isolated or skipped.

## Project structure

- `app/` — desktop entry point and QML UI
- `src/aura_native/` — Native services, contracts, adapters, and Qt bridges
- `tests/native/` — focused Native regression tests
- `docs/` — migration and handoff documentation

## Current limitations

The project is Windows-focused, some provider features require user configuration, and unsupported hardware telemetry is reported as unavailable rather than synthesized. Windows executable packaging is planned for a later dedicated release effort; the historical Chromium lineage remains in Git history.

## Repository boundaries

This project is local-first. Credentials, OAuth tokens, runtime databases, logs, caches, test evidence, and user state are excluded from source control. Do not commit `%LOCALAPPDATA%\AURA-NATIVE`, private credentials, or files from the legacy `C:\AURA GPT version` workspace.

## License

Copyright (c) 2026 Veyr. All rights reserved. See [LICENSE](LICENSE). Public source visibility does not grant a license to copy, modify, distribute, sublicense, sell, or use the software without prior written permission from the copyright holder.
