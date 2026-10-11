# Lot 6B-A2 — services offline

`CalendarService` et `TasksService` utilisent `PreparedActionRepository` pour préparer des mutations sans appeler leurs providers. Une action doit être confirmée puis elle est exécutée une seule fois; les erreurs provider normalisées la font passer à `error`. Les providers sont uniquement les fakes en mémoire, sans SDK, OAuth, réseau ou credential.

Validation : A1 3 tests, A2 3 tests, 111 tests natifs et 37 tests stricts verts; zéro bytecode source/test. Les scans Google SDK, réseau et credentials historiques sont propres. Google et productivity restent non configurés. Prochaine étape : 6B-A3, non commencée.
