# Security

AURA is designed so that each user supplies their own provider credentials locally.

## Never commit

- API keys or provider tokens
- OAuth tokens or cookies
- `.env`
- local memory databases
- conversation history
- personal/private voice samples
- model binaries
- local logs and diagnostics containing private information

The repository should contain only blank configuration templates such as `.env.example`.

Before every public release, run a secret scan on the complete Git staging tree.
