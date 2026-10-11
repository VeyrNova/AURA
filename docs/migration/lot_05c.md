# Lot 5C — streaming natif offline

Le contrat provider expose `ProviderChunk`; `StreamingFakeProvider` produit des
fragments déterministes sans réseau. `AgentService` exécute le flux dans son
executor, publie `agent.delta`, agrège les fragments et ne persiste qu'un seul
message assistant final.

L'annulation enregistre la requête comme terminale, annule le futur si possible
et bloque les chunks ou messages tardifs. Le runtime arrête explicitement
l'executor agent avant sa reconstruction afin de réduire les ressources
asynchrones persistantes. Le bridge expose `agentStream`, remis à zéro aux
états terminaux; QML l'affiche comme brouillon temporaire.

`OllamaProvider.generate_stream` est implémenté avec la bibliothèque standard
pour le protocole NDJSON, mais aucun test ni lancement n'effectue de requête
réseau. La composition native reste sur `NoProvider` sauf injection explicite
d'un provider de test.

Validation : 85 tests natifs, 37 tests stricts lot 1, self-check QML et zéro
bytecode source/test. Limite : les fournisseurs réseau et la visualisation
interactive Windows ne sont pas validés dans ce lot.
