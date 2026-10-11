# Lot 6B-A5 — consolidation Google offline

Le domaine Calendar/Tasks est consolidé offline autour de `PreparedActionRepository`, des FakeProviders, ToolRegistry/Router, AgentService, LocalBus, NativeCoreBridge et PendingActionCard. Les écritures restent préparées jusqu'à confirmation ; les lectures n'émettent aucune action pending. La règle multi-pending expose la plus ancienne action prepared et conserve les autres.

Validation E2E : 5 tests dédiés, suite native 134/134, strict lot 1 37/37, bytecode 0. Aucun OAuth, SDK Google, credential, ancien AppData ou réseau Google n'est utilisé. Google reste `not_configured` ; cette validation ne signifie pas qu'un compte Google est connecté.
