# Lot 6A — météo native et premier outil agent

## Audit legacy

L'ancien système utilisait Open-Meteo, mais mélangeait bridge PySide6,
`%LOCALAPPDATA%\AURA`, cache disque, worker Qt, géolocalisation, cartes de
relief et vent, ainsi que surfaces Chromium. Seules les idées suivantes ont
été retenues : géocodage puis prévision, unités explicites et mapping WMO. Aucun
fichier legacy n'est importé ou exécuté.

## Architecture

`WeatherService` reste un domaine Python sans Qt. `OpenMeteoProvider` effectue
géocodage et prévision via `urllib`; `FakeWeatherProvider` couvre les tests.
Les modèles `WeatherLocation`, `WeatherCurrent`, `WeatherDaily` et
`WeatherReport` normalisent les données en Celsius, km/h et mm. Le cache est
strictement mémoire et expire après cinq minutes.

Les erreurs publiques sont : `weather_location_not_found`,
`weather_provider_unavailable`, `weather_timeout`, `weather_network_error` et
`weather_invalid_response`. Les codes WMO deviennent des états stables, par
exemple `clear`, `partly_cloudy`, `rain` et `thunderstorm`.

`ToolRegistry` enregistre `weather.get_forecast`; `ToolRouter` applique une
détection déterministe aux requêtes météo contenant une ville explicite. Il ne
route pas les requêtes non météo. Le résultat structuré est inséré dans
`<tool_result>` avant le message courant et le prompt demande à Ollama de ne
jamais inventer de valeur météo externe. La mémoire et le streaming existants
restent inchangés. Aucune vue QML n'est ajoutée dans ce lot : `WeatherView.qml`
historique dépend encore de `WeatherBridge` et reste hors du parcours natif.

## Validation

Tests hors ligne : géocodage, erreur de ville, current/daily, mapping WMO,
timeout, erreur réseau, réponse invalide, cache, registre, validation outil,
routage, non-routage et injection du résultat dans l'agent.

Le test réel du 28 septembre 2026 a interrogé Open-Meteo pour Nice, France :
pour le 29 septembre, `cloudy`, 19.3–25.9 °C, 3 % de précipitation. Le parcours
AURA complet a émis un unique `agent.tool_completed`, puis Ollama a répondu
avec les mêmes valeurs. Le lot ne fournit pas encore de localisation système,
de cache persistant, ni de vue météo QML native.
