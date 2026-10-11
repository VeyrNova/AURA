# Native Runtime Parity 05 — 2026-10-02

CUTOVER BLOCKED. Résultats automatisés verts, aucune validation Windows interactive revendiquée. Aucun Git, réseau réel, OAuth ou Google write exécuté. Les lectures historiques ont été limitées à des sources Python ; aucune source historique importée/exécutée/modifiée.

## Cause Music et corrections

Le getter `playing` comparait la méthode `playbackState` à PlayingState au lieu d’appeler `playbackState()`. Avant modification, un probe montrait simultanément QMediaPlayer=PlayingState et bridge.playing=False : LoadedMedia, un signal PlayingState, NoError, durée 5000 ms, hasAudio=true, QAudioOutput attaché, volume 0.8 et non muted. Le backend n’était donc pas en échec. Le getter a été corrigé ; les modèles musicPlaylistModel/musicLibraryModel de production ne sont plus des EmptyListModel. NativeModuleComposition construit les mêmes bridges de modules pour production et tests. Les objectName ajoutés servent uniquement à localiser les vrais contrôles, sans handlers artificiels.

## Rapport demandé

| # | Contrôle | Résultat |
|---|---|---|
| 1 | Music mediaStatus before play | LoadedMedia |
| 2 | Music playbackState before play | StoppedState |
| 3 | Music play signal observed | Oui, QSignalSpy installé avant les clics |
| 4 | Music playback states observed | 8 signaux : Playing, Stopped, Playing, Paused, Playing, Paused, Playing, Stopped |
| 5 | Music error | NoError |
| 6 | Music errorString | vide |
| 7 | Music duration | 5000 ms |
| 8 | Music hasAudio | true |
| 9 | Music QAudioOutput attached | Oui, player.audioOutput() is bridge._audio |
| 10 | bridge direct playback test | PASS sur le même player que le test QML |
| 11 | offscreen playback result | PASS ; aucune limitation backend constatée |
| 12 | Windows non-offscreen playback result | PASS, platform=windows, Playing → Paused → Stopped |
| 13 | Music QML load | PASS, vraie MusicCenterView et clic TITRES |
| 14 | Music QML play dispatch | PASS, vrai TapHandler togglePlay → play |
| 15 | Music QML pause dispatch | PASS, togglePlay → pause |
| 16 | Music QML resume dispatch | PASS, togglePlay → play |
| 17 | Music QML stop dispatch | PASS, stop |
| 18 | Music QML volume | PASS, slider réel → QAudioOutput volume |
| 19 | Music QML seek | PASS, slider réel → position > 1000 ms |
| 20 | Center/Subdock same instance | PASS, même contexte installé par NativeModuleComposition |
| 21 | Center/Subdock state sync | PASS, pause depuis Subdock ; icônes pause/play liées au vrai état |
| 22 | Music reopen same player | PASS, déchargement/rechargement de la vraie vue avec même bridge/player ; pas une navigation Windows interactive |
| 23 | Music final status | PASS AUTOMATED dans le périmètre lecture locale ; interaction humaine non validée |
| 24 | Modules Legacy status | LEGACY_FUNCTIONAL pour catalogue/navigation/panneau Mail ; helpers conversation |
| 25 | Modules Legacy functions | 7 entrées, navigation Weather/Maps, panneau Mail, préremplissage Recherche/Documents/Notifications/Contacts et commande boîte Mail |
| 26 | Modules Native implementation | Réutilisation de ModulesView QML ; transfert des signaux vers Main/composer ; aucun AuraCoreBridge |
| 27 | Modules route | modules → ModulesView ; exclu de Foundation |
| 28 | Modules QML offscreen | PASS, navigation/prefill/panneau et self-check Main natif |
| 29 | Modules final status | PASS UI ; parité backend Mail non acquise |
| 30 | Settings locale Legacy contract | fr-FR/en-US ; localeChanged ; GET/POST /api/locale ; dépendance serveur remplacée, persistance serveur non exécutée |
| 31 | Settings Native owner | LocaleService Qt-free, composé par compose_runtime ; ProviderSettingsService reste spécifique aux providers |
| 32 | Settings locale read | PASS, fr-FR par défaut ; fallback sûr si fichier invalide |
| 33 | Settings setLocale | PASS, valeurs autorisées uniquement ; invalide refusé |
| 34 | Settings signal | PASS, localeChanged émis une fois pour changement réel |
| 35 | Settings persistence | PASS, config/ui_locale.json atomique dans state-dir natif ; reconstruction service relit en-US |
| 36 | Settings QML offscreen | PASS, vraie SettingsView et clic EN après scroll du vrai Flickable |
| 37 | Settings final status | PASS pour contrat locale UI ; aucune migration voix/traduction globale revendiquée |
| 38 | Mail Legacy functional yes/no | Oui : backend Gmail réel + raccord runtime historique |
| 39 | Mail Native equivalent | Non : aucun outil/service Gmail dans registre natif ; sendMessage seul ne constitue pas la parité |
| 40 | Mail parity blocker yes/no | OUI — NATIVE_PARITY_BLOCKER |
| 41 | Documents status | UI = helper conversation ; historique possède FilesProvider/GoogleLiveFilesBackend ; parité métier native non établie, à conserver ouverte |
| 42 | Contacts status | UI = helper conversation ; historique possède ContactProvider/GoogleLiveContactsBackend ; parité métier native non établie, à conserver ouverte |
| 43 | Maps status | Amorce navigation ; aucune vue Maps dédiée dans WorkspaceView local audité ; aucun développement ajouté |
| 44 | remaining Legacy-functional Native-missing routes | Mail confirmé ; Documents/Contacts à cadrer avant tout gate ; pas de nouveaux ports hors périmètre |
| 45 | runtime wiring | PASS, vraies instances de composition module + Core ; Weather/Diagnostics utilisent services runtime |
| 46 | context contract tests | PASS, membres coreBridge extraits dans Settings/ProviderIntegrations/Modules ; identité musicBridge et modèles |
| 47 | pre-cutover discovered tests | 462 |
| 48 | pre-cutover executed tests | 214 |
| 49 | pre-cutover PASS | 214 |
| 50 | pre-cutover FAIL | 0 |
| 51 | imports | 0 échec |
| 52 | timeouts | 0 |
| 53 | QML self-check | PASS : Music, Weather, Diagnostics, Modules, Settings, ADF |
| 54 | cutover gate | BLOCKED — Mail et parités métier non closes ; global offline sélectionné vert |
| 55 | run_native_ui.bat switched yes/no | NON ; fichier inchangé |
| 56 | app/main.py default | legacy, inchangé |
| 57 | explicit Legacy mode | Conservé : --core-mode legacy |
| 58 | SAME_COMPOSITION | FALSE pour A/B/C avant cutover : BAT et défaut = legacy, option explicite = native |
| 59 | Computer Use availability | NOT_AVAILABLE ; une tentative, apps=[] |
| 60 | live Music | NOT_AVAILABLE ; test Windows automatisé PASS ne vaut pas validation interactive |
| 61 | live Weather | NOT_AVAILABLE ; aucune requête météo réelle |
| 62 | live Diagnostics | NOT_AVAILABLE ; collecte locale et QML offscreen PASS |
| 63 | live Modules | NOT_AVAILABLE |
| 64 | live Settings | NOT_AVAILABLE |
| 65 | post-cutover tests | NON_APPLICABLE |
| 66 | post-cutover PASS | NON_APPLICABLE |
| 67 | post-cutover FAIL | NON_APPLICABLE |
| 68 | bytecode | 0 .pyc, scan workspace avec fichiers cachés/non ignorés |
| 69 | files modified | Liste ci-dessous ; preuves locales générées séparément |
| 70 | remaining parity blockers | Mail ; Documents/Contacts non établis ; capacités Music avancées stub non portées et hors périmètre de ce lot |
| 71 | remaining RC blockers | Validation Windows interactive ; parité métier ci-dessus ; validateur strict LOT1 bloque sur import Qt préexistant |
| 72 | next STRICT macro-step | Cadrer séparément Mail et les dépendances Documents/Contacts en lecture seule, avant autorisation de migration ; aucun nouveau lot commencé |

## Tests et preuves

- `test_music_qml_controls`, `test_settings_native`, `test_modules_native`, `test_runtime_wiring` : 6/6 PASS.
- Runner fresh : 108 modules découverts, 60 exécutés, 48 exclus ; 462 tests découverts, 214 exécutés, 248 exclus. 214 PASS, 0 FAIL, import failures=0, timeouts=0, status=complete. Les exclus ne sont PAS déclarés validés. ADF=35/35.
- `headless_latest.json`, `parity05_global.txt`, `parity05_targeted.txt`, six `parity05-qml-*.txt` sous tests/native/_evidence.
- Windows probe local : QApplication, aucun offscreen, aucune fenêtre AURA complète, WAV temporaire supprimé après shutdown.
- LOT1 strict tenté avec `-I -S -B ... --tests-only` : bloqué par import PySide6 du ReminderScheduler via composition. Aucun 37/37 revendiqué ; superviseur non modifié.

## Audit fonctionnel limité

`ModulesView.qml` est QML pur. Son panneau Mail transmet `affiche mes mails` à coreBridge.sendMessage ; cela ne prouve pas l’existence du service Mail. Sources historiques lues : `integrations/google/live_email_backend_v121.py` (search_messages/get_message/get_thread/create_draft/send_message) et `runtime/google_personal_integrations_bridge_v121.py` (raccord EmailProvider, ContactProvider, FilesProvider). Le registre natif expose Weather, Calendar et Tasks, pas Gmail/Contacts/Files. Aucun port de ces backends dans ce lot.

Travail nécessaire avant gate : établir les contrats Mail réellement requis (lecture/recherche/thread puis writes protégés si retenus), définir provider/service natifs et outils agent, tests FakeProvider et isolation credentials, intégrer les états indisponibles explicitement. Ne pas recopier l’ancien runtime ni réactiver RC4.2. Déterminer séparément si Documents/Contacts restent dans le périmètre fonctionnel obligatoire.

## Fichiers ajustés/créés

- `src/aura_native/ui/music_bridge.py`
- `src/aura_native/ui/module_composition.py (nouveau)`
- `src/aura_native/config/locale_service.py (nouveau)`
- `src/aura_native/bootstrap/composition.py`
- `src/aura_native/ui/qt_bridge.py`
- `app/main.py`
- `app/qml/Main.qml`
- `app/qml/views/NativeWorkspaceView.qml`
- `app/qml/views/ProviderIntegrationsView.qml`
- `app/qml/components/MusicSubdock.qml`
- `tests/native/test_music_qml_controls.py`
- `tests/native/test_settings_native.py (nouveau)`
- `tests/native/test_modules_native.py (nouveau)`
- `tests/native/test_runtime_wiring.py`
- `tests/native/test_native_isolation.py`
- `tools/run_native_headless.py`
- `tests/native/_evidence/music_windows_probe.py (harness local nouveau)`

Documentation : NATIVE_RUNTIME_PARITY.md, FUNCTIONAL_INVENTORY.md, RC_READINESS.md, INTERACTIVE_RC_CHECKLIST.md et docs/handoff/CURRENT_TASK.md. Le BAT reste inchangé. Les logs de preuve et state-dir fake sont locaux, non publiés.


Validation finale fraîche après les derniers ajustements : 214/214 PASS, 462 tests découverts, 248 exclus, 0 import failure, 0 timeout, status=complete ; durée 76.937 s. Deux timeouts Qt ont été observés sur un run intermédiaire à budget 15 s (test_live_module_qml et test_local_reminders_r1). Le test QML a repassé isolément ; le runner conserve une borne de 30 s pour les modules Qt autorisés, 15 s pour les autres. Aucun résultat de run incomplet ou en échec n’est utilisé pour la clôture. Les tests Settings et runtime wiring sélectionnent explicitement le FakeProviderCredentialStore, avec state-dir de test ; aucune préférence utilisateur réelle n’est changée.
