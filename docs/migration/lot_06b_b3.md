# LOT 6B-B3 — Google read-only providers

This lot adds isolated, read-only Calendar and Tasks providers backed by the official Google discovery API, loaded dynamically only when authenticated credentials are configured. Offline tests inject a fake discovery builder; no SDK installation, OAuth, network, token output, or write operation is performed by the test suite.

Calendar and Tasks reads support pagination, primary/default collection selection, date/time and missing-field normalization, free/busy, and normalized authentication, permission, rate-limit, network, and invalid-response errors. All write methods remain `google_write_not_migrated`.

The native composition selects the real providers only when `AURA_GOOGLE_OAUTH_CLIENT_FILE` is explicitly configured and the auth store reports an authenticated state. Otherwise it retains deterministic fake providers. Legacy Chromium, RC4.2, historical AppData, and historical credentials are not used.

Validation target: offline technical PASS; real read validation remains required by an explicit manual run of `tests/native/_evidence/lot6b_b3_google_read.py`.

## Credential boundary corrective patch

`GoogleAuthProvider.get_credentials()` now reconstructs an official
`google.oauth2.credentials.Credentials` object from the opaque store and the
configured client metadata. Calendar and Tasks both consume this single
contract and pass `cache_discovery=False`; no serialized dictionary reaches
the discovery client. Existing scopes and keyring entries are preserved.

Expiry values are canonicalized to `YYYY-MM-DDTHH:MM:SS` for new saves and
legacy values using a space separator remain loadable. Missing expiry remains
valid. No OAuth renewal or credential rewrite is forced.
