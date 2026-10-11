# Runtime Parity 08 — Gmail production READ adapter

The native Mail domain now has `GmailMailBackend` in `src/aura_native/mail/gmail_adapter.py`. It consumes the existing `GoogleAuthProvider` used by Calendar/Tasks; it creates no OAuth flow and no credential store. The adapter is read-only: search/list, message, thread and attachment metadata/content. Its capability declaration disables writes.

The adapter requires the existing authenticated identity and the explicit `https://www.googleapis.com/auth/gmail.readonly` scope. The current Native OAuth configuration only declares Calendar and Tasks scopes, so no production Gmail request was attempted: `MAIL_PRODUCTION_READ=BLOCKED_BY_SCOPE`. No scope was silently expanded and no credential was read for this validation.

`MailService` remains backend-agnostic. FakeMailBackend and GmailMailBackend share normalized MailMessage/MailThread structures. Fake adapter tests cover search, message, thread, attachment contract and missing scope. NativeMailBridge/MailView were not changed for the adapter; composition chooses Gmail only when the existing identity is authenticated with the explicit Gmail read scope, otherwise the deterministic offline backend remains available to tests.

No real Gmail content is written to evidence or logs. No send, draft, reply, forward, archive, label, delete, trash or mark-read operation is exposed by GmailMailBackend. The existing offline PreparedAction send path remains test-only and is not a production capability.

Fresh global run: 470 tests discovered, 220 executed, 250 excluded; 220 PASS, 0 FAIL, 0 import failures, 0 timeouts; ADF 35/35. Native Mail QML self-check passed. Bytecode scan: 0 `.pyc`. Maps was not touched; Documents/Contacts classifications were not changed. `run_native_ui.bat` and the `legacy` default in `app/main.py` were not modified. Cutover remains forbidden for this lot.
