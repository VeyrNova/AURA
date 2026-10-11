# ADF recovery phases

1. Evidence lock and SHA-256 comparison (complete).
2. Native policy kernel: default-off mode, workspace/symlink/outside-root denial, safe targets and audit receipts.
3. Plan/stage/diff with preimage hashes and no mutation during planning.
4. Approval transaction: explicit phrase, backup, atomic apply, post-tests and automatic rollback on failure.
5. Metadata-only provider and ten-agent catalogs; no secrets or auto-discovery.
6. Queued Qt/QML bridge; unavailable features stay `not_migrated`.
7. Offline-fake resilience and resumable jobs.
8. Unit, E2E fake, security, QML offscreen and release acceptance.
