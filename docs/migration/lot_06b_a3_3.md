# Lot 6B-A3.3 — orchestration d'outils AgentService

AgentService appelle ToolRouter une fois par requête puis exécute l'outil retenu via un ToolRegistry injecté. `None` conserve le chemin provider et streaming existant. Une clarification produit une réponse locale sans handler ni PreparedAction. Une écriture réussie prépare seulement l'action et produit une réponse locale avec confirmation requise. Une lecture injecte un résultat JSON balisé comme donnée dans le contexte du provider.

Les erreurs tool sont converties en réponses utilisateur sans trace. Weather rejoint ce flux générique sans réseau supplémentaire. Les fakes Google sont injectés uniquement par les tests; bootstrap conserve la capability Google absente/non configurée.

Validation : orchestration et météo/streaming 12/12, suite native 121/121, strict lot 1 37/37, zéro bytecode sous `src` et `tests`. Limite : résolution des cibles textuelles update/delete et confirmation UI restent pour A3.4.