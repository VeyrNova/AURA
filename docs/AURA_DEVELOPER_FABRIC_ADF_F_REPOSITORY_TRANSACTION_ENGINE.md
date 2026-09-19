# AURA Developer Fabric — ADF-F

## Repository Context + Planner + Patch/Test/Diff Transaction Engine

ADF-F is the first milestone that can safely transform a code workspace.

The pipeline is deliberately ordered:

1. bounded repository scan
2. relevance-bounded context pack
3. deterministic development plan
4. explicit edit proposal with pre-image SHA-256 hashes
5. unified diff generation
6. isolated staging copy
7. allowlisted tests with `shell=False`
8. diff/test review
9. exact approval phrase bound to the transaction id
10. transactional backup + atomic writes
11. post-apply tests
12. automatic rollback on failure
13. durable transaction receipt and manual rollback

Sensitive files such as `.env`, private keys and credential files are excluded from repository context. Symlinks are not followed. Paths outside the workspace are denied.

ADF-F does not make AURA self-modifying by default. ADF-G will add the stricter self-development policy layer, protected authorities, approval hierarchy and audit receipts required before AURA may use this engine on its own codebase.
