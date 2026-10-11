# Provider Credentials Center — socle

The provider settings foundation separates non-secret `ProviderConfig` metadata
from secrets. API keys are stored only through `ProviderCredentialStore`; the
Windows implementation delegates to `keyring`, while tests use an in-memory
fake. No secret is placed in SQLite, JSON, LocalBus contracts, QML properties,
logs or documentation.

Initial provider identifiers are `openai`, `anthropic`, `gemini`, `ollama` and
`custom`. Google Workspace remains on its existing OAuth/keyring boundary and
is intentionally not replaced by an API key. Environment and CLI migration,
settings bridge and UI are subsequent steps; no network test is automatic.
