# Runtime Parity 09 — Gmail READ scope enablement

Scope owner: `src/aura_native/google/auth.py`, `GoogleOAuthConfig.scopes`. The single native scope set is now Calendar + Tasks + `https://www.googleapis.com/auth/gmail.readonly`. No Gmail write scope (`gmail.modify`, `gmail.compose`, `gmail.send`, `gmail.labels`, `mail.google.com`) is present.

The existing `GoogleAuthProvider` and its existing credential store remain the only identity path. Existing Calendar/Tasks consent remains authenticated for those domains; `GmailMailBackend` independently checks the actually granted scope and returns `PERMISSION_REQUIRED` when `gmail.readonly` is absent. No OAuth loop or automatic reauthorization was started.

The existing explicit reconnect action reuses `GoogleAuthProvider.connect()` to request the newly configured scope when an old token is present but incomplete. Startup still never invokes it implicitly.

Production composition selects `GmailMailBackend` only when the same authenticated provider reports the Gmail read scope. Otherwise the isolated/offline composition remains deterministic. The backend advertises read capabilities only and rejects `send`/`create_draft` with `WRITE_NOT_SUPPORTED`. MailService and MailView contracts are unchanged.

No production smoke was attempted: the validation state has no authorized Gmail identity, and no consent flow was triggered. Status is `GMAIL_PRODUCTION_READ=PERMISSION_REQUIRED` / `AUTH_NOT_AVAILABLE` for this environment. No Gmail content, token, header or credential was written to logs/evidence.

Fresh global run: 472 discovered, 222 executed, 250 excluded; 222 PASS, 0 FAIL, 0 import failures, 0 timeouts; ADF 35/35. Mail QML and adapter tests pass. Bytecode is 0 `.pyc`. Maps, Documents and Contacts were not developed. `run_native_ui.bat` and the `legacy` default in `app/main.py` were not modified. Cutover remains forbidden.
