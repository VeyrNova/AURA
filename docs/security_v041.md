# AURA v0.4.1 — Security Foundation

This version introduces the first **real code-level security boundary**. The prompt in
`docs/identity_security_core.md` remains a behavior specification, but authorization is
now enforced by deterministic Python code.

## Implemented

`IntentManager -> ActionRouter -> SecurityPolicyEngine -> Module`

- Unknown actions fail closed.
- Current local data operations have explicit risk levels and permissions.
- Future high-risk action names are pre-declared and cannot run with default permissions.
- Critical actions such as disabling security stay denied even if marked confirmed.
- Security decisions are written to `security_audit` in SQLite.
- Ollama is local-only by default; a remote endpoint requires explicit configuration and HTTPS.
- Basic secret redaction is applied to application logging.
- A minimal SelfModel reports only capabilities actually implemented.

## Important limitation

No software can guarantee "zero vulnerabilities". v0.4.1 reduces the attack surface and
establishes boundaries for future modules. Before Internet, filesystem, shell, email,
webcam or system-control capabilities are added, they must be integrated through this
security layer and receive dedicated validators/tests.
