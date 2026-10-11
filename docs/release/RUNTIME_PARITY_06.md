# Runtime Parity 06 — Weather city selection, Maps and Mail

Date : 2026-10-03. Le cutover reste interdit.

Weather Native est désormais `PARTIAL/PASS pour le périmètre ville` : `WeatherService.search_locations()` utilise le même provider Open-Meteo (géocodage séparé), `NativeWeatherBridge.searchLocations()` expose des résultats, `selectCity()` conserve les coordonnées sélectionnées puis recharge le forecast. `WeatherView.qml` affiche les résultats dans le contrôle de recherche existant, sans logique réseau dans QML. Nice → Paris est testé avec FakeWeatherProvider ; recherche vide, erreur provider et changement de ville sont couverts. Aucune persistance de ville n’a été ajoutée : l’ancien contrat ne démontre pas de persistance utilisateur.

Maps est `LEGACY_PLACEHOLDER/PARTIAL`, pas `FUNCTIONAL` : l’inventaire du workspace ne contient aucune `MapsView` ou service de carte autonome. ModulesView ne fait que naviguer vers `maps`; NativeWorkspaceView ne présente donc pas de fonctionnalité Maps perdue à migrer. Le test verrouille explicitement l’absence de faux port et la route Foundation n’est pas présentée comme Maps.

Mail est `LEGACY_FUNCTIONAL` et reste `NATIVE_PARITY_BLOCKER`. La source historique lue en read-only expose recherche, lecture message/thread, pièces jointes, brouillon et envoi via Gmail. Le registre natif n’expose aucun service Gmail/mail et `ModulesView` ne fait qu’envoyer un préremplissage `coreBridge.sendMessage`. Aucun credential, OAuth, réseau ou write Google n’a été utilisé.

Run offline frais : 466 tests découverts, 218 exécutés, 248 exclus ; 218 PASS, 0 FAIL, 0 import failure, 0 timeout, `complete=true`. ADF 35/35. Les tests ajoutés sont `test_weather_city_qml.py` et `test_maps_mail_classification.py`. Aucun BAT, défaut `legacy`, ADF ou ancien workspace n’a été modifié.

Prochaine étape stricte : concevoir séparément le contrat Mail natif (reads fake, actions sensibles PreparedAction) et décider si Maps doit rester explicitement non migré ou recevoir un périmètre fonctionnel autorisé. Pas de cutover avant cette décision.
