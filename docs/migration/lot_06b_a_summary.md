# Synthèse Lot 6B-A

Architecture offline native : providers fake derrière CalendarService/TasksService, PreparedAction SQLite et transitions prepared/confirmed/executed/cancelled/expired/error. Les outils déterministes sont enregistrés et routés par AgentService ; les lectures alimentent le contexte provider, les écritures demandent confirmation via LocalBus.

NativeCoreBridge traduit les événements pending vers Qt/QML. PendingActionCard affiche un résumé humain, confirme ou annule via le bridge et restaure l'action prepared après redémarrage. Aucun secret, OAuth, SDK Google ou transport Google n'est présent. Google et productivité restent non configurés.

Validation finale A5 : 134 tests natifs, 37 tests stricts Lot 1, self-check QML vert et zéro bytecode. Limite : le raccordement OAuth réel reste le lot 6B-B.
