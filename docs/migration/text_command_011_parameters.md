# Lot 011 — paramètres Weather, Search et Navigation

Le routeur conserve maintenant les paramètres prouvés dans la chaîne Native :

- `quel temps fait-il à Marseille` → `WEATHER_QUERY(location=Marseille)` ;
- `météo à Lyon demain` → `WEATHER_QUERY(location=Lyon, date=tomorrow)` ;
- `ouvre la météo de Bordeaux` → `OPEN_MODULE(module=weather, location=Bordeaux)` ;
- `ouvre les documents sur ICPE` → `OPEN_MODULE(module=documents, query=ICPE)` ;
- `cherche ICPE sur internet` → `WEB_SEARCH(query=ICPE)` ;
- `cherche ICPE dans mes notes` → `SEARCH_NOTE(query=ICPE)` ;
- `cherche ICPE dans ma mémoire` → `SEARCH_MEMORY(query=ICPE)`.

La frontière UI conserve le payload des intents dans `AuraBridge.navigationContext`
avant de changer de workspace. Aucun parsing n’est fait en QML et aucune
mutation ou PreparedAction n’est produit par ces commandes.

Validation automatisée : `test_text_command_011_parameters.py` 5/5, anciens
tests Text Command 006/010 verts, QML Native 5/5, Lot 1 strict 53/53.
Computer Use était indisponible (`apps=[]`), donc aucune validation live n’est
revendiquée.
