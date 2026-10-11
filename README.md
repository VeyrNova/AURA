# AURA Native

AURA Native is the Qt/PySide desktop runtime for the local-first AURA assistant on Windows. This repository contains the native migration baseline, its provider adapters, local persistence, QML UI, and regression tests.

## Status

The Native migration is complete through LOT 014E. The historical Chromium implementation remains available in the repository's existing history; the Native migration is published on its own branch so that history is preserved without rewriting the public baseline.

## Requirements

- Windows 10/11
- Python 3.11+
- PySide6 6.11.2 for the desktop UI

Install the project and UI dependencies in an isolated virtual environment, then run the self-check. The `.[ui]` extra includes PySide6 and the psutil-backed Diagnostics collector; no separate psutil install is required:

```powershell
python -m pip install -e ".[ui]"
python -m aura_native
```

Launch the desktop shell with:

```powershell
python app/main.py --windowed
```

Use `--core-mode legacy` only for an explicit rollback comparison. Native mode is the default. Runtime state is stored under `%LOCALAPPDATA%\AURA-NATIVE` unless an isolated `--state-dir` is supplied.

## Validation

The `tests/native` suite covers runtime wiring, QML/PySide bridges, Music, Documents, provider policy, persistence, notifications, tray ownership, and lifecycle safety. Tests that need credentials or external services are explicitly isolated or skipped.

## Repository boundaries

This project is local-first. Credentials, OAuth tokens, runtime databases, logs, caches, test evidence, and user state are excluded from source control. Do not commit `%LOCALAPPDATA%\AURA-NATIVE`, private credentials, or files from the legacy `C:\AURA GPT version` workspace.

## License

Copyright (c) 2026 Veyr. All rights reserved. See [LICENSE](LICENSE). Public source visibility does not grant a license to copy, modify, distribute, sublicense, sell, or use the software without prior written permission from the copyright holder.
