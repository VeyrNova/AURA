# AURA - LOT 3A - native storage and memory backend

Status: implementation package for local validation. No Git operation.

## Scope

LOT 3A adds the first native business capability behind the LocalBus:

QML boundary -> NativeCoreBridge/LocalBus -> MemoryService -> MemoryRepository -> SQLite

This sub-lot intentionally does not change QML yet. The memory backend is made
available and tested first; UI exposure will be LOT 3B after this backend is
validated.

## Privacy and migration choices

- No historical database is read or imported.
- No historical AppData path is discovered.
- No .env is loaded.
- Sensitive memories are tagged locally and excluded from list/search by default.
- No auto-capture is implemented.
- No AI, embeddings, cloud sync, Google, voice or historical MemoryKernel is imported.
- The database lives only under the explicit native state-dir: data/aura_native.db.
- Forget performs a hard delete from the active memory table and leaves only a
  minimal technical audit record without memory content.

## Deferred historical features

Continuity, relationship familiarity, adaptive learning, MemoryKernelV2 graph
entities/facts/relations/conflicts and legacy migration are deliberately deferred.
They are not required to prove the first autonomous native memory path.
