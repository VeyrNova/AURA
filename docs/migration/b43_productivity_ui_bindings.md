# B4.3 — Liaison Agenda / Tâches native

La navigation native monte désormais directement `AgendaView.qml` et
`TasksView.qml`. Le bridge natif expose explicitement les propriétés attendues
par ces vues (`googleTasksCount`, `googleCalendarCount`, statuts et libellés),
avec l’état `not_migrated` et des compteurs à zéro tant que les intégrations ne
sont pas migrées. Cela évite les valeurs `undefined` sans réactiver le legacy.

Le calendrier affiche un mois local déterministe de 42 cellules et permet la
navigation précédente/suivante/aujourd’hui sans réseau. Les modèles Google et
locaux restent vides et aucune mutation, authentification ou lecture de
credential n’est déclenchée par l’ouverture de ces vues.

Validation : tests ciblés de liaison/routage verts, suite `tests/native` verte,
self-check QML conservé, et aucun bytecode généré dans les sources.
