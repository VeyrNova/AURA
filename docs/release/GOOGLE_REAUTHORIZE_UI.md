# Google reauthorization UI fix — 2026-10-03

`ProviderIntegrationsView.qml` now exposes a separate `RÉAUTORISER GOOGLE` action in the Google Workspace card. It calls only `NativeCoreBridge.startGoogleWorkspaceOAuth()`, which reuses the existing `GoogleAuthProvider.connect()` flow. `IMPORTER UN CLIENT OAUTH` remains a separate file-picker/import action. The UI disables the reauthorization action while the workspace status is connecting and displays a safe in-progress label. No token, credential payload or OAuth error is shown.

Targeted Settings/Google tests pass. Fresh global run: 473 discovered, 223 executed, 250 excluded; 223 PASS, 0 FAIL, 0 import failures, 0 timeouts; ADF 35/35. No browser or consent flow was launched by this validation. The user must click the new button and complete Google consent manually before the Gmail READ smoke. BAT/default legacy mode unchanged; no cutover.
