# Lot 6B-A3.4 — validation finale

Le repository PreparedAction partagé alimente Calendar/Tasks, AgentService et PendingActionOrchestrator. Les handlers `pending_action.confirm` et `pending_action.cancel` sont liés au LocalBus.

Tests A3.4 : 3/3 verts, couvrant confirmation, annulation, expiration, idempotence, erreur provider et tâche. Suite native : 124/124 ; strict lot 1 : 37/37 ; bytecode : 0. Aucun OAuth, SDK Google, réseau, Qt ou Git.
