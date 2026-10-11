# Memory, history and context parity

Audit date: 2026-10-10. Legacy path was inspected read-only; no Legacy process was started and no user rows were read or copied.

## Evidence and classification

| DOMAIN | CAPABILITY | LEGACY_EVIDENCE | LEGACY_REACHABILITY | LEGACY_STORAGE | NATIVE_IMPLEMENTATION | NATIVE_STORAGE | PARITY_STATUS | DATA_MIGRATION_REQUIRED | RISK | NOTES |
|---|---|---|---|---|---|---|---|---|---|---|
| History | append user/assistant turn | `core/aura_core.py` appends volatile `conversation_history`; `database/database.py` has no transcript table | ACTIVE_REACHABLE in runtime, persistence of transcript not evidenced | memory-only transcript; session counters in SQLite | `ConversationService` + `ConversationRepository` | `conversation_messages` SQLite | NATIVE_STRONGER | NOT_REQUIRED | low | Native explicitly persists turns |
| History | ordered retrieval | `AuraCore.build_llm_messages` uses list order | ACTIVE_REACHABLE | volatile list | repository `sequence` and unique `(conversation_id, sequence)` | SQLite | PASS | NOT_REQUIRED | low | deterministic ordering |
| History | session continuity | `memory/continuity.py` states transcript is not persisted | ACTIVE_REACHABLE | `conversation_sessions` counters only | conversation/session IDs and persisted messages | SQLite | PASS_NATIVE | NOT_REQUIRED | low | semantics intentionally differ and are safer |
| History | restart persistence | no Legacy transcript evidence | UNKNOWN | none evidenced | repository reopen tests | SQLite | PASS_NATIVE | NOT_REQUIRED | low | isolated temp-state proof |
| History | isolation | Legacy uses one in-memory core list | ACTIVE_REACHABLE | process memory | `(session_id, conversation_id)` checks | SQLite | PASS | NOT_REQUIRED | medium | cross-session reads rejected |
| Context | assembly | `consciousness/context_builder.py` combines system, recent messages, memory context | ACTIVE_REACHABLE | volatile history + SQLite memories | `ContextBuilder` combines system, bounded history, selected scoped memory, current turn | SQLite | PASS | NOT_REQUIRED | medium | roles and ordering preserved |
| Context | size limiting | Legacy `LLM_MAX_HISTORY_MESSAGES` and memory char limits | ACTIVE_REACHABLE | configuration | native message-count and memory-char bounds | SQLite + request memory | PASS_WITH_DIFFERENT_LIMITS | NOT_REQUIRED | medium | no fake token precision |
| Context | pruning | Legacy limits request context, does not prove destructive transcript deletion | ACTIVE_REACHABLE | request-only | native slices assembled context only | persisted history retained | PASS | NOT_REQUIRED | low | persisted rows remain intact |
| Memory | persistent read/write | `database.memories`, `memory/manager.py`, `kernel_v2.py` and explicit remember/forget paths | ACTIVE_REACHABLE | SQLite `memories`, `preferences` | `MemoryRepository` and `MemoryService`, scoped records, deduplication, forget | versioned Native SQLite | PASS_NATIVE_CONTRACT | REQUIRES_EXPLICIT_SPEC_FOR_REAL_DATA | medium | no real migration performed |
| Memory | delete/forget | `MemoryManager.forget`, `forget_all_profile_data` | ACTIVE_REACHABLE | Legacy SQLite | `memory.forget`, session clear | Native SQLite | PASS_NATIVE_CONTRACT | REQUIRES_TRANSFORM | medium | no automatic cross-schema copy |
| Agent | duplicate completion | no equivalent durable request ID proven in Legacy audit | UNKNOWN | unknown | `AgentRepository.find_by_user_message` rejects duplicate agent submission; request IDs remain distinct | SQLite | PASS_NATIVE | NOT_REQUIRED | medium | not text-equality deduplication |
| Storage | schema versioning | Legacy migration method v0.6, no single schema version table evidenced | ACTIVE_REACHABLE | ALTER TABLE migrations | `schema_migrations`, current version 13 | Native SQLite | PASS | NOT_REQUIRED | low | corrupt/newer schema fails closed |
| Storage | corruption behavior | no safe Legacy reset contract established | UNKNOWN | unknown | migration/runtime error, no destructive reset | Native SQLite | PASS | NOT_REQUIRED | medium | tested with newer schema |
| Operations | concurrency | Legacy single connection/process behavior | UNKNOWN | process-local | `BEGIN IMMEDIATE`, busy timeout, ordered sequence | SQLite | PASS_OFFLINE | NOT_REQUIRED | medium | near-concurrent safety covered by SQLite contract |

## Explicit split

`LEGACY_CONVERSATION_HISTORY=ACTIVE_REACHABLE_VOLATILE`

`LEGACY_SESSION_CONTEXT=ACTIVE_REACHABLE_VOLATILE_WITH_EXPLICIT_LIMITS`

`LEGACY_PERSISTENT_USER_MEMORY=ACTIVE_REACHABLE_EXPLICIT_MEMORY_MANAGER_AND_KERNEL`

The Legacy transcript list is not classified as persistent user memory. Native memory records are a separate, explicit product domain with scope, sensitivity filtering, and forget operations.

## Native contracts

- Conversation IDs identify persisted conversations; session IDs authorize access to them; message IDs identify individual turns; request IDs identify agent requests. They are never overloaded.
- History ordering uses a monotonic per-conversation `sequence`, not timestamp ordering alone.
- `ContextBuilder` assembles system prompt, selected non-sensitive memory, bounded historical turns, and the current user turn. It does not delete persisted history.
- User, assistant and system roles are represented in the schema. Tool results remain request context and are not silently persisted as user memory.
- All validation uses isolated temporary databases. `%LOCALAPPDATA%\AURA-NATIVE` was not opened or changed.

## Migration assessment

`LEGACY_NATIVE_HISTORY_MIGRATION=UNSAFE_OR_UNNECESSARY_FOR_TRANSCRIPT; Legacy does not evidence persisted transcript rows. Native history is a new versioned store.`

`LEGACY_NATIVE_MEMORY_MIGRATION=REQUIRES_TRANSFORM; schemas and IDs differ. Future migration requires read-only source, dry run, row counts, checksums, explicit mapping, backup and rollback. No rows were copied.`

`MEMORY_HISTORY_CORE_PARITY=PASS_NATIVE`

`MEMORY_CONTEXT_PARITY=PASS_NATIVE_WITH_EXPLICIT_MESSAGE_LIMIT`

`PERSISTENT_USER_MEMORY_PARITY=PASS_NATIVE_CONTRACT; legacy data migration remains open`

`MEMORY_PRODUCT_INTEGRATION=DEFERRED_TO_EXISTING_NATIVE_BRIDGE/UI_SCOPE`

`MEMORY_HISTORY_CUTOVER_BLOCKER=false`

## Validation

- Focused memory/history/context suite: 22/22 PASS.
- Existing Conversation suite: 5/5 PASS.
- Existing Agent Context suite: 9/9 PASS.
- Lot 1 strict validation remains required after the complete regression run.

## Memory 002 migration specification
- `LEGACY_NATIVE_MEMORY_MIGRATION=REQUIRES_TRANSFORM` remains unchanged.
- Synthetic planner and read-only fixture validation are documented in `memory_legacy_native_migration_spec.md`.
- No real rows, credentials, user content or Native state were accessed.
