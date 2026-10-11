# Lot 6B-A4.1 — NativeCoreBridge pending actions

`NativeCoreBridge` expose l'action pending via `hasPendingAction`, son identifiant, résumé, outil, type, état et erreur. Il écoute `pending_action.created`, les transitions de confirmation et les états finaux. `confirmPendingAction()` et `cancelPendingAction()` publient uniquement les commandes LocalBus correspondantes.

Au démarrage, le bridge restaure la plus ancienne action `prepared` via le repository partagé. Il ne contient aucune logique Calendar/Tasks, mutation SQLite, OAuth, provider ou réseau. Le dispatcher Qt existant conserve les callbacks sur le thread UI.

Validation : tests A4.1 et A3.4 ciblés 11/11, suite native 126/126, strict lot 1 37/37, zéro bytecode. Prochaine étape : A4.2.
