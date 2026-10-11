# Legacy → Native persistent memory migration specification

Status: specification and synthetic dry-run only. No real Legacy or Native database was opened, written, copied or migrated.

## Schemas

Legacy `database/database.py` defines `memories` with integer `id`, `content`, `type`, `importance`, `source`, `confidence`, `created_at`, then v0.6 adds `updated_at`, `normalized_content`, `status`, `access_count`, `last_used_context_at`, `is_sensitive`, and `tags`. Legacy also has a separate `preferences(key,value,updated_at)` table. `memory/manager.py` and `memory/kernel_v2.py` provide explicit remember/search/forget behavior. Legacy conversation transcript remains volatile and is not part of this migration.

Native uses versioned SQLite (`schema_migrations`, version 13). `memories` requires `memory_id`, `content`, `normalized_content`, `memory_type`, `scope`, `scope_id`, `importance` 1–5, `confidence` 0–1, `source`, `is_sensitive`, `created_at`, `updated_at`, optional `expires_at`, and `status`. `memory_audit` records memory_id, action, timestamp and non-content JSON detail. Native has no dedicated provenance columns, so a future writer must add a reviewed provenance mechanism or keep migration provenance in a separate migration ledger; it must never put bookkeeping into visible content.

## Mapping

| LEGACY_FIELD | LEGACY_SEMANTICS | NATIVE_FIELD | TRANSFORMATION | REQUIRED | DEFAULT | LOSSY | DISPOSITION |
|---|---|---|---|---|---|---|---|
| id | stable Legacy integer identity | migration ledger / provenance | stringify; never reuse as Native primary key | yes | none | no | TRANSFORM |
| content | remembered value | content | trim, preserve Unicode | yes | none | no | DIRECT |
| type | fact/preference/project/etc. | memory_type | allow only evidenced Native types | yes | none | possible | TRANSFORM |
| importance | Legacy priority | importance | accept only proven 1–5 semantics | yes | 1 | possible | TRANSFORM |
| confidence | Legacy confidence | confidence | accept only proven 0–1 scale | yes | 1.0 | possible | TRANSFORM |
| source | origin label | source | `legacy_aura` plus provenance ledger | no | legacy | no | TRANSFORM |
| created_at | creation timestamp | created_at | preserve valid ISO value | yes | none | no | DIRECT |
| updated_at | last update | updated_at | preserve valid ISO value or created_at | no | created_at | possible | TRANSFORM |
| status | active/deleted state | status | inactive/deleted rows are not imported | yes | ACTIVE | no | TRANSFORM |
| is_sensitive | privacy marker | is_sensitive | boolean preservation | no | false | no | DIRECT |
| normalized_content | search normalization | normalized_content | recompute with Native normalization | no | derived | no | TRANSFORM |
| access_count / last_used_context_at / tags | Legacy usage metadata | no Native field | retain only in future provenance ledger if required | no | none | yes | DROP_WITH_EXPLICIT_REVIEW |
| preferences.key/value | configuration/preferences | Native memories | do not coerce | no | none | yes | SEPARATE_STORE |

Every candidate is classified `NEW`, `ALREADY_MIGRATED`, `POSSIBLE_DUPLICATE`, `CONFLICT`, `INVALID` or `UNSUPPORTED`. Unknown types, ambiguous scopes, deleted records, invalid IDs/content/timestamps and invalid confidence are skipped with a reason; they are never silently repaired.

## Scope, identity and idempotence

`MEMORY_SCOPE_MAPPING=PASS_WITH_REVIEW`: only Legacy global user records with an evidenced global scope may map to Native `scope=user`, `scope_id=default`. Session, conversation, agent or unknown scope is `UNSUPPORTED_REQUIRES_REVIEW`; it cannot become global accidentally.

Migration version is `legacy_memory_to_native_v1`. A deterministic identity is `(migration_version, source=legacy_aura, legacy_id)`. Native IDs remain independently generated. A stable structural SHA-256 fingerprint is also calculated for duplicate evidence. A second run classifies existing provenance/fingerprint as `ALREADY_MIGRATED` and inserts zero rows. Semantic text equality alone is only `POSSIBLE_DUPLICATE`, never an automatic merge.

Preferences remain a separate migration concern: `LEGACY_PREFERENCE_MIGRATION=SEPARATE_STORE`. They are not memory records.

## Dry-run and safety

`src/aura_native/migration/memory_legacy.py` is a pure planner. It accepts synthetic records and returns structured counts: source_records, eligible, new, already_migrated, possible_duplicates, conflicts, invalid, unsupported, would_insert, would_update and would_skip. It performs no destination write. `read_synthetic_source_read_only()` uses SQLite `mode=ro`; source mutation fails with `OperationalError`.

Future execution, if separately authorized, must:

1. verify migration version and source schema;
2. open Legacy source read-only;
3. create a Native DB backup without touching the source;
4. run the dry-run and require review of invalid/unsupported/conflict counts;
5. `BEGIN`, insert only approved candidates, write provenance/audit records, verify counts and `COMMIT`;
6. rollback on any failure; never overwrite newer Native rows;
7. retain source unchanged and provide row counts/fingerprints without raw content.

`REAL_MEMORY_MIGRATION_EXECUTED=NO`.

## Synthetic validation

`tests/native/test_memory_migration_spec.py` covers direct and Unicode mapping, types, scope, timestamps, provenance, stable IDs, idempotence, semantic duplicates, conflicts, invalid/deleted/unsupported rows, preferences, read-only source enforcement, zero writes, deterministic fingerprints, schema errors and migration versioning: **24/24 PASS**.
