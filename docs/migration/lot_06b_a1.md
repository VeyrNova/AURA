# Lot 6B-A1

PreparedAction est désormais immuable et persistant dans SQLite native via la migration additive v5. Le repository contrôle les transitions `prepared → confirmed/cancelled/expired` et `confirmed → executed/error/cancelled`, sérialise le payload JSON et exclut tout état terminal de `get_pending`. Aucun OAuth, SDK, réseau ou intégration tool/UI n'est inclus ; prochaine étape : 6B-A2.
