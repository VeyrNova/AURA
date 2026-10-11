# AURA — LOT 3B — interface mémoire native minimale

## Objectif

Exposer la capacité mémoire locale validée au LOT 3A dans le parcours Qt/QML
natif, sans construire la vue mémoire legacy et sans réintroduire RC4.2,
HTTP/SSE, MainWindow, WebEngine ou l'ancien AppData.

## Périmètre

- `NativeCoreBridge` expose liste, recherche, création et oubli.
- `NativeWorkspaceView.qml` fournit la première interface mémoire native.
- Les autres capacités restent explicitement `not_migrated`.
- Aucun import ou transfert automatique de la mémoire historique.
- Aucun cloud, IA, embeddings ou auto-capture.

## Flux

QML -> NativeCoreBridge -> LocalBus -> MemoryService -> SQLite native

Les événements `memory.created`, `memory.updated`, `memory.forgotten`,
`memory.listed` et `memory.search_completed` mettent à jour l'état QML.

## Validation attendue

- 59 tests précédents restent verts.
- tests Qt mémoire du LOT 3B verts.
- self-check QML natif sans TypeError.
- aucune dépendance legacy active en mode natif.
- aucun bytecode sous `src/aura_native` ou `tests/native`.
