# Lot 6B-A3.1 — ToolRegistry et ToolResult

Ce lot ajoute le contrat immuable `ToolResult` et les outils offline Calendar/Tasks. `register_google_offline_tools` enregistre les contrats `calendar.list_events`, `calendar.get_day`, `calendar.find_free_time`, `calendar.create`, `calendar.update`, `calendar.delete`, `tasks.list`, `tasks.create`, `tasks.complete` et `tasks.delete`; il ne configure aucun compte Google.

Les lectures retournent un `ToolResult` réussi sans confirmation. Les écritures ne font que créer une `PreparedAction`, retournent `requires_confirmation=True` et son identifiant, sans appeler les FakeProviders. Les erreurs provider demeurent structurées. La météo reste inchangée et séparée.

Validation attendue : A1, A2, A3.1, toute la suite native, les 37 tests stricts du lot 1, et aucune création de bytecode. Aucun routeur, bridge Qt, QML, bus, OAuth, SDK Google ou accès réseau n'est introduit.
## Résultat de validation

Les validations ciblées sont vertes : PreparedAction A1 3/3, services A2 3/3 et registry A3.1 4/4, soit 10/10. Les 37 tests stricts du lot 1 sont verts et aucun `.pyc` n'a été créé sous `src` ou `tests`.

La découverte intégrale de `tests/native` a exécuté 115 tests mais reste non validée à cause d'une instabilité existante, hors périmètre, de `test_agent_streaming.AgentStreamingTests.test_cancel_drops_late_chunks_and_assistant` (un delta tardif après annulation). Le même test rejoué isolément est vert. Aucune correction du streaming n'est faite dans ce lot. Par conséquent, A3.1 ne peut pas être déclaré PASS tant qu'une exécution intégrale verte n'est pas obtenue ou que cette instabilité n'est pas traitée dans son lot.

Les scans A3.1 ne trouvent aucun SDK Google, OAuth, credential historique, chemin de l'ancienne installation ou ancien AppData dans les modules Google/outils. Les seules URLs trouvées appartiennent aux tests préexistants d'Ollama, avec des openers simulés; A3.1 ne réalise aucun accès réseau.

## Stabilisation streaming — validation

La course venait de deux fenêtres : le worker pouvait publier un delta après son contrôle d'annulation, et un delta déjà admis dans la FIFO pouvait être distribué après la commande `agent.cancel`. `AgentService` sérialise désormais l'admission des événements de streaming et l'annulation par requête ; chaque publication de delta est contrôlée sous ce verrou. La finalisation contrôle le même état avant persistance, complétion et publication. `LocalBus.discard_events` retire les `agent.delta` et changements d'état en attente pour la requête annulée.

Validation : test de cancellation 20/20, module streaming 4/4, suite native 115/115 trois fois consécutives, A1/A2/A3.1 10/10, strict lot 1 37/37, et zéro `.pyc` sous `src` et `tests`.
