# AURA Native — calcul d’itinéraire Maps

## Audit historique

Le Maps historique calculait effectivement des itinéraires internes. Le code
`C:\AURA GPT version\ui\chromium\v0.7.2.2-rc4.2\tools\shell_host.py`
utilisait le serveur public FOSSGIS OSRM `routing.openstreetmap.de/routed-car`
avec `route/v1/driving`, `overview=full`, `geometries=geojson` et `steps=true`.
Il recevait une distance en mètres, une durée en secondes, une LineString et
des étapes. Aucune clé API n’était nécessaire. L’origine venait d’une position
navigateur ou d’un choix manuel; la destination était géocodée. Un lien Google
Maps externe existait aussi, mais ne remplaçait pas ce calcul interne.
Les variantes, le guidage simulé, le recalcul automatique et les liens externes
du parcours historique restent à examiner séparément pour la parité complète.

## Portage natif

`MapsView.qml → NativeMapsBridge → MapsService → RoutingService → RoutingBackend`.
La production injecte `OSRMRoutingBackend`, et les tests `FakeRoutingBackend`.
Le backend réseau est inerte au démarrage et ne contacte OSRM qu’après une
demande de calcul. Origine et destination emploient le géocodage déjà utilisé
par Maps. Le service valide les coordonnées et normalise distance, durée,
GeoJSON LineString et étapes. Le bridge expose états, erreurs, métriques,
géométrie et viewport. `GeoBaseMap.qml` dessine la route avec la projection
Mercator utilisée pour Natural Earth et les marqueurs A/B. La recherche simple
reste disponible. Une action explicite efface l’itinéraire.

La carte affiche l’attribution OpenStreetMap/OSRM et un lien « Corriger la
carte ». L’usage du serveur public impose le respect de sa limite de débit;
le backend espace les appels d’au moins 1,05 s. Le serveur est une dépendance
réseau externe, sans garantie de disponibilité ni trafic temps réel. Les
coordonnées demandées sont envoyées au serveur lors d’un calcul réel. OSRM
Backend est sous licence BSD-2-Clause; les données cartographiques sont
attribuées à OpenStreetMap. Sources :
[politique FOSSGIS](https://routing.openstreetmap.de/about.html),
[API OSRM](https://project-osrm.org/docs/v26.4.0/http),
[code OSRM](https://github.com/Project-OSRM/osrm-backend).

## Validation et état

Les tests sont strictement hors ligne. Les trajets Vidauban → Nice et Nice →
Paris utilisent des réponses simulées et vérifient la chaîne QML, les métriques,
la géométrie, les marqueurs et l’emprise. Ces chiffres de test ne représentent
pas des distances routières observées. La validation visuelle Windows et le
smoke réel du serveur public restent à faire séparément. Le statut Maps demeure
**PARTIAL** et le cutover reste bloqué tant que ces preuves et la décision sur
les autres fonctions de navigation historique ne sont pas obtenues.

Validation finale locale : 4/4 tests routing, 491 tests découverts, 241/241
sélectionnés et réussis, 0 échec, 0 import échoué, 0 timeout; self-check QML
PASS, aucun `.pyc` dans `src/aura_native`, `app` et `tests/native`. La surface
Computer Use ne proposait aucune application Windows (`apps=[]`) :
`LIVE_ROUTING=NOT_AVAILABLE`. À cette étape offline, aucun appel réel à OSRM
n’avait été effectué; le smoke autorisé ci-dessous est séparé.

## Smoke OSRM autorisé

Deux appels réels exactement ont ensuite été effectués avec les coordonnées
issues du contrat de géocodage Native : Vidauban (43.427, 6.431) → Nice
(43.703, 7.266), puis Nice → Paris (48.857, 2.352). Le premier a renvoyé
1697 points, 88 558,6 m, 4217,8 s et 32 étapes en 246,5 ms; son emprise est
`[6.430955, 43.426983, 7.267855, 43.707038]`. Le second a renvoyé 14 492
points, 932 508,9 m, 35 379,1 s et 40 étapes en 1191,6 ms; son emprise est
`[2.306114, 43.395094, 7.265966, 48.857283]`. Les premiers et derniers
points sont cohérents avec les marqueurs. Aucun retry n’a été effectué.

La parité comprend maintenant l’action secondaire « OUVRIR DANS GOOGLE MAPS »
qui construit un deep link `api=1`, origine, destination et `travelmode=driving`;
elle reste distincte du calcul OSRM. L’origine par position courante reste
`NON_AVAILABLE` dans Native; l’origine manuelle est disponible. Clear et
recalcul sont disponibles. Les variantes Legacy de navigation simulée,
reroutage automatique et guidage vocal ne font pas partie de ce lot.

## Origine par position courante

PySide6 6.11.2 expose `QtPositioning.QGeoPositionInfoSource`; aucune abstraction
de localisation AURA existante n’était présente. `CurrentLocationService` utilise
ce fournisseur système avec états bornés `requesting`, `ready`,
`permission_required`, `permission_denied`, `unavailable`, `timeout` et `error`.
Le bouton « MA POSITION » renseigne l’origine seulement après un résultat réel.
En l’absence de source Windows, l’interface reste utilisable avec la saisie
manuelle; aucune position IP, navigateur ou valeur par défaut n’est utilisée.
