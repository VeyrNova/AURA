# AURA Developer Fabric — ADF-C

## 50-provider ToS-aware registry + Free-tier/Quota Observatory

ADF-C adds the provider-governance layer required by the AURA Developer Fabric capability charter.

### Clean-room rule

Provider names and publicly advertised connection requirements are treated as interoperability/reference facts.
No FCC source module, implementation, launcher, configuration file, or runtime artifact is copied or imported.

### Provider registry

The seed contains 50 provider routes from the public ecosystem snapshot observed on 2026-08-30.

Each record contains only non-secret metadata:

- provider id and display name
- credential *variable names* or local connection mode
- ToS/policy status
- source/reference URL
- last verification timestamp
- verification TTL
- policy eligibility state

No API key/token value is stored.

### Freshness policy

Remote provider policy references expire after 30 days by default.
Once expired, AURA marks the provider `stale_review_required` and policy-ineligible until it is re-verified.

Local providers (LM Studio, llama.cpp, Ollama) do not depend on remote ToS freshness.

This is intentionally stricter than treating an old "ToS-friendly" list as permanent truth.

### Free-tier/Quota Observatory

The observatory separates:

1. **External headline reference** — currently 1.3B+ free tokens/month from a public FCC claim.
2. **Known token-equivalent reference floor** — only observations explicitly denominated in tokens and still fresh.
3. **Non-token metrics** — requests/minute, neurons/day, "free", "unlimited", etc. These are never fabricated into token counts.
4. **Guaranteed quota** — always zero unless AURA has an explicit contractual guarantee.

The public headline is therefore visible but explicitly marked:

- not guaranteed
- not independently verified by AURA
- freshness-limited
- controlled by upstream providers

### ADF HTTP endpoints

ADF-C extends AFG with two read-only endpoints:

- `GET /aura/v1/providers`
- `GET /aura/v1/quotas`

No secret values are returned.

### Next

ADF-D will build the 10 coding-agent compatibility layer and native launchers/IDE bridges against the AURA Fabric Gateway.
