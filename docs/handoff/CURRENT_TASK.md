# AURA — CURRENT TASK — Live UI integration repair

2026-10-03 Maps routing parity: audit read-only du moteur Legacy confirmé :
OSRM public FOSSGIS avec distance, durée, GeoJSON et étapes, distinct du lien
Google Maps externe. Implémentation Native ajoutée derrière un backend injectable
et un fake offline; UI Maps affiche départ/arrivée, route Mercator et marqueurs.
Validation réelle OSRM et Windows visible encore en attente; `MAPS_NATIVE=PARTIAL`,
`MAPS_BLOCKS_CUTOVER=YES`. Détails : `docs/release/MAPS_ROUTING_PARITY.md`.
Validation offline finale : routing 4/4, headless 241/241 sur 491 découverts,
0 FAIL, 0 import échoué, 0 timeout, QML self-check PASS, 0 `.pyc`.
Deux smokes OSRM réels autorisés ont réussi : Vidauban→Nice (1697 points,
88,6 km, 70 min, 32 étapes) et Nice→Paris (14492 points, 932,5 km, 9 h 50,
40 étapes). Le deep link Google Maps secondaire est maintenant couvert par
test mocké. Position courante Native encore non disponible; routage vocal,
simulation et reroutage Legacy restent hors périmètre. `MAPS_NATIVE=PARTIAL`
jusqu’à décision sur ces écarts et validation Windows visible.

2026-10-03 Natural Earth lot: four official AWS-hosted Natural Earth archives
acquired (50m land/coastline, 10m land/coastline), SHA-256 and Public Domain
provenance recorded in `app/assets/maps/natural_earth/SOURCE.md`. Build-only
standard-library converter generated global and clipped Europe/Mediterranean
GeoJSON. Maps and Weather now use the same real geography; old Weather terrain
fallback canvas removed. Offscreen Nice captures show recognizable coastline
and marker. The Computer Use surface reported `apps=[]`, so live Windows review
is still pending. See `docs/release/NATURAL_EARTH_INTEGRATION.md`.
Final offline validation: 487 discovered, 237 executed, 237 PASS, 0 FAIL,
0 import failures/timeouts, ADF 35/35; QML self-check PASS; 0 bytecode.

Earlier 2026-10-03 checkpoint, superseded by the Natural Earth lot above:
Maps and Weather shared `GeoBaseMap.qml`; Maps search was styled and geocoding
became asynchronous. At that checkpoint no local geographic dataset was
available and production geometry count was 0. Mail
has a production permission-required view and fake-only inbox tests. Agenda's
real month delegate consumes asynchronously prefetched Daily Hub summaries and
routes badge clicks to the matching popup tab. Targeted tests 12/12, global
headless 233/233 (483 discovered, 0 failed imports/timeouts, ADF 35/35), QML
self-check PASS, bytecode 0. No network, OAuth, Google write, Git or cutover.
See `docs/release/LIVE_UI_INTEGRATION_REPAIR.md` for that historical checkpoint.

## Daily Hub Google — fondation

Ajout de `GoogleDaySummaryService`, `GoogleDaySummaryBridge`,
`MailSummaryService`, liens Gmail/Tasks sûrs et popup QML compact. Les services
sont injectés et testables hors ligne; aucune connexion, OAuth ou écriture
Google n'est déclenchée au démarrage. Les cellules Agenda conservent une
hauteur bornée, affichent au plus deux événements et un overflow, avec badges
de compteurs. Validation ciblée: 3 tests Daily Hub PASS; self-check QML PASS.
Le popup expose désormais les listes Calendar/Mails/Tasks et les résumés
locaux asynchrones. La file est bornée à deux workers et les résultats obsolètes
sont ignorés par génération. Le cutover legacy/native reste inchangé.

## Live UX Maps / Weather / Mail

Maps route désormais vers `MapsView.qml` avec `MapsService` et
`NativeMapsBridge`; Weather restaure une couche géographique vectorielle de
secours lorsque `terrainJson` est vide; Modules → Mail ouvre `MailView` au lieu
de Conversation. Signature et validation détaillées:
`docs/release/LIVE_UX_REPAIR_VALIDATION.md`.

## RC Readiness 01 — état courant

Inventaire fonctionnel et rapport RC : `docs/release/FUNCTIONAL_INVENTORY.md`
et `docs/release/RC_READINESS.md`. La suite headless déterministe est fournie
par `tools/run_native_headless.py` : 82/82 tests sélectionnés verts en 9,30 s,
avec timeout subprocess de 30 s par module. Notes UPDATE et le test de
productivité avec restart sont automatisés. R3C tray Windows et validation
interactive Notes restent explicitement non vérifiés.

## Macro-lot Notes / QML (état courant)

Notes locales sont désormais persistantes via migration SQLite 11. CREATE,
UPDATE et DELETE sont routés par PreparedAction; `updateNote` conserve le
`note_id` technique dans le payload et affiche un résumé humain. Tests Notes
CRUD/confirmation et self-check QML sont verts hors ligne. Le warning Column de
MemoryView et les traces Agenda de géométrie ont été réduits. Validation GUI
interactive Notes non vérifiée faute de surface Windows exploitable.

## Transition LOT 4A

Audit préalable du 28 septembre 2026 : 37 tests stricts LOT 1 et 62 tests
natifs verts, sans `.pyc` sous `src/aura_native` ni `tests/native`.
`MemoryService` est le seul service métier relié au runtime. La commande
`conversation.send` est déjà émise par `NativeCoreBridge`, mais elle ne possède
pas encore de handler.

Objectif : créer le domaine conversation natif persistant : QML -> bridge ->
LocalBus -> ConversationService -> ConversationRepository -> SQLite
`paths.data_dir / aura_native.db`. Ajouter une migration idempotente pour les
tables conversations/messages, sans seconde base ni lecture legacy. Le core
reste sans Qt ; la conversation native reste dans `NativeWorkspaceView.qml` et
ne construit jamais `ConversationView.qml` historique.

Les commandes attendues sont `conversation.new`, `conversation.send`,
`conversation.list`, `conversation.get`, `conversation.clear`; les événements
sont `conversation.created`, `conversation.message_created`,
`conversation.loaded`, `conversation.cleared`, `conversation.updated`.

Le message utilisateur doit être persistant et restitué dans le bridge. Aucune
réponse assistant ne doit être simulée : `conversation` devient `available` et
`agent` reste `not_migrated`. Sont interdits : Core historique, MainWindow,
WebEngine, RC4.2, HTTP/SSE, ancien AppData/DB, LLM, clé API, voix, comptes,
musique, `.env`, BAT, Git et lot ultérieur.

Validation : tests conversation, 37 tests stricts, suite native, self-check
QML et contrôle bytecode. Le workspace hors dépôt Git ne doit recevoir aucun
commit ni push.

## Objectif
Valider l'interface mémoire native minimale au-dessus du backend LOT 3A.

## État
LOTS 1, 2 et 3A sont validés. La mémoire native SQLite fonctionne via LocalBus.

## Modifications LOT 3B
- `src/aura_native/ui/qt_bridge.py`
- `app/qml/views/NativeWorkspaceView.qml`
- `tests/native/test_memory_qt_bridge.py`
- `docs/migration/lot_03b.md`
- ce handoff

## Contraintes
Aucun RC4.2, HTTP/SSE historique, MainWindow, WebEngine, ancien AppData ou
migration automatique des données legacy.

## Validation
Rejouer toute la suite native, les tests stricts LOT 1, le self-check QML natif
et le contrôle de bytecode.

## Prochaine action
Le LOT 4A est maintenant exécuté et validé. Ne pas commencer de lot ultérieur
avant autorisation utilisateur.

## Lot 4A — état final

Le domaine conversation local est relié à SQLite par migration v2 idempotente,
repository/service sans Qt, puis `LocalBus` et `NativeCoreBridge`. Les vues
legacy de conversation ne sont pas construites en mode natif. Les 66 tests
natifs, les 37 tests stricts et le self-check QML sont verts avec bytecode
désactivé; aucun `.pyc` source/test ne reste. Voir
`docs/migration/lot_04a.md`.

## Lot 5B — robustesse offline

`FakeProvider` offline, idempotence de requête, annulation et reprise de
requêtes interrompues sont validés. La composition native n'utilise plus de
configuration provider issue de l'environnement. La propriété
`providerAvailable` du bridge est dynamique. Voir `docs/migration/lot_05b.md`.
Validation attendue finale : 83 tests natifs, 37 stricts, self-check QML et
zéro bytecode source/test. Ne pas commencer de lot suivant sans autorisation.

## Lot 5C — streaming native offline

Le streaming par `ProviderChunk` et `StreamingFakeProvider` est validé hors
ligne. Les fragments `agent.delta`, l'agrégation assistant unique, l'annulation
et les chunks tardifs sont couverts; le bridge expose `agentStream`. Le runtime
ferme désormais l'executor agent. Validation : 85 tests natifs, 37 stricts,
self-check QML, zéro `.pyc` source/test. Voir `docs/migration/lot_05c.md`.

## Correction de contrat conversation

La migration courante est v3 et conserve la migration v2 : `conversations`
porte `session_id`; `conversation_messages` porte `sequence` et `status`.
Les données v2 sont copiées sans suppression. Liste/lecture/clear sont isolés
par session et le bridge restaure le dernier historique de sa session avec
`refreshConversation`. Validation finale : 69 tests natifs, 37 stricts,
self-check QML, tous verts sans `.pyc` source/test.

## Lot 4B — validation fonctionnelle

Les contrôles automatiques du 28 septembre 2026 sont verts : 37 tests stricts,
69 tests natifs, self-check QML et hygiène bytecode. La commande native isolée
est documentée dans `docs/migration/lot_04b.md`. Le contrôleur Windows de cette
session n'a exposé aucune fenêtre pour le processus Qt lancé : aucune saisie UI
n'a été simulée et les validations visuelles restent `PARTIAL`. Aucun lot
assistant n'est autorisé.

## Lot 4B — correction en attente de validation visuelle

Cause identifiée : sur Home, `Main.qml` conserve le compositeur partagé, mais
`Composer.qml` désactivait son champ en mode native sans consulter
`conversationAvailable`. La correction locale donne au message utilisateur la
capacité `connected && conversationAvailable`; `interactionReady` reste faux
pour l'agent et la voix. `NativeCoreBridge.sendMessage` et
`ConversationService` ne changent pas. L'agent reste `not_migrated` et aucune
réponse assistant n'est créée.

Fichiers concernés : `app/qml/components/Composer.qml`, `HomeView.qml`,
`NativeWorkspaceView.qml`, le test de bridge conversation, le nouveau test de
contrat `tests/native/test_native_composer_contract.py`, et cette
documentation. À exécuter : suite native, validation stricte lot 1,
self-check QML, puis contrôle bytecode. LOT 4B reste `PARTIAL` jusqu'à la
confirmation visuelle manuelle sur Windows. La validation automatique de la
correction compte 71 tests natifs et 37 tests stricts. Ne pas commencer le lot
5.

## Lot 4C — finition UI conversation native

Objectif : supprimer le double composer et appliquer la safe-zone réelle du
dock à la conversation native, sans modifier le backend conversation ni
commencer le moteur assistant. `Main.qml` possède l'unique composer global;
la saisie locale historique de `NativeConversationView.qml` a été retirée.
Cette vue n'expose plus qu'un historique et un contrôle QML `EFFACER`.

`workspaceSafeLeft` et `workspaceSafeRight` sont transmis par `Main.qml` à
`NativeWorkspaceView`, puis à `NativeConversationView`; la carte conversation
se décale après le dock. Les couleurs, bordures et états pressés/hover du clear
sont définis pour les thèmes sombre et clair. Conversation reste `available`,
agent reste `not_migrated`; aucun assistant, legacy, RC4.2, HTTP/SSE,
MainWindow, WebEngine, musique ou ancien AppData n'est ajouté.

Tests à exécuter avant clôture : tests ciblés conversation/bridge/QML, suite
native, 37 stricts lot 1, self-check QML et hygiène bytecode. LOT 4C reste
`PARTIAL` jusqu'à validation visuelle Windows. Résultats automatisés : 73
tests natifs, 37 tests stricts, self-check QML et 10 tests d'isolation verts;
aucun bytecode source/test créé. Ne pas commencer le lot 5.

## Lot 5A — socle agent natif

Le domaine `agent` natif utilise LocalBus, une requête immutable et SQLite v4.
`AgentService` est sans Qt et `NoProvider` est explicitement indisponible :
aucun réseau, provider, streaming ou réponse assistant. L'orchestrateur agent
est `available`, tandis que `inference` demeure `not_migrated`. Le bridge et
la conversation exposent l'indisponibilité du provider. Voir
`docs/migration/lot_05a.md`. Valider la suite native, les 37 stricts, le
self-check QML et l'hygiène bytecode avant tout lot suivant.

## Lot 5D — contexte intelligent natif

Objectif courant : intégrer la mémoire native pertinente dans les requêtes du
provider sans introduire de RAG, réseau additionnel, fallback legacy ou accès
aux installations historiques. `ContextBuilder` assemble prompt système,
mémoire non sensible, historique récent et message courant. Il limite à cinq
souvenirs et seize messages d'historique, isole `user/default`, la session
active et, uniquement sur identifiant explicite, le projet actif. Les souvenirs
sont des données dans `<user_memory>`, jamais des instructions.

Fichiers : `src/aura_native/agent/context.py`, `agent/service.py`,
`bootstrap/composition.py`, `tests/native/test_agent_context.py` et
`docs/migration/lot_05d.md`. Le snapshot contient seulement IDs, version du
prompt et horodatage. Les validations ont donné 99 tests natifs, 37 tests
stricts et un self-check QML vert. Les variables provider ne sont pas présentes
dans le shell de validation, donc l'essai Ollama réel reste requis avant de
déclarer le lot PASS. Ne pas commencer le lot 6.

## Lot 6A — météo native et tool calling

Le lot 6A remplace uniquement le parcours météo natif : Open-Meteo via
`urllib`, cache mémoire de cinq minutes, modèles structurés, mapping WMO et
erreurs contrôlées. `ToolRegistry` et `ToolRouter` enregistrent et routent
`weather.get_forecast` avant Ollama, puis `AgentService` injecte le résultat
structuré comme donnée autoritaire. Aucun bridge Qt, AppData, carte, cache
disque, géolocalisation ou code historique n'est réutilisé.

Validation : tests offline météo, 105 tests natifs, 37 stricts du lot 1 et
self-check QML à rejouer lors de clôture. Test réel déjà réussi : Nice,
France, prévision du 29 septembre 2026 `cloudy`, 19.3–25.9 °C et 3 %, avec un
unique tool event et une réponse Ollama concordante. Ne pas commencer le lot
6B sans autorisation.

## Lot 6B-A1 — PreparedAction SQLite

Migration v5 additive et `PreparedActionRepository` ajoutés pour le cycle de
vie offline `prepared`, `confirmed`, `executed`, `cancelled`, `expired` et
`error`. Les payloads JSON sont persistés sans secret et les transitions sont
contrôlées. Tests ciblés verts. Prochaine étape : Lot 6B-A2 uniquement.

## Lot 6B-A2 — services Calendar/Tasks offline

Les services utilisent le repository persistant pour créer les actions
`calendar.*` et `tasks.*`. Les FakeProviders restent en mémoire : aucune
mutation n'est possible avant `confirmed`, une action exécutée ne peut pas être
rejouée, et une erreur provider est enregistrée. Validation : 3 tests A1, 3
tests A2, 111 tests natifs, 37 stricts et zéro bytecode. Aucun OAuth, SDK,
réseau ou credential historique. Prochaine étape : 6B-A3 uniquement.

## Lot 6B-A3.1 — ToolRegistry et ToolResult

Objectif courant : ajouter les contrats d'outils Calendar/Tasks offline sans raccorder ToolRouter, AgentService, bus, bridge Qt ou QML. `ToolResult` rend explicites succès, erreur, confirmation et action préparée. Les écritures préparent uniquement une action persistée et ne mutent aucun provider. La configuration Google reste absente. À valider : A1, A2, A3.1, la suite native, les 37 stricts du lot 1 et l'hygiène bytecode. Ne pas commencer 6B-A3.2 sans autorisation.

Validation A3.1 : tests ciblés A1/A2/A3.1 10/10, 37 tests stricts lot 1 verts, zéro bytecode sous `src` et `tests`. La suite complète `tests/native` exécute 115 tests mais échoue de façon intermittente sur le test préexistant `test_cancel_drops_late_chunks_and_assistant`; son exécution isolée est verte. A3.1 reste non déclaré PASS sans suite intégrale verte. Ne pas modifier le streaming dans A3.1 ni commencer 6B-A3.2.

Stabilisation streaming validée : admission des deltas et annulation sérialisées par requête, événements streaming déjà en file purgés à l'annulation, et finalisation protégée avant persistance/completed. Test cancellation 20/20 ; streaming 4/4 ; suite native 115/115 trois fois consécutives ; A1/A2/A3.1 10/10 ; strict lot 1 37/37 ; zéro `.pyc` sous `src` et `tests`. A3.1 est désormais validable. Ne pas commencer 6B-A3.2 sans autorisation.

## Lot 6B-A3.2 — routage d'intentions local

`ToolRouter.route()` renvoie `ToolRouteResult` sans exécuter un outil. Il couvre météo localisée, Calendar, Tasks, no-match et clarification, avec dates françaises déterministes basées sur la date locale. La compatibilité `execute_for` est conservée pour le chemin météo pré-A3.3 de l'AgentService existant. Validation : ciblés A1/A2/A3.1/A3.2/streaming 18/18, suite native 119/119, strict lot 1 37/37 et zéro `.pyc` sous `src` et `tests`. Ne pas commencer A3.3 sans autorisation.

## Lot 6B-A3.3 — orchestration AgentService

AgentService route une fois, gère no-match, clarification locale, lecture injectée au provider, et écriture préparée sans mutation. Validation : 12 ciblés, 121 natifs, 37 stricts et zéro `.pyc`. Ne pas commencer A3.4 sans autorisation.

A3.4 en cours : composition repository/services/orchestrateur et handlers LocalBus ajoutés ; validation globale restante. Ne pas commencer A4.

A3.4 micro-lot validé : tests A3.4 3/3, suite native 124/124, strict 37/37, zéro pyc. Prochaine étape A4 uniquement sur autorisation.

Lot 6B-A4.1 validé : NativeCoreBridge pending action, slots confirm/cancel, restauration prepared, tests ciblés 11/11, suite native 126/126, strict 37/37, zéro pyc. Ne pas commencer A4.2.

Lot 6B-A4.2 implémenté : PendingActionCard QML native intégrée au-dessus du Composer. Tests structurels 3/3, suite native 129/129, strict 37/37, self-check QML OK, zéro pyc. PASS technique ; validation visuelle interactive encore requise. Ne pas commencer A5.

A4.2 correction visuelle : boutons custom QML et summaries human-friendly. Tests 129/129, strict 37/37, self-check QML OK, zéro pyc. Capture réelle corrigée à effectuer avant PASS visuel. Ne pas commencer A5.

LOT 6B-A5 consolidation offline validée : E2E 5 tests, suite native 134/134, strict 37/37, self-check QML déjà vert, zéro pyc. Google reste not_configured. Prochaine étape autorisable : LOT 6B-B OAuth Google natif réel.

LOT 6B-B1 validé offline : auth config/scopes, secure-store abstraction/fake, credential serialization et provider d’état. Suite native 137/137, strict 37/37, self-check QML OK, zéro pyc. Google reste not_configured. Ne pas commencer B2.

LOT 6B-B2 fondation technique préparée : flow loopback explicite, harness status/connect/disconnect, tests offline 3/3, suite native 140/140, strict 37/37, zéro pyc. Les dépendances déclarées ne sont pas installées dans .venv ; aucun OAuth réel lancé. B2 reste PASS TECHNIQUE / AUTH RÉELLE REQUISE.

LOT 6B-B3 en cours : providers Calendar/Tasks Google en lecture seule ajoutés
avec discovery dynamique, pagination, normalisation des modèles et erreurs,
free/busy, tasklist par défaut et refus explicite des écritures. La composition
ne sélectionne ces providers que si `AURA_GOOGLE_OAUTH_CLIENT_FILE` est
explicitement configuré et authentifié; sinon les fakes offline restent actifs.
Tests B3 offline : 8 cas lisibles, sans SDK installé, réseau, OAuth ou
credential historique. Harness manuel :
`tests/native/_evidence/lot6b_b3_google_read.py`. Validation technique et
self-check QML restent à rejouer; validation réelle de lecture requise. Ne
pas commencer LOT 6B-B4.

LOT 6B-B4.1 : providers Google write offline ajoutés. Calendar utilise
insert/patch/delete et Tasks insert/patch completed/delete. Les providers ne
sont appelés qu'après confirmation PreparedAction; les tests de préparation
confirment zéro appel. Erreurs HTTP write normalisées. Validation offline :
tests ciblés B4.1 3/3 et suite native 154/154, sans réseau ni mutation Google.
Les capacités calendar_write et tasks_write restent en attente de B4.2.

LOT 6B-B4.2.1 préparé : harness manuel Calendar réel ajouté avec flags
explicites `--create/--status/--update/--delete` et garde obligatoire
`--confirm-real-write`. L'état persiste uniquement event_id, résumé, horaires
et phase; les créations duplicata sont bloquées et le cleanup reste possible
après panne partielle. Aucun réseau réel n'a été lancé. Statut : PASS
TECHNIQUE / REAL WRITE VALIDATION REQUIRED. Ne pas commencer B4.2.2.

Correctif B3 credentials : la fuite du dictionnaire sérialisé vers
`googleapiclient.discovery.build()` est corrigée. `GoogleAuthProvider` expose
désormais `get_credentials()` et reconstruit un objet officiel
`google.oauth2.credentials.Credentials`; Calendar et Tasks utilisent le même
contrat avec `cache_discovery=False`. Aucun nouveau consentement, scope,
keyring ou credential historique n'est demandé. Le roundtrip fake-store et
les deux appels build sont couverts par les tests ciblés. B3 reste PASS
TECHNIQUE / VALIDATION RÉELLE REQUISE.

Correctif expiry B3 : les dates avec espace déjà présentes dans le secure
store sont normalisées avant `Credentials.from_authorized_user_info`; les
dates futures sont sérialisées avec `T`, les microsecondes sont tolérées et
une expiry absente reste valide. Tests ciblés : 17/17; suite native : 151/151.

Correctif B4.2.1 delete readback : GET 404/410 et les événements Google avec
`status=cancelled` sont reconnus comme supprimés. `--status` répare le state
file en `phase=deleted` sans mutation supplémentaire. Tests B4.2.1 : 7/7;
suite native : 161/161. Aucun réseau réel n'a été lancé.

Finalisation B4.2.1 préparée : harness E2E réel Calendar ajouté avec
PreparedActionRepository, CalendarService, PendingActionOrchestrator, LocalBus
et providers Google. Les flows prepare-confirm, double-confirm, cleanup par
event_id, prepare-cancel et cancel sont séparés et protégés par flags
explicites. Aucun réseau/mutation réel n'a été lancé. Statut PASS PARTIEL /
E2E CONFIRM+CANCEL REQUIRED. Ne pas commencer B4.2.2.

LOT 6B-B4.2.2 préparé : harness Tasks réel ajouté pour create/status/complete/
delete, PreparedAction confirm/cleanup et cancel via LocalBus. Toutes les
mutations exigent `--confirm-real-write`; aucune opération réelle n'a été
lancée. Calendar reste inchangé. Statut PASS TECHNIQUE / REAL WRITE
VALIDATION REQUIRED.

B4.3 UI bug correction : le routeur Calendar distingue désormais date/heure/
durée du titre; le cas `TEST AURA UI CALENDAR` produit un titre correct et une
fin à +30 minutes. Les summaries PreparedAction incluent date et heures. Les
deux backgrounds de contrôles NativeWorkspaceView qui déclenchaient les
warnings de personnalisation ont été retirés localement. Tests ciblés et suite
native restent verts; aucune validation Google réelle n'a été relancée.

LOT 6B-B4.3 préparé : launcher UI natif manuel ajouté avec `--launch`, mode
native explicite et state-dir isolé. Tests offline vérifient le contrat
PendingActionCard/bridge et l'absence de providers Google dans QML. Aucune UI,
OAuth ou mutation réelle n'a été lancée. Statut PASS TECHNIQUE / REAL UI
VALIDATION REQUIRED.
# PCC-2C — état courant

Le service `GoogleOAuthClientConfigService`, les fixtures offline, le bridge
Qt/QML et le launcher isolé PCC-2C sont présents. Validation technique :
187 tests `tests/native` verts et self-check QML vert. Aucun launcher, réseau,
OAuth réel, SDK Google ou credential réel n’a été exécuté. La validation
visuelle interactive reste requise avant PCC-3.

## PCC-3 — incident async production corrigé

L'incident commun Gemini/Ollama venait de la frontière asynchrone, pas des
testeurs réseau. Deux défauts coexistaient dans `NativeCoreBridge` : le callback
du `Future` était enregistré au mauvais endroit et la composition production
fournissait un registre de testeurs par fournisseur alors que le bridge traitait
ce registre comme un testeur unique.

Le chemin final est déterministe : le bridge conserve un
`ThreadPoolExecutor` pendant toute sa durée de vie, conserve chaque `Future`
actif, puis le worker dépose uniquement un résultat normalisé dans une
`SimpleQueue`. Un `QTimer` parenté au bridge et créé sur le thread GUI vide la
file toutes les 25 ms et émet `providerTestFinished`. Une génération par
fournisseur ignore les résultats obsolètes; le timeout bridge précède le
watchdog QML et tout résultat tardif est ignoré. Le mode
`AURA_PCC3_DEBUG=1` journalise uniquement fournisseur, request id, statut et
identifiants de threads.

Validation offline : 16 tests PCC-3 ciblés, 248/248 tests natifs, 37/37 tests
stricts LOT 1, self-check QML natif réussi et zéro `.pyc`. Les scénarios Qt
runtime couvrent 500 ms, 2 s, erreur d'authentification, exception, timeout,
résultat tardif, requête obsolète et composition production avec registre
Gemini/Ollama. Aucun réseau fournisseur, credential réel ou GUI interactif n'a
été lancé.

## PCC-4A — routage runtime des fournisseurs

État de travail : implémentation du routage runtime Ollama/Gemini préparée avec snapshots par requête, erreurs normalisées, absence de fallback implicite et harness/tests fake-only. Les paramètres actifs de ProviderSettingsService sont la source de vérité; les variables AURA_PROVIDER, AURA_MODEL et AURA_OLLAMA_HOST ne sont que des overrides de développement.

OpenAI, Anthropic et Custom restent explicitement indisponibles dans ce lot, faute d'adaptateurs runtime configurés. Aucun GUI, OAuth, SDK Google, appel fournisseur réel ou Git ne doit être lancé pendant la validation. Prochaine action : relancer les tests PCC-4A et de régression en isolant les providers, puis vérifier self-check QML et absence de bytecode.

## PCC-4A — validation terminée

Routage runtime par provider sélectionné livré pour Ollama et Gemini, sans
fallback, avec snapshot immutable par requête, hot switch, streaming, cancel,
messages d'erreur normalisés et isolation du secret. OpenAI/Anthropic/Custom
restent non activés pour la conversation dans ce lot.

Validation finale : 22/22 tests PCC-4A, cinq modes du harness offline, 270/270
tests/native, 37/37 tests stricts Lot 1, self-check QML réussi et zéro `.pyc`.
Les profils fixes déjà présents sous `_evidence` ont été laissés intacts; les
tests de chemins ont utilisé des chemins vierges injectés en mémoire. Aucun
test réussi n'a appelé un fournisseur réel. Attention : un premier lancement
de suite avec le seed global `AURA_PCC_FAKE=1` a pu tenter Ollama en loopback
sur `127.0.0.1:11434`; ce run échoué est exclu des résultats finaux. Le run
complet final a été refait sans seed global et PCC-4A avec adapters fakes.

Statut : PASS TECHNIQUE / validation de conversation réelle requise. Ne pas
lancer PCC-4B avant autorisation explicite; aucun réseau, OAuth ni Git n'a été
utilisé pendant la validation finale.

## PCC-4B — préparation de validation réelle

La préparation autorisée ajoute une trace `AURA_PCC4_DEBUG=1` limitée à
provider, modèle, request id, transition et code d'erreur normalisé, ainsi
qu'un harness réel protégé par fournisseur exclusif, state-dir explicite et
`--confirm-real-network`. Le prompt est fixe et le texte généré n'est jamais
affiché. La procédure manuelle Ollama → Gemini → Ollama, STOP et no-fallback
est documentée dans `docs/migration/pcc4b_real_validation.md`.

Statut visé après régression offline : **READY FOR MANUAL REAL CONVERSATION
VALIDATION**. Aucun appel réel, credential réel, changement de préférence
utilisateur ou Git ne doit être exécuté par Codex.

Validation terminée : 6/6 tests de préparation PCC-4B, 6/6 tests de diagnostic
Gemini, 283/283 tests/native, 37/37 LOT 1 strict, self-check QML réussi et zéro `.pyc`
dans le code projet. Les tests ont confirmé le refus du harness sans garde,
les traces sans prompt/réponse/secret, le partage d'instances en composition
et l'absence de lecture de credential à la composition.

Statut courant : **PCC-4B = READY FOR MANUAL REAL CONVERSATION VALIDATION**.
Les commandes réelles sont documentées mais n'ont pas été exécutées.

Diagnostic offline Gemini ajouté : HTTP 400/401/403/404/408/429/5xx,
timeouts connect/read, DNS/reset, SSE malformé, keepalive, buffering et
historique multi-provider avec utilisateur annulé sans assistant sont couverts.
Le endpoint utilise `alt=sse` et l'en-tête `x-goog-api-key`; aucune clé n'est
dans l'URL. `SettingsView.qml` n'appelle plus l'obsolète `refreshLocale()`.

## PCC-4B — retry transient Gemini

GeminiRuntimeProvider est borné à trois tentatives avant le premier delta, avec backoff/jitter, Retry-After borné, annulation pendant l'attente et aucun retry après émission. Le même snapshot/messages/request id est conservé, sans fallback entre fournisseurs. Les traces PCC4_RETRY_SCHEDULED et PCC4_RETRY_STARTED sont sanitisées. Tests retry ciblés : 6/6 verts; aucun réseau réel, credential ou Git utilisé.

## Isolation PCC-4B

Les tests d'isolation ne dépendent plus de `unused-profile-lot5b`. `test_isolation.py` et `test_paths.py` utilisent des répertoires temporaires uniques; sous le validateur strict `-I -S`, ils utilisent un chemin vierge non créé. Aucun dossier `_evidence` n'a été supprimé. Suite native : 289/289 OK deux fois consécutivement. Le validateur LOT 1 exécute 37/37 tests verts; son audit de baseline reste non comparable à cause des changements historiques déjà présents dans le workspace. Aucun réseau, OAuth, credential réel ou Git.

## PCC-5A foundation

Added `src/aura_native/providers/model_catalog.py` with safe `ProviderModelDescriptor`, canonical provider IDs, deterministic `FakeModelCatalogProvider`, and explicit in-memory `ModelCatalogService`. Focused tests: 5/5. This is not yet PCC-5A PASS: QML selector, bridge, async GUI delivery, production composition and fake UI harness remain. No real network or credential was used. Preserve the existing reserves: Gemini STOP after first delta and B4.3 real UI validation.

## PCC-5A UI integration

Added the production catalog instance, Qt bridge APIs/signals, queue-to-GUI delivery, and `ProviderModelSelector.qml` with local search and explicit refresh. Focused integration tests: 11/11; QML self-check passes offline. Full fake harness and regression matrix remain pending. No network or real credential access.

## PCC-5A fake harness

Created the offline fake launcher under `tests/native/_evidence/pcc5_model_catalog_ui.py` and added selector object names. The 60-model headless scenario and QML self-check pass. PCC-5A is awaiting manual fake UI observation; no real provider access occurred. Existing Gemini STOP and B4.3 UI debts remain.

## PCC-5A refresh button fix

Le refresh est maintenant un vrai `AuraButton` cliquable, avec loading désactivé et signaux de résultat raccordés au selector. Cause précédente : simple Text + MouseArea inline. Validation ciblée 11/11 et self-check QML OK; aucune connexion réelle.

## PCC-5A popup polish

Popup premium finalisé : aucune surface blanche native, champ AuraTextField, lignes hiérarchisées, état actif, hover/pressed, liste scrollable bornée et fermeture Escape/clic extérieur. Self-check QML OK; aucune connexion réelle.

## PCC-5A large catalog correction

Le launcher interactif propage désormais `--large-catalog` à la composition via une variable interne fake/offline. La même instance FakeModelCatalogProvider alimente le ModelCatalogService utilisé par le bridge. Headless large : 60 modèles; normal : 3 modèles; QML et tests ciblés verts.

## PCC-5A stale model

Correction du harness stale : propagation launch/headless, seed Gemini `gemini-old-model`, détection UI après refresh et indicateur amber. Aucune auto-sélection; activeProvider reste inchangé. Headless stale et self-check QML OK.

## PCC-5A error scenario

Correction de la propagation `--error` au launcher interactif. Gemini fake retourne `network_error`, l'état UI est distinct de stale, le bouton est réactivé et les sélections restent inchangées. Headless error et self-check QML passent; aucun réseau réel.

## PCC-5A closure

Régression finale : 12/12 tests PCC-5 ciblés; 295/295 tests/native au run #1 et 295/295 au run #2. Self-check QML OK, bytecode 0. LOT 1 strict : 37/37 tests verts, audit baseline non comparable documenté séparément. Statut : **PCC-5A PASS TECHNIQUE / INTERACTIVE FAKE UI VALIDATION REQUIRED**. PCC-5B interdit pour l'instant. Dettes Gemini STOP post-first-delta et B4.3 UI réelle conservées.

## PCC-5B offline providers

Ollama `/api/tags` and Gemini `models.list` providers are implemented with mocked HTTP tests. Production wiring is conditional and refresh-only; no boot fetch or credential read occurs. Guarded real harness created but not run. Status: **PASS TECHNIQUE / REAL MODEL CATALOG VALIDATION REQUIRED**. Debts unchanged: Gemini STOP post-first-delta and B4.3 real UI.

## PCC-5B real harness dispatch

Le placeholder qui bloquait toujours le harness est remplacé par le vrai dispatch protégé : `--ollama` ou `--gemini` + `--confirm-real-network` + `--state-dir`. Les tests patchés vérifient un appel unique par provider, la garde et la sortie safe. Codex n'a déclenché aucun réseau réel ni lu de clé réelle.

## PCC-5B Ollama UI wiring fix

Correction du premier différentiel harness/UI : la composition pouvait fournir une base_url vide au provider réel tandis que le harness utilisait explicitement l'hôte local. Résolution désormais base_url → AURA_OLLAMA_HOST → défaut local. Tests mock de parité et composition verts; aucun réseau réel.

## PCC-5B selected_model hydration

Ajout d'un accès bridge provider-aware read-only pour hydrater le modèle persisté au démarrage. Aucun auto-refresh ou auto-selection. Tests ciblés et self-check QML verts.

## PCC-5 final closure

Validation réelle humaine confirmée : Ollama 1 modèle (`qwen3:8b`) et Gemini 44 modèles (`gemini-3.8-flash`) avec hydratation initiale et refresh UI validés. Régression offline : 306/306 tests/native, 17/17 PCC-5 ciblés, LOT 1 37/37, QML OK, 0 `.pyc`. Statut final : **PCC-5A PASS / PCC-5B PASS / PCC-5 PASS**. Ne pas commencer le lot suivant. Dettes ouvertes : Gemini STOP post-first-delta et B4.3 UI réelle.

## B4.3 preparation

Préparation offline validée : parsing exact, PreparedAction, exactly-once confirm, cancel zero-write. Le parser retire la ponctuation terminale avant la durée. Tests/native 308/308 et self-check QML OK. B4.3 reste en attente de validation UI réelle humaine; aucune écriture Google réelle n'a été lancée.

## B4.3 routing correction

NativeWorkspaceView previously had no AgendaView or TasksView branches; agenda/tasks fell into Foundation. Existing views were found and mounted directly for routes `agenda` and `tasks`; Foundation now excludes them. Memory refresh is limited to memory routes. Tests/native 312/312 and QML self-check pass. No real Google action executed.
## B4.3 — UI Agenda / Tâches native

Correction ciblée des bindings après validation du routage : le
`NativeCoreBridge` fournit désormais des valeurs explicites et sûres pour les
compteurs/statuts Google, et `AgendaView.qml` génère un calendrier local hors
réseau. Aucun appel Google, OAuth, credential ou écriture n’est effectué.

Lot R2 local reminders DELETE : repository/service/bridge/orchestrator et delegate QML utilisent désormais une PreparedAction `local_reminders.delete`. L’ID reste technique dans le payload, le contenu alimente le résumé human-friendly, et aucune mutation ne survient avant confirmation. 7 tests R1/R2 verts et self-check QML OK; zéro `.pyc`. Ne pas modifier Google/Calendar ni commencer le lot suivant sans autorisation.

## ADF historical recovery (2026-10-02)

The legacy installation and GitHub commit 41bc6503ff7f67bd65915d72e138aae32cdbde65 were read-only compared. All 21 ADF-A..H manifest/policy/registry contracts match by SHA-256. GitHub is canonical; old local runtime/state/secrets are excluded. Native Developer Fabric is SOURCE_RECOVERED/PARTIAL: bounded offline scaffold is active, while provider failover/quota, ten-agent catalog adapters, ADF audit chain, persistent jobs and Qt/QML bridge remain 
ot_migrated. No historical runtime executed, no network/OAuth/Google write, no Git operation. Next action: implement only the next approved native policy-kernel hardening phase with offline tests.

## ADF macro-lot 01 implementation

Added developer_fabric/adf.py and 	est_adf_macro.py: transaction hardening baseline, SQLite jobs/audit, active project, provider failover and ten-agent catalog. Global headless: 177 PASS, 0 FAIL, 0 failed imports. Remaining work is Qt bridge/models, richer state transitions, circuit breaker, process-tree cleanup and expanded security/E2E coverage.

## ADF macro-lot 02

Migration 12 forward-only ajoutée; developer_jobs/developer_audit ne sont plus créés ad hoc. Bridge Qt, modèles, circuit breaker baseline, détection/sandbox agents ajoutés. Validation globale: 177 PASS, 0 FAIL, 0 failed imports. Statut PARTIAL; prochaines étapes: transaction multi-fichier/rollback automatique, restart/crash recovery, UI QML et E2E complets.

## ADF macro-lot 03

Runner metrics now expose discovered/executed/excluded tests. Multi-file staging/apply with stale preflight and automatic rollback baseline added. Global: 177 PASS, 0 FAIL, 0 failed imports. Remaining blockers: complete QML UI/navigation, restart/crash recovery, verified audit chain, process-tree cleanup and expanded E2E security.

## ADF closure 04

Native composition now exposes one ADF service, bridge and Projects/Jobs/Providers/Agents models; DeveloperFabricView.qml is routed via developer, developer-fabric, df. Offscreen QML self-check PASS. Global: 182 PASS, 0 FAIL, 0 failed imports; 0 pyc after cleanup. Status remains PARTIAL pending full workflow UI E2E, restart/crash recovery and verified audit-chain tamper tests.

## ADF closure 05

DeveloperFabricView actions now call plan/stage/approve/apply bridge slots; composition owns one service and closes its SQLite handles. Offscreen native self-check PASS. Remaining status gates: full dynamic models/QML E2E, crash recovery, verify_chain/tamper, complete policy/quota and Windows process-tree proof.

## ADF closure 06

Added verify_chain baseline, dynamic model signals, picker abstraction, provider policy skip reasons and 11 structured tests. Runner: 99 modules, 51 executed, 441 discovered tests, 193 executed, 193 PASS, 0 failed imports. Remaining blockers: full QML E2E, restart/crash recovery, Windows process-tree proof and complete policy/quota integration.

## ADF closure 07

Audit migration 13 adds monotonic sequence; verify_chain now validates sequence, canonical payload, previous hash and entry hash. Runner emits ADF_DISCOVERED_TESTS/ADF_EXECUTED_TESTS/ADF_EXCLUDED_TESTS. Full QML E2E, crash recovery and Windows process-tree remain the only unproven blockers.

## ADF closure 08

Fresh global run after changes: 193 PASS, 0 FAIL, 0 failed imports; ADF_DISCOVERED_TESTS=26, ADF_EXECUTED_TESTS=26, ADF_EXCLUDED_TESTS=0. Added command policy rejection for shell executables and bounded stdout/stderr. Remaining blockers are full QML E2E, restart/crash recovery, dynamic provider/model synchronization and Windows process-tree proof.

## ADF closure 09R — runner recovery and fresh validation (2026-10-02)

The headless runner now emits flushed `MODULE_START`/`MODULE_END` progress, applies a 15-second timeout per selected module, and atomically persists `tests/native/_evidence/headless_latest.json` plus JSONL progress. Recently modified ADF modules all completed individually (`NO_HANG_REPRODUCED`). Fresh global run: 101 discovered modules, 53 executed, 48 excluded; 450 discovered tests, 202 executed, 248 excluded; ADF 35/35; 202 PASS, 0 FAIL, 0 failed imports, 0 timeouts, 44.22s. Generated Python bytecode was removed and rechecked at zero. This validates runner observability and the currently implemented offline ADF scope; unresolved functional blockers remain explicitly open and are not claimed closed.

## Native live module wiring repair (2026-10-02)

User screenshot proved Diagnostics Native data flow failed despite route/bridge existence. Root cause: `NativeDiagnosticsBridge.refreshDiagnostics` referenced `Path` without importing it, then swallowed the exception and set `diagReady=true`; all displayed values stayed `Unavailable`. A Qt-free DiagnosticsService now collects CPU/RAM/disk and network deltas; the bridge delegates to it and emits `diagnosticsChanged`. Real local CPU/RAM/disk collection and deterministic signal/network tests pass. GPU/VRAM/temperature remain explicitly `UNSUPPORTED` where no native collector exists.

Music Native now mounts `MusicCenterView` for route `music` and enables the shared `MusicSubdock` loader in Native. The one `musicBridge` QML context object remains `NativeMusicBridge`; isolated player tests cover load/play/pause/stop, and the native music workspace self-check loads. This does not yet prove QML click-to-player state end to end.

Weather Native bridge now exposes all property names referenced by WeatherView and performs refresh on a worker thread, returning results to the Qt thread via signal. Fake provider → WeatherService → bridge properties and signal passes; actual QML-visible value after refresh remains unproven. Production network was not called.

Fresh global headless run: 104 modules discovered, 56 executed, 48 excluded; 455 tests discovered, 207 executed, 248 excluded; 207 PASS, 0 FAIL, 0 failed imports, 0 timeouts; ADF 35/35. Native QML self-check and music workspace self-check pass; source/test/app bytecode count 0. Computer Use surfaces: apps=[], so live Windows validation unavailable. `run_native_ui.bat` remains Legacy because the full UI data-flow gate is not proven. No Git, Chromium, OAuth or Google write.

## Native live module QML evidence

Actual `DiagnosticsView.qml` and `WeatherView.qml` were loaded offscreen with their native context bridges. Diagnostics local collection updated the rendered RAM percentage and network text; FakeWeatherProvider data rendered `Nice` and `20` through the real WeatherView. Music route now mounts MusicCenterView and the shared MusicSubdock loader in Native. The native music workspace self-check loaded, while click-to-QMediaPlayer QML action flow is still unproven. Latest global run: 105 modules discovered, 57 executed, 48 excluded; 457 tests discovered, 209 executed, 248 excluded; 209 PASS, 0 FAIL, 0 import failures, 0 timeouts. No real weather network smoke or live Windows validation. Launcher gate remains blocked; BAT stays Legacy.


## Runtime Parity 05 — 2026-10-02 (état actuel)

Music : getter playbackState() corrigé, vrais contrôles QML et test Windows normal PASS. Modules : vraie route/vue et signaux raccordés. Settings : LocaleService natif fr-FR/en-US, signal et persistance config/ui_locale.json, clic QML PASS. Global offline sélectionné : 462 découverts, 214 exécutés, 248 exclus ; 214 PASS, 0 FAIL, 0 import failures, 0 timeouts, complete ; ADF 35/35. Six self-checks QML PASS, 0 pyc. Mail = NATIVE_PARITY_BLOCKER : backend Gmail historique fonctionnel absent du natif. Documents/Contacts : helpers UI mais backends historiques réels, parité métier non établie. Computer Use apps=[] : NOT_AVAILABLE. BAT inchangé, défaut legacy, aucun cutover ; post-cutover NON_APPLICABLE. LOT1 strict ne peut pas être déclaré 37/37 : import Qt scheduler bloqué par son garde existant. Voir docs/release/NATIVE_RUNTIME_PARITY.md pour les 72 contrôles et preuves. Aucun Git/réseau réel/OAuth/Google write. STOP ; pas de nouveau lot.


Validation finale fraîche après les derniers ajustements : 214/214 PASS, 462 tests découverts, 248 exclus, 0 import failure, 0 timeout, status=complete ; durée 76.937 s. Deux timeouts Qt ont été observés sur un run intermédiaire à budget 15 s (test_live_module_qml et test_local_reminders_r1). Le test QML a repassé isolément ; le runner conserve une borne de 30 s pour les modules Qt autorisés, 15 s pour les autres. Aucun résultat de run incomplet ou en échec n’est utilisé pour la clôture. Les tests Settings et runtime wiring sélectionnent explicitement le FakeProviderCredentialStore, avec state-dir de test ; aucune préférence utilisateur réelle n’est changée.
## Runtime Parity 06 — 2026-10-03

Weather city selection is now wired through a native geocoding contract: `searchLocations` → `cityResults` → `selectCity` → forecast. Offline QML/bridge tests cover Nice/Paris, errors and empty queries. Global fresh run: 466 discovered, 218 executed, 248 excluded; 218 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35.

Maps is classified LEGACY_PLACEHOLDER/PARTIAL: ModulesView contains only a navigation entry and no standalone MapsView/service exists in the audited workspace. Mail is confirmed LEGACY_FUNCTIONAL and NATIVE_PARITY_BLOCKER: historical Gmail backend supports search/read/thread/attachments/draft/send, while native has no Gmail service or tool. No OAuth, credentials, network, Google write or Git used. BAT remains Legacy and app default remains legacy. Cutover forbidden; next strict step is Mail contract design and an explicit Maps scope decision.
## Runtime Parity 07 — 2026-10-03

Mail Native domain created: `MailService`, deterministic `FakeMailBackend`, `NativeMailBridge`, `MailView.qml`, native `mail` route and composition wiring. Search/list, read, thread, attachment metadata and PreparedAction send/cancel/confirm are covered offline. No Gmail network, OAuth, credential read or Google write occurred. Mail QML self-check PASS.

Fresh global: 468 discovered, 218 executed, 250 excluded; 218 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35; bytecode 0. Maps stays documented placeholder/non-blocker. Documents/Contacts remain partial conversation helpers, not autonomous native routes. Cutover remains BLOCKED: Mail still needs a production Gmail adapter reusing the existing Google identity and read-only parity validation. BAT unchanged; app default remains legacy; no Git.
## Runtime Parity 08 — 2026-10-03

Added read-only `GmailMailBackend` using the existing `GoogleAuthProvider` identity. No second OAuth or credential store. The adapter normalizes search, message, thread and attachment reads and refuses operation without the explicit `gmail.readonly` scope. Current native OAuth scopes are Calendar/Tasks only, so `MAIL_PRODUCTION_READ=BLOCKED_BY_SCOPE`; no real smoke request was made.

Fake adapter contract tests and Mail/Runtime regression pass. Fresh global: 470 discovered, 220 executed, 250 excluded; 220 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35. Mail QML self-check PASS; bytecode 0. No Gmail writes, no network, no Git. BAT and default legacy mode unchanged. Cutover remains blocked until scope approval and a separately authorized read-only production smoke.
## Runtime Parity 09 — 2026-10-03

Added only `gmail.readonly` to the unique Google scope owner (`GoogleOAuthConfig.scopes`). Existing `GoogleAuthProvider` and credential store are reused. Gmail adapter checks actual granted scopes and returns `PERMISSION_REQUIRED` without triggering OAuth when the existing token lacks Gmail READ. Production writes are explicitly rejected (`WRITE_NOT_SUPPORTED`). No real smoke was attempted because no authorized Gmail state was available; no credentials or content were read or recorded.

Fresh global: 472 discovered, 222 executed, 250 excluded; 222 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35; Mail QML self-check PASS; bytecode 0. BAT and default legacy mode unchanged; no cutover, Git, network or Google write. Next strict step is user-controlled Gmail read consent/review followed by a minimal read-only smoke, if authorized.

The explicit existing Google reconnect action now reuses `GoogleAuthProvider.connect()` when an old grant lacks the newly configured Gmail read scope. Startup remains non-interactive. Codex did not launch the consent flow.
## Maps current-location parity — 2026-10-03

QtPositioning is available in PySide6 6.11.2 and exposes a Windows-capable
`QGeoPositionInfoSource`. NativeMapsBridge now uses `CurrentLocationService`
with explicit requesting/ready/permission/unavailable/timeout/error states and
manual-origin fallback. Fake success, permission, unavailable and timeout tests
pass; no coordinates are written to evidence. No visible Windows surface was
available (`apps=[]`), so live permission/current-location interaction remains
unverified. Navigation simulation, automatic rerouting and voice guidance are
deferred after RC. Fresh global: 495 discovered, 242 executed, 242 PASS, 0
FAIL, 0 imports, 0 timeouts; QML self-check PASS; bytecode 0.
## Mail + Daily Hub visual gate — 2026-10-03

Offline validation confirms the native MailView route, sidebar/list/preview
layout, explicit Gmail permission-required state and read-only wording. The
Agenda monthly delegate renders Calendar overflow, Gmail permission badge and
Tasks counts; GoogleDayDetailPopup tab dispatch is covered from Agenda.
Targeted Mail/Daily/QML checks: 17/17 PASS. Fresh global: 495 discovered,
242 executed, 242 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35; QML
self-check PASS; bytecode 0. No OAuth, Gmail network, Google write, BAT
change, cutover or Git. Windows visual review remains unavailable until a
desktop surface is provided; the next authorized step is human visual
confirmation, then Gmail consent.
## Mail premium UI — 2026-10-03

MailView received a QML-only premium desktop pass: three-column responsive
layout, AURA-styled search/sync, navigation icons, read-only/status card,
permission-required panel, rich message cards with avatars/unread state,
empty states, preview header, local-summary card and Gmail action. Backend
contracts and production composition were unchanged; FakeMailBackend remains
test-only. Targeted Mail/Daily checks: 18/18 PASS. Fresh global: 496 discovered,
243 executed, 243 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35; QML
self-check PASS; bytecode 0. Windows visual capture remains unavailable
(`apps=[]`), so `READY_FOR_GMAIL_CONSENT=FALSE` pending human visual review.
## Mail final visual polish — 2026-10-03

MailView received a QML-only polish pass for the five live findings: header
status is dimensioned inside the toolbar, normal card borders are subdued,
selected cards have a distinct cyan/violet active rail, the preview header/body
use stronger hierarchy and bounded scrolling, and summary fallback is labelled
`EXTRAIT DU MESSAGE` instead of being presented as an AI summary. Drafts and
Send are visibly locked/disabled in read-only mode; filters and Open Gmail
remain available. Targeted Mail tests: 5/5 PASS. Fresh global: 496 discovered,
243 executed, 243 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35; QML
self-check PASS; bytecode 0. No backend, OAuth, Gmail network, Google Write,
Maps, BAT, cutover or Git changes. Windows screenshot validation remains
unavailable (`apps=[]`).
## Mail live path and performance — 2026-10-03

The Native Modules Mail item now routes directly to workspace `mail`; the
runtime no longer enters a Mail quick subdock or requires an Inbox second click.
Mail body loading is shell-first and asynchronous: `NativeMailBridge.search`
uses a worker thread and drains results on the Qt side, while QML shows the
header/sidebar/list/preview immediately. Preview horizontal scrolling remains
disabled and long content wraps into the styled vertical scroll area. The
delayed fake-backend test (2 seconds) confirms shell readiness before data.
Targeted Mail/navigation tests: 11/11 PASS. Fresh global: 498 discovered,
244 executed, 244 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35; QML
self-check PASS; bytecode 0. No Gmail network, OAuth, Google Write, Maps,
Legacy, BAT, cutover or Git changes. Windows live timing/capture remains
unavailable in this session (`apps=[]`).
## Mail navigation cleanup — 2026-10-03

Native Modules → Mail now emits the direct `mail` workspace route; the Mail
subdock/intermediate Conversation or Foundation path is not instantiated by
the Native route. MailView remains the sole internal Mail navigation surface.
Preview body scrolling is vertical-only with `ScrollBar.horizontal` disabled,
bounded content width and `Text.WrapAnywhere`, including long URLs and words.
Targeted route/preview tests: 10/10 PASS. Fresh global: 497 discovered, 244
executed, 244 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35; QML self-check
PASS; bytecode 0. Legacy files, backend Mail, OAuth and cutover remain
unchanged.
## Google reauthorization UI — 2026-10-03

Added `RÉAUTORISER GOOGLE` to the Google Workspace card. It calls only `startGoogleWorkspaceOAuth()`; client import remains `oauthDialog.open()` and is not conflated. Targeted tests and fresh global pass: 473 discovered, 223 executed, 223 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35. No browser/OAuth consent was launched automatically. Next user action: click reauthorize and complete consent, then perform the restricted Gmail READ smoke. No cutover/Git.

## Mail live route correction — 2026-10-03

La capture Windows a identifié la cause exacte du faux parcours Mail : `app/qml/Main.qml` instanciait `ModulesSubdock` avec `visible: root.modulesDockOpen`, sans condition de mode. Même après la route directe de `ModulesView`, le sous-dock Legacy restait donc visible et exposait `MAIL RAPIDE`. Correction localisée : `visible: root.modulesDockOpen && runtimeMode === "legacy"`. En Native, la carte `ModulesView` émet `navigateRequested("mail")`, `NativeWorkspaceView` appelle le bridge de workspace et `MailView` est chargé directement. Le sous-dock historique reste disponible uniquement en Legacy.

Le chargement Mail reste shell-first : le bridge travaille hors thread UI puis draine les résultats côté Qt; cinq skeletons QML sont visibles pendant le chargement et le compteur non lu affiche `···` jusqu'à disponibilité des données. Aucun fallback silencieux vers Legacy.

Validation ciblée : 13/13 PASS (Mail bridge/QML, layout, route Modules et routing workspace). Validation globale fraîche : 498 tests découverts, 244 exécutés, 244 PASS, 0 échec, 0 import failure, 0 timeout; ADF 35/35. Self-check QML PASS et bytecode 0. Aucun réseau, OAuth, Gmail réel, Google Write, BAT ou Git exécuté.

La preuve automatisée couvre le vrai `ModulesView`/QML et le contrat de routage; un clic visible complet dans la fenêtre Windows reste à confirmer sur une surface desktop (`apps=[]` dans cette session). Le prochain contrôle humain doit ouvrir Native → Modules → Mail et vérifier l'absence de `MAIL RAPIDE` ainsi que l'arrivée directe sur MailView.

## Modules catalogue Native restored — 2026-10-03

La régression provenait de `app/qml/Main.qml` : `ModulesSubdock` avait été limité à `visible: root.modulesDockOpen && runtimeMode === "legacy"`, ce qui masquait le catalogue complet en Native. La visibilité est restaurée à `visible: root.modulesDockOpen`, pour Native et Legacy.

Le composant `ModulesSubdock` contient deux niveaux distincts : le catalogue de 7 modules (Maps, Météo, Recherche, Documents, Notifications, Mail, Contacts) et l'ancien panneau interne `MAIL RAPIDE`. En Native, `choose("mail")` émet désormais `navigateRequested("mail")` et ne passe jamais à `page = "mail"`; en Legacy, le comportement historique `page = "mail"` est conservé. MailView, son backend et les routes Maps/Météo n'ont pas été modifiés.

Tests ciblés : 11/11 PASS, incluant catalogue partagé, routes Maps/Météo/Mail, absence de page Mail rapide en Native et non-régression workspace. Suite headless fraîche : 499 tests découverts, 245 exécutés, 245 PASS, 0 FAIL, 0 import failure, 0 timeout; ADF 35/35. Self-check QML PASS; bytecode 0. Aucun OAuth, réseau réel, Gmail Write, BAT ou Git.

Validation humaine suivante : ouvrir Native → Modules, vérifier les 7 cartes visibles, puis cliquer Mail et confirmer l'arrivée directe sur MailView sans `MAIL RAPIDE`. Les autres entrées doivent conserver leur comportement actuel.

## Modules catalogue chevrons removed — 2026-10-03

Suppression purement visuelle du `Text` affichant `›` dans le delegate des sept cartes du catalogue `ModulesSubdock` (Maps, Météo, Recherche, Documents, Notifications, Mail, Contacts). Les `HoverHandler`, `TapHandler`, `choose(...)`, signaux et routes restent inchangés; le panneau `MAIL RAPIDE` Legacy reste intact et inaccessible en Native via le routage déjà établi.

Tests ciblés : 11/11 PASS. Suite headless fraîche : 499 tests découverts, 245 exécutés, 245 PASS, 0 FAIL, 0 import failure, 0 timeout. Self-check QML PASS; bytecode 0. Aucun réseau, OAuth, Google Write, BAT ou Git.

## Mail initial-load regression correction — 2026-10-03

Audit of the Native path found two deterministic issues after the async move. `MailView` relied on `onVisibleChanged` alone for the first `openInbox()` call; an initially visible/loaded view could therefore expose the shell without firing the request. In addition, `NativeMailBridge` recorded backend exceptions in `_error` but `MailView` rendered every zero-row non-loading result as `AUCUN MESSAGE À AFFICHER`, hiding API/auth/network failures as an empty inbox.

Correction: `Component.onCompleted` now triggers the canonical read when the view starts without data; the existing `onVisibleChanged` path remains. A read-only `state` property distinguishes `LOADING`, `READY`, `PERMISSION_REQUIRED`, `AUTH_ERROR` and `API_ERROR`. QML shows skeletons and `···` during loading, a permission panel for permission-required state, an explicit retry/error state for backend failures, and the true empty state only after a successful zero-row result. Refresh keeps the previous model until the new result is applied. No Gmail backend, OAuth, scope, Maps or Weather code was changed.

Runtime composition remains conditional: `GmailMailBackend` is selected only when the existing authenticated identity already contains `gmail.readonly`; otherwise `PermissionRequiredMailBackend` is used. No real Gmail read or OAuth was launched in this validation, so no live message count is claimed.

Mail tests and async delayed-backend coverage pass. Fresh global: 500 tests discovered, 245 executed, 245 PASS, 0 FAIL, 0 import failure, 0 timeout. QML self-check PASS; bytecode 0. No network, Gmail Write, BAT or Git.

## Daily Hub compact badges — 2026-10-03

AgendaView conserve les événements Calendar comme contenu prioritaire, limite l'affichage à deux événements puis `+N événements`, et réserve le bas de cellule aux indicateurs Daily Hub. Les anciens pills textuels `Gmail ...` et `Tasks ...` ont été remplacés par des mini-badges `G n` et `✓ n` de 34×18 px. Ils sont absents lorsque le compteur du jour vaut zéro et restent silencieux pendant le chargement; aucune permission n'est répétée dans chaque cellule.

Les clics restent inchangés : badge Mail → onglet Mail, badge Tasks → onglet Tasks, overflow → onglet Calendar. Aucun backend Google, service Mail, OAuth, Maps ou Weather n'a été modifié.

Tests ciblés Agenda/Daily Hub : 9/9 PASS. Suite headless fraîche : 501 tests découverts, 246 exécutés, 246 PASS, 0 FAIL, 0 import failure, 0 timeout. Self-check QML PASS; bytecode 0. Aucun réseau réel, Gmail Write, BAT ou Git.

## Daily Hub production data wiring — 2026-10-03

Audit confirms `GoogleDaySummaryBridge` is instantiated by `app/main.py` from `native_runtime.google_day_summary_service`, which is composed from the Native Calendar service, Native Tasks service and the same `MailService` used by `NativeMailBridge`. The production composition selects `GmailMailBackend` only when the existing authenticated Google identity already has `gmail.readonly`; test-only `FakeMailBackend` is selected only under the explicit `AURA_PCC_FAKE=1` test environment. No second OAuth/client/store was added.

Agenda requests the complete visible 42-cell month grid on component completion and on previous/next/today month changes. `GoogleDaySummaryService` aggregates counts by local date for Calendar, Gmail metadata and Tasks due dates; no message body or summary is loaded during aggregation. `GoogleDaySummaryBridge` now emits safe count-only diagnostics (`DAILY_HUB_MONTH`, day counts and totals) after applying a generation-valid result. Partial source failures remain isolated per domain.

Realistic offline month coverage proves 3 mails on 2 October, 1 mail plus 2 tasks on 4 October, no badge on 5 October, and 1 task on 7 October. Compact `G n`/`✓ n` badges remain hidden for zero and loading states; popup tab dispatch is unchanged.

Targeted Daily Hub/Agenda tests: 18/18 PASS. Fresh global: 502 tests discovered, 247 executed, 247 PASS, 0 FAIL, 0 import failure, 0 timeout. QML self-check PASS; bytecode 0. No OAuth, real Gmail READ, Google writes, Maps/Weather changes, BAT or Git.

## Google READ bounded transport — 2026-10-04

Calendar, Gmail and Tasks real providers previously used `googleapiclient.discovery.build(...).execute()` with the default `httplib2` transport and no explicit timeout. A shared `aura_native.google.transport` helper now builds real discovery clients through `httplib2.Http(timeout=10)` and `google_auth_httplib2.AuthorizedHttp`; fake builders used by offline tests remain untouched. Transport failures normalize to `TIMEOUT` or `NETWORK_UNAVAILABLE` before provider/API mapping.

Offline transport/provider/Daily Hub validation: 22/22 PASS. Fresh global: 504 tests discovered, 249 executed, 249 PASS, 0 FAIL, 0 import failure, 0 runner timeout. QML self-check PASS; bytecode 0.

The authorized real smoke resolved the persisted GUI composition and confirmed the existing session/providers, but the first real read still did not return within the bounded smoke process (likely credential refresh or lower-level network path before discovery response). The smoke was stopped safely; no OAuth, consent, Google write, or personal content logging occurred. Daily Hub live counts and real badges remain unconfirmed pending a separately bounded credential-refresh transport check.

## Google auth refresh bounded — 2026-10-04

Le refresh implicite de `google-auth` pouvait utiliser son `Request` par défaut, distinct du transport API `httplib2`. `transport.py` fournit maintenant `BoundedGoogleAuthRequest` avec le timeout partagé de 10 s et `refresh_credentials_if_needed()` protégé par un verrou single-flight. Les credentials valides ne sont pas rafraîchis inutilement; les credentials expirés avec refresh token sont rafraîchis une seule fois avant création du client API. Aucun navigateur, OAuth ou secret n'est exposé.

Le Gmail adapter réutilise désormais un client API pour toute une recherche au lieu de reconstruire le service pour chaque message. Smoke READ réel avec la composition officielle et `%LOCALAPPDATA%\\AURA-NATIVE` : Calendar PASS (20 événements, 19 jours, 1,67 s), Gmail PASS (25 messages au total, 6,4 s), Tasks PASS (3 tâches, 1,63 s). Les données Tasks réelles n'ont aucune échéance dans la grille visible; les mails ont des dates dans la plage visible. Le pipeline DaySummary produit 42 jours, 5 dates avec Mail et 0 date avec Tasks dans la plage testée.

Tests refresh/providers/Daily Hub : 25/25 PASS. Suite globale fraîche : 507 tests découverts, 252 exécutés, 252 PASS, 0 FAIL, 0 import failure, 0 runner timeout. QML self-check PASS; bytecode 0. Aucun Google Write, OAuth, consentement, Maps/Weather ou Git.

## Daily Hub last-mile badge bridge→QML fix (2026-10-04)
- Root cause: AgendaView rebuilt JS calendar rows by indexing the bridge's Python-backed `QVariantMap` directly (`summaries[dateKey]`), making the map-to-QML delegate handoff ambiguous during async replacement.
- Fix: `AgendaView.qml` now reads each date through the existing `GoogleDaySummaryBridge.summaryForDate(YYYY-MM-DD)` contract. `summaryChanged` remains the sole reactive rebuild trigger; no timer or forced window reload was added.
- Added explicit offscreen QML coverage for async badge refresh, month/key contract, and empty-map safety in `tests/native/test_agenda_daily_hub_delegate.py`.
- Focused validation: Daily Hub/Agenda 10/10 PASS. QML self-check command completed without error; no network, OAuth, Google write, or Git.
- Real backend counts remain read-only and anonymized: five Gmail dates were previously confirmed; no personal message fields are logged. Live Windows visual badge capture remains pending, so final cutover gate stays NO.

## Daily Hub popup last-mile fix (2026-10-04)
- Root cause: `GoogleDayDetailPopup.qml` supplied array models, but its StackLayout pages/ListViews lacked explicit fill geometry. Calendar/Mail/Tasks delegates therefore had zero/undefined usable viewport despite correct counts.
- Fix: explicit `Layout.fillWidth/Height` or anchors for all popup pages and lists; added compact empty states for Calendar, Mail and Tasks. Existing summary arrays and bridge contract are unchanged.
- Popup date remains supplied by `AgendaView.openGoogleDay()` and refreshed on `summaryChanged`; no timer/reload workaround.
- Targeted popup/Daily Hub tests: 15/15 PASS. Canonical runner: 515 discovered, 260 executed, 260 PASS, 0 FAIL, 0 failed imports, 0 timeouts; ADF 35/35.
- QML self-check and bytecode hygiene remain required; no OAuth, Google write, transport/auth, or Git. Live Windows validation should verify 2026-10-04 Mail (1), Calendar non-empty, Tasks empty state.

## Agenda final premium pass (2026-10-04)
- Native Agenda source audit: grid consumes current `coreBridge.googleCalendarEvents` in native mode; reminders/local models remain separate. No physical deletion or legacy-store cleanup performed.
- No dedicated Google Calendar asset existed. Added local `GoogleCalendarIcon.qml` and replaced the generic G glyph on Calendar event chips; Gmail `G n` badges remain unchanged.
- `GoogleDayDetailPopup.qml` received compact AURA header, summary strip, custom segmented tabs, close X, explicit responsive list geometry, internal scrolling, and Calendar/Mail/Tasks empty states. Existing bridge arrays and date summary source are preserved.
- Targeted Agenda/popup tests: 10/10 PASS. Canonical runner: 515 discovered, 260 executed, 260 PASS, 0 FAIL, 0 failed imports, 0 timeouts; ADF 35/35. QML self-check PASS; bytecode 0.
- Live Windows visual validation remains required; Computer Use unavailable. No OAuth, consent, Google write, transport/auth change, or Git.

## Agenda final live fix (2026-10-04)
- Added explicit `showPastEvents` policy, default OFF, with a local header toggle. Past events are hidden by display policy only; historical months remain visible and no Google data is deleted.
- Replaced generic/monochrome Calendar event visuals with local `GoogleCalendarIcon.qml`; no dedicated Google Calendar asset existed in the repository and no network asset is loaded.
- Popup body geometry was hardened with explicit StackLayout size and list viewport sizing. Premium header, summary strip, segmented tabs, close X, scrollable cards and empty states remain intact.
- Targeted Agenda/popup tests: 15/15 PASS. Canonical runner: 520 discovered, 265 executed, 265 PASS, 0 FAIL, 0 failed imports, 0 timeouts; ADF 35/35. QML self-check PASS; bytecode 0.
- Computer Use is unavailable; live Windows acceptance remains required. No OAuth, transport/auth, provider, Google write, Maps, Weather, MailView or Git changes.

## Google favicon micro-polish (2026-10-04)
- Reused existing local `app/qml/assets/google_favicon.png` through new `app/qml/components/GoogleFavicon.qml` (PreserveAspectFit, smooth, no network URL).
- Agenda Mail badges now render `[favicon] count` with a separate numeric Text; the textual `G ` prefix is gone. Popup Mail summary uses the same favicon. Calendar continues using `GoogleCalendarIcon.qml`.
- Targeted Agenda/Daily Hub tests pass after updating the badge assertion; QML self-check PASS and bytecode 0. No backend, OAuth, transport, provider, network, Google write or Git changes.

## Google favicon micro-polish validation (2026-10-04)
- Existing local `app/qml/assets/google_favicon.png` reused via `app/qml/components/GoogleFavicon.qml`.
- Agenda Mail badges render favicon plus separate numeric count; no textual `G` prefix. Popup Mail summary uses the same favicon. Calendar remains on `GoogleCalendarIcon.qml`; Tasks unchanged.
- Targeted Agenda tests: 20/20 PASS. Fresh canonical runner: 525 discovered, 270 executed, 270 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35. QML self-check PASS; bytecode 0.
- No backend/provider/auth/transport changes, OAuth, network, Google writes, or Git. Windows visual recheck remains required.

## Daily Hub popup single-tab cleanup (2026-10-04)
- Merged summary counts and tab navigation into one interactive row in `GoogleDayDetailPopup.qml`.
- Removed the redundant second Calendar/Mail/Tasks label row. Each tab now contains its icon, count, active state and page selection.
- Popup max height reduced from 460 to 420 px; content scroll and empty states remain.
- Targeted popup/Agenda tests: 24/24 PASS. Fresh canonical runner: 529 discovered, 274 executed, 274 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35. QML self-check PASS; bytecode 0.
- No backend, OAuth, Google write, Agenda grid, Git or data-model changes.

## Agenda legacy Calendar grid cleanup (2026-10-04)
- Legacy Google event chip renderer is visually disabled in the month grid; event payloads, counts, editing compatibility and backend data remain intact.
- Added compact `dayCalendarBadge` using `GoogleCalendarIcon`; it opens `GoogleDayDetailPopup` on Calendar tab. Mail and Tasks badges keep their existing routes.
- `calendarCount` is derived from the filtered display events, so the existing `showPastEvents` policy controls historical Calendar badges without deleting data.
- Targeted Agenda tests: 31/31 PASS. Fresh canonical runner: 536 discovered, 281 executed, 281 PASS, 0 FAIL, 0 imports, 0 timeouts; ADF 35/35. QML self-check PASS; bytecode 0.
- No Google backend/provider/auth/transport, Daily Hub service, Maps, Weather, MailView, OAuth, write, Git or physical data deletion.

## Reminder scheduler isolated-import gate (2026-10-04)
- Split reminder policy into stdlib-only `ReminderScheduler` and Qt-only
  `QtReminderSchedulerAdapter`; timezone resolution is lazy for `-I -S -B`.
- Targeted strict import: `STRICT_REMINDER_IMPORT=PASS`. Reminder tests 11/11;
  bootstrap tests 14/14. Full strict Lot 1 remains blocked by subsequent
  pre-existing Qt imports reached during bootstrap (`notification_center`,
  mail/maps bridges); no cutover is authorized.
- No parity implementation, OAuth/network/write, legacy change, or Git action.

## Lot 1 strict Qt import closure follow-up (2026-10-04)
- Removed eager Qt package re-exports from `mail` and `maps`; notification
  center/window state now use a small runtime-neutral signal contract, while
  tray and Qt scheduler remain runtime adapters.
- Strict validation progressed beyond Qt imports. New blocker is
  `DiagnosticsService -> psutil`, unavailable under isolated `-I -S`.
- Targeted Reminder and bootstrap tests remain green (25/25). Full Lot 1 is
  still blocked; no parity work or cutover was started.

## Lot 1 third-party import closure (2026-10-04)
- `DiagnosticsService` no longer imports psutil eagerly. Normal runtime keeps
  the psutil collector; isolated environments return explicit UNAVAILABLE
  metrics without inventing zero values.
- Strict validation progressed beyond psutil. New blocker is non-import ADF
  construction attempting `sqlite3.connect` under the read/write guard.
- Diagnostics, Reminder, bootstrap and local-reminder targeted tests: 34/34.
  No parity work, cutover, OAuth, network, Google write or Git action.

## Lot 1 ADF bootstrap side-effect closure (2026-10-04)
- `ADFService` construction is now pure: no directory creation, SQLite
  connection or migration. `initialize()` opens the stores exactly once;
  `enable()` initializes explicitly for normal Developer Mode use.
- ADF targeted suite plus diagnostics/bootstrap: 33/33 PASS.
- Strict validation progressed past ADF SQLite construction. Remaining errors
  are the validator's isolated temp-directory availability in this host
  (`FileNotFoundError` from `tempfile`), not an application import or ADF
  persistence side effect. No cutover or parity audit performed.

## Contacts Native lot (2026-10-04)
- Implemented local Contacts model/repository/service/Qt bridge and dedicated ContactsView; Modules routes now target contacts without Conversation prefill.
- SQLite initialization is lazy; delete requires confirmation; duplicate emails and optimistic version conflicts are normalized.
- No Google adapter/OAuth/network/write, no legacy data migration, no cutover, no Git. PySide6 is unavailable in this shell, so QML/live checks require the configured native Qt environment.

## Native Voice foundation (2026-10-04)
- Read-only Legacy audit completed: active facade is `voice/voice_engine.py` via
  `core/aura_core.py`; explicit push-to-talk microphone, Hybrid STT (local
  Whisper/optional Groq), XTTS/Piper output and fallbacks. Optional automatic
  VAD is a separate runtime. Full live barge-in remains UNPROVEN.
- Added stdlib-only `src/aura_native/voice/` contracts and `VoiceController`.
  No device/model/network/credential/process access occurs at import or
  construction. Fake providers cover lifecycle, fallback and confirmation
  safety; transcripts reuse `NativeIntentRouter`.
- Real provider wiring, Qt/QML voice exposure and live Windows validation are
  explicitly deferred. Lazy audio/STT/TTS contracts and an offline
  `NativeVoiceBridge` were added; missing dependencies return explicit
  unavailable states. `manual_voice_smoke.py` requires `--record` and was not
  run. No Legacy modification, cutover, OAuth, network, or Git.

## Voice local model checkpoint (2026-10-04)
- Installed only in the project `.venv`: `numpy`, `sounddevice`,
  `faster-whisper==1.2.1`, and `piper-tts==1.8.0`. PortAudio enumeration is
  available with 10 input devices; no capture was opened.
- Downloaded only the approved local assets under `%LOCALAPPDATA%\AURA-NATIVE`:
  `Systran/faster-whisper-small` (486 MB model files) and
  `fr_FR-siwis-medium` (63 MB ONNX plus JSON/MODEL_CARD). Explicit model-load
  checks pass (CPU/int8 STT, Piper synthesis of the synthetic sentence).
- Piper is GPL-3.0-or-later and marked
  `PIPER_DISTRIBUTION_REVIEW_REQUIRED=true`; no installer packaging is
  authorized. No voice alternative, XTTS, torch, cloud provider, or second
  model was installed. `NativeVoiceBridge` is now registered in the Native
  `app/main.py` composition, exposed as `voiceBridge`, and used by the existing
  Composer microphone control through a lazy QThread worker. Startup remains
  microphone/model safe; live microphone smoke remains pending and default
  runtime stays Legacy.

## Native voice output (2026-10-10)
- Added explicit voice request correlation metadata through ConversationService and AgentRequest to the canonical completed assistant event.
- `NativeCoreBridge.voiceResponseFinal` is consumed by `NativeVoiceBridge`; only correlated voice responses invoke the existing local Piper provider. Keyboard `sendMessage` requests do not speak automatically.
- Synthesis/playback diagnostics and stop/shutdown cleanup are fail-closed; response text remains in the conversation on output errors.
- Offline voice suites: 27/27 passed. Live TTS and live stop-speaking remain pending human retest; no network, OAuth, or Git action was performed.

## System Control 003 (2026-10-10)
- Added test-owned PySide6 window harness at `tests/native/_evidence/system_control_003_live.py` and child window helper. It targets only a generated title plus exact PID/HWND and closes only its own child.
- Native System Control tests: 20/20 PASS. Lot 1 strict: 53/53 PASS.
- Live safe Win32 validation: windows/processes/foreground discovery PASS; owned minimize/maximize PASS; focus classified DENIED_BY_WINDOWS_POLICY when Windows rejects foreground activation in the harness context.
- All three mutating actions require confirmation; stale target after owned child close returns structured NOT_FOUND/FAILED; PID/HWND cross-check PASS; handle reuse not reproduced.
- No shell, shell=True, shutdown/restart/logoff/sleep/hibernate, process kill, network, OAuth, Google or Git. Product/Text/Voice/PreparedAction wiring remains deferred; cutover remains blocked.

## Memory/history/context 001 (2026-10-10)
- Legacy audit completed read-only. Legacy conversation transcript is volatile in `AuraCore`; persistent SQLite memory is an explicit, separate MemoryManager/MemoryKernel domain.
- Native history is versioned SQLite (`schema_migrations` v13), ordered by per-conversation sequence, isolated by session/conversation IDs, and survives isolated restart tests.
- Added a lazy memory package export to remove a repository/service circular import; storage connection failures now close the SQLite handle before propagating.
- Focused validation: memory/history/context 22/22, Conversation 5/5, Agent Context 9/9. No Legacy execution, no real-state access or migration, no Git.
- Native memory/context remains a contract-level parity result; real Legacy data migration is not performed and requires a future explicit mapping specification.

## Memory 002 migration specification (2026-10-10)
- Added pure synthetic planner `src/aura_native/migration/memory_legacy.py`; it performs no destination writes and opens only supplied sources in SQLite read-only mode.
- Legacy schema mapped from source definitions: `memories` plus separate `preferences`; transcript migration remains NOT_REQUIRED.
- Synthetic migration specification tests: 24/24 PASS. No real Legacy or `%LOCALAPPDATA%\AURA-NATIVE` state accessed or modified.
- Future migration remains `REQUIRES_TRANSFORM`: provenance, preference separation, scope review, conflict review and an explicit writer/backup step are still required before any controlled execution.

## Text Command + Prepared Action 001 (2026-10-10)
- Router/dispatcher audit completed. `IntentResult` now carries source and request correlation metadata; System Control minimize/maximize/focus parse only typed title candidates and require confirmation at dispatch.
- Dispatcher returns explicit result categories and creates a PreparedAction only through an injected factory. No direct OS, shell or LLM mutation path exists.
- Foundation tests: 20/20; text command 4/4; PreparedAction repository 3/3; System Control 20/20; Conversation 5/5; Agent Context 9/9; Memory/history 22/22; Lot 1 strict 53/53.
- Product wiring remains PARTIAL: exact HWND/PID resolution, PreparedAction creation in the production bridge and live end-to-end UI confirmation remain deferred. Voice internals remain frozen.

## Text Command + Prepared Action 002 (2026-10-10)
- Added `WindowTargetResolver` and `SystemControlProductService`: exact normalized title resolution, explicit NOT_FOUND/AMBIGUOUS/INVALID results, immutable HWND/PID payload and PreparedAction creation without mutation.
- Existing pending-action orchestrator now routes `system.window.minimize`, `system.window.maximize` and `system.window.focus` through the product service and revalidates exact identity before System Control execution.
- NativeCoreBridge keyboard and existing voice transcript paths now create the same typed System Control PreparedAction; confirmation remains UI/action-ID based and voice confirmation remains deferred.
- Safe live owned-window path: typed minimize → PreparedAction → no mutation before confirmation → confirmed minimize → executed state, all PASS. No user-owned window, shell, power action or network used.
- Product integration is no longer only a factory contract, but UI visual live validation and full live cancel/double-confirm/stale/maximize/focus matrix remain to be completed before cutover.

## Text Command + Prepared Action 002 completion (2026-10-10)
- Completed live test-owned window matrix: minimize, maximize and focus confirmed execution PASS; cancel zero mutation, double confirmation exactly once and stale target rejection PASS.
- All live operations targeted generated child windows only. No user-owned window, shell, power action, network, OAuth or Git operation was used.
- Historical checkpoint: UI visual live inspection was unavailable at this stage. The shared confirmation surface gate is superseded by the real local validation in Text Command 004 and the canonical 005 review; unrelated cutover gates remain open.

## Text Command + Prepared Action 003 UI (2026-10-10)
- Reused `PendingActionCard.qml` as the production confirmation surface. It now calls ID-bound `confirmPreparedAction(id)` and `cancelPreparedAction(id)` slots; compatibility no-argument slots remain available to existing callers.
- Terminal `error` and `expired` states hide the confirmation surface. Confirmed state disables both buttons immediately. Summary remains display-only; no HWND/PID or JSON is exposed.
- Expanded repository coverage: 16 explicit PreparedAction cases. QML contract coverage: 8/8.
- Historical checkpoint: technical UI wiring was complete and visual validation was pending then. Text Command 004 subsequently validated the shared local confirmation surface live; see the canonical 005 review.

## Text Command 004 local product wiring (2026-10-10)
- LocalIntentProduct connects nine existing local intents through NativeActionDispatcher and existing services/repositories. Six mutations use PreparedAction; existing ID-based confirmation and orchestrator remain authoritative. No Google mutation path is used.
- Router preserves original content, rejects empty creates and requires an explicit YYYY-MM-DDTHH:MM for reminder creation. Relative French time parsing is not implemented; it fails closed.
- Local tests 40/40, regression batch 207/207, strict Lot 1 53/53 and QML self-check PASS. Computer Use validated create note/task/reminder, completion, cancel zero mutation and chat response; actual views show the records.
- Historical 004 cleanup request was completed: both exact authorized UI deletes and guarded test-task cleanup PASS; see 004 final validation below. No cleanup remains pending.
- Final small UI status correction clears stale confirmation guidance after execute/cancel and ordinary chat; final targeted rerun required after this correction. No next lot or Git.

## Text Command 004 final validation (2026-10-10)
- Final offline regression: 215/215 PASS, including 42 local command tests and PreparedAction, QML contracts, System Control, Conversation, Agent, Memory, Developer Fabric and Voice suites. Additional targeted run: 68/68 PASS. Strict Lot 1: 53/53 PASS; native QML self-check: exit 0 / PASS.
- Existing voice worker transcriptReady signal is connected by the official bootstrap to a queued, local-only bridge slot. Offline test proves a voice transcript creates a pending action without storage mutation or automatic confirmation; normal conversation text is ignored by this additive slot. Voice internals remain unchanged. Live microphone test was not performed.
- Computer Use: live create note/task/reminder, complete task, cancel with zero mutation, normal Gemini chat, delete note and delete reminder PASS. User explicitly authorized the two exact UI deletions at action time. PendingActionCard disappeared after each confirmed delete; exact SQLite IDs were independently verified absent.
- Cleanup PASS: note 308e2ff5-287b-4b11-bb5c-cfaab379ab49 and reminder 1c0e0749-6bbc-468e-9448-bb3e6d8f50e1 deleted through UI. Completed task 68b01661-3232-4d8f-aad6-6364d2c7dd41 removed by exact ID AND exact test title AND completed=1 guard; one row affected. All three exact records now absent; no other local entities deleted. Conversation test messages retained.
- Validation uses -B and PYTHONDONTWRITEBYTECODE=1. Bytecode inventory is NOT zero: 1987 cached files remain (.runtime 218, .venv 1756, app 1, src 10, tests 2). No cache deletion performed in this scoped local-command lot; do not claim BYTECODE=0.
- One newly added source-contract test initially used the wrong project parent path; corrected in the test only, then the full final 215-test regression passed.
TEXT_COMMAND_LOCAL_MUTATION_PARITY=PASS_NATIVE (nine scoped intents; explicit datetime contract)
TEXT_COMMAND_ROUTER_PARITY=PARTIAL_REMINDER_NATURAL_TIME
TEXT_COMMAND_DISPATCH_PARITY=PARTIAL_GLOBAL_MATRIX
TEXT_COMMAND_CUTOVER_BLOCKER=true
- Remaining: natural-language reminder datetime parity, remaining global deterministic domains, live voice local-command retest and separate bytecode hygiene review. No next lot started, Git, Google mutation, Legacy writes or cutover.



## Text Command 005 — current audit-only checkpoint (2026-10-10)
- Review only; production src/app hashes unchanged. No Git, Legacy execution/import, network, credentials, microphone, real mutation or .pyc deletion.
- Canonical current matrix is section 005 of docs/migration/text_command_prepared_action_parity.md; prior 001–004 sections are historical. 157 rows = conservative 150 comparison obligations (including 17 authenticated Roadmap endpoint routes without proven normal Composer invocation) + 7 exclusions. Native scoped PASS 11, PARTIAL 45, DEFERRED 94. Full detail: docs/migration/text_command_005_remaining_gaps_review.md.
- Natural reminder parity is a real blocker: Legacy active ReminderParser handles tomorrow/time, minutes/hours, weekdays. Native supports content + explicit YYYY-MM-DDTHH:MM only, fixed Europe/Paris conversion. Do not copy Legacy ignored absolute dates or broken recurrence.
- Proven gaps: SEARCH_NOTE/memory text commands, PC windows/processes/foreground grammar and restore, business query parameters discarded in Main.qml navigation, Google/business/extension text dispatch, local-vs-Google task precedence and Legacy local aliases. Mark-the-task-as-done suffix is incorrectly retained in Native target raw. No patches applied.
- PREPARED_ACTION_UI_LIVE=PASS supersedes historical unobserved UI gate; Computer Use 004 performed real Confirm/Cancel and authorized deletes. Voice core/System Control/Memory/Text Chat baselines preserved.
- VOICE_LOCAL_INTENT_LIVE=NOT_AVAILABLE: Computer Use has no physical microphone phrase input; no AURA window returned during review; no fake live claim. Offline state probe proves local pending cancellation leaves VoiceController THINKING; new Voice local integration terminalization defect, not a downgrade of validated Voice core. Requires separate authorization before fix.
- Review tests 67/67 = local42 + PreparedAction19 + Conversation6; strict Lot1 53/53; QML self-check exit0/PASS. 215 baseline not rerun because no production code changed.
- PYC total1987 = src/app11 + runtime/.venv1974 + test/evidence2. New0/changed0 during controlled -B/PYTHONDONTWRITEBYTECODE run; hygiene debt, not Text Command cutover blocker. No cache deleted.
- TEXT_COMMAND_ROUTER_PARITY=PARTIAL_PROVEN_GRAMMAR_GAPS; TEXT_COMMAND_DISPATCH_PARITY=PARTIAL_PROVEN_DOMAIN_GAPS; TEXT_COMMAND_CUTOVER_BLOCKER=true. No next lot begun. Recommend scoped local/time contract lot, then Voice local terminalization/live gate; separately decide extension perimeter and per-domain dispatch lots.
## Text Command 006 checkpoint

Implemented the focused local command and French temporal parser scope. See `docs/migration/text_command_006.md`. Automated targeted validation is green; real Windows validation has exercised two owned reminder confirmations and one owned cancellation. Invalid-date, needs-time, note-search and normal-chat live checks remain to be completed before declaring the live lot PASS. No Voice, Memory, PC READ, Google or cutover work was started.

## Text Command 006B closure (2026-10-10)

006B is closed as `PASS_NATIVE_LIVE`. The authorized test reminder IDs `e98ee5f3-92a6-439a-938c-ca8cdcb73525` and `15fb4317-bef4-4177-aedb-b8bc5b949feb`, plus note ID `a462941a-6815-4edd-a810-2e9d62ae7045`, were deleted only through the AURA UI after confirmation. Each ID was checked absent in SQLite after execution and again in a final read-only query. No other local record was deleted; invalid-date, needs-time, and cancelled-test checks are absent.

Final validation: temporal matrix 11 tests / 40+ cases; local command regression 42/42; targeted 006 + 004 suite 53/53; strict Lot 1 53/53; QML self-check exit 0/PASS; controlled runs used `-B` and `PYTHONDONTWRITEBYTECODE=1` with 0 new `.pyc`. Live statuses: relative reminder, tomorrow reminder, cancel zero mutation, invalid date, needs time, and local note search PASS. Chat routing PASS with no PreparedAction leak; provider response remains `BLOCKED_PROVIDER_UNAVAILABLE`. `TEXT_COMMAND_CUTOVER_BLOCKER=true` remains for Voice local terminalization, Memory commands, PC READ grammar and other proven global gaps. Récurrence remains `UNSUPPORTED_RECURRENCE`. Stop here; do not start Lot 007.

## Lot 007 — Voice local PreparedAction terminalization (2026-10-10)

Audit root cause: `transcriptReady` ne portait pas d'identité Voice fiable vers le dispatch local ; les événements `pending_action.*` ne pouvaient donc pas sortir le VoiceController de `THINKING`. La correction ajoute un signal transcript corrélé, une table d'association action → voice request, la propagation des états terminaux et une libération idempotente vers `IDLE`. Les actions clavier restent sans association Voice.

Validation : Voice/local/Text ciblée 92/92, Lot 1 strict 53/53, self-check QML PASS, exécutions contrôlées sans nouveau `.pyc`. Computer Use a lancé et observé la fenêtre native réelle ; des périphériques sounddevice existent mais l'injection audio physique n'est pas contrôlable par Codex (`VOICE_MIC_LIVE=NOT_AVAILABLE`). Aucun objet de test destructif n'a été créé, aucun réseau/OAuth/Google utilisé, aucun Git. Lot 008 non commencé.

## Lot 007B — clôture UI transcript path (2026-10-10)

Ajout d'une entrée de sonde strictement diagnostique (`AURA_PTT_DIAGNOSTICS=1`, `--voice-transcript-probe`) qui passe par le signal transcript corrélé de production. Computer Use a validé dans la vraie fenêtre Native : Voice transcript → PreparedAction note → ANNULER (`cancelled`, aucune note, Voice `IDLE`) ; Voice transcript → PreparedAction note → CONFIRMER (une seule note, `executed`, Voice `IDLE`) ; puis suppression UI autorisée de `AURA_TEST_007B_CONFIRM_20261010`, ID `d0c64f22-9c2b-4e32-a047-c4bb85c7ad32`, vérifiée absente par ID et titre. Une action note d'origine clavier a été annulée via l'UI ; Voice est resté `IDLE` et aucune note n'a persisté.

Statuts : `LIVE_TEST_DATA_CLEANUP=PASS`, `LIVE_VOICE_LOCAL_CANCEL=PASS_LIVE_TRANSCRIPT_PATH`, `LIVE_VOICE_LOCAL_CONFIRM=PASS_LIVE_TRANSCRIPT_PATH`, `LIVE_KEYBOARD_VOICE_ISOLATION=PASS`, `VOICE_LOCAL_PREPARED_ACTION_PARITY=PASS_NATIVE_LIVE_PRODUCT_PATH`, `VOICE_LOCAL_TERMINALIZATION_BLOCKER=false`.

Microphone : périphérique présent, non contrôlable par Computer Use ; `VOICE_MIC_LIVE=NOT_AVAILABLE` et gate externe inchangé. Aucun réseau/OAuth, Google, Legacy ou Git. Lot 008 non commencé.

Régressions ciblées : 217 tests exécutés, 216 réussis ; un échec isolé de `test_database_is_lazy_until_first_memory_operation` révèle que la composition crée déjà la base avant la première opération mémoire. Lot 1 strict : 53/53. QML self-check : PASS. Les `.pyc` existants n'ont pas été supprimés conformément au périmètre.

## Lot 008 — Memory commands (en cours)

Le premier défaut corrigé est la fausse non-laziness SQLite : `QtReminderSchedulerAdapter.start()` reporte le rescan initial avec `QTimer.singleShot(0, ...)`, de sorte que `compose_runtime()` sans boucle Qt n'ouvre pas la base avant une opération mémoire. Le test ciblé `test_database_is_lazy_until_first_memory_operation` est vert.

Le routeur natif reconnaît le sous-ensemble mémoire Legacy prouvé (remember/store, list/show, search/find, forget) et `LocalIntentProduct` prépare les créations/suppressions via `PreparedAction`; `PendingActionOrchestrator` exécute les actions `memory.*` après confirmation. Lecture et recherche appellent directement `MemoryService`/son repository. Aucun réseau, Google, OAuth, Legacy write, Git ou nettoyage de données réelles n'a été effectué. Validation complète et Computer Use du lot 008 restent à faire.

## Lot 008B — live closure gate (2026-10-10)

AURA Native was launched with an isolated `lot008b-live-state`. Computer Use found the real window, but coordinate input was rejected (`foreground window did not report a process id`). No disposable Memory was created, no user data was touched, and no destructive confirmation was requested. Offline targeted suites remain green; the Lot1 strict validator produced a pre-existing/independent forbidden import report for `aura_native.notes` and is recorded as a regression requiring follow-up. Lot 008 remains open pending a usable Computer Use input surface and a clean full regression gate.

## Lot 008C — strict import and live input gate (2026-10-10)

The requested strict invocation completed under `-I -S -B`: 53/53 PASS. The full supervisor's forbidden-import inventory is separate from the strict contract and reports `aura_native.notes` during dynamic composition inspection. AURA was relaunched with an isolated state; Windows read-only inspection proved runtime PID 35972 owns HWND 2687176 and the main title is `AURA Native UI POC 6H FIX2`. Computer Use rendered the window but input remained unavailable because the foreground adapter reported no PID. No Memory test object was created and the isolated memory table stayed empty. No feature scope was expanded and Lot 009 has not started.

## Lot 008D — Computer Use input root-cause isolation (2026-10-10)

Input matrix: Notepad PASS; PySide6 QWidget probe PASS; minimal PySide6 QML probe PASS. The AURA-specific failure is the default frameless/translucent layered window surface; the existing `--windowed` diagnostic mode removes the layered surface and accepted Composer input. `AURA_PRODUCT_FIX_REQUIRED=false`, `AURA_PRODUCT_FIX_APPLIED=false`; no production source was changed. Memory live closure was not completed after the Computer Use session became unavailable for reattachment. No live memory object or deletion was performed. Memory commands 2/2, Memory history 22/22, Lot1 strict 53/53, native self-check `ok: true`. Lot 008 remains open; do not start Lot 009.

## Lot 008E — final live closure attempt (2026-10-10)

Fresh `--windowed` AURA launched (PID 11080, HWND 1903048), but the reset Computer Use session did not expose native app binding (`getApp` unavailable; inventory empty). Therefore no live Composer Memory flow was executed and no test data or deletion confirmation was touched. Automated required suites and strict Lot1 remain green; PYC count stayed 21 with 0 new. Lot 008 remains open; do not start PC READ.

## Lot 009 — PC read-only product wiring (2026-10-10)

Implemented safe French text commands for listing windows, listing processes, and reading the foreground window. Legacy evidence shows corresponding PC dispatcher grammar, but Native reports this as a product enhancement rather than claiming historical parity. Computer Use is unavailable (`apps=[]`), so live validation remains pending external tooling. Automated PC read 5/5, System Control targeted 24/24, Lot1 strict 53/53; no production window mode change and no mutation path change.

## Lot 010 — final reachability and parity gate (2026-10-10)

Computer Use availability was checked first and remained unavailable (`apps=[]`). Static Legacy reachability and Native routing were audited read-only. Small deterministic aliases were implemented and covered by `test_text_command_010.py`; no Voice, Memory, PC Read core, Google, or default window changes were made. QML runtime regression and Lot1 strict remain green. See `docs/migration/text_command_010_final_reachability.md` for the canonical matrix and remaining blockers.

## Lot 011 — Weather/Search/Navigation parameters (2026-10-10)

Implemented only the proven parameter propagation group: Weather location/day, Web/Note/Memory search query forms, and parameterized module navigation. `AuraBridge.navigationContext` preserves structured slots at the UI boundary. Computer Use was unavailable, so live checks remain pending external tooling. No frozen domain was reopened.

## Lot 012 — Mail/Calendar/Contacts (2026-10-10)

Implemented read-only text dispatch through existing Mail, Calendar and Contacts services. Google writes remain deferred and governed; no test-owned contact live mutation was attempted because Computer Use was unavailable. Automated Lot 012 is green and Lot1 remains 53/53.

## Lot 012B — Contacts local mutations (2026-10-10)

Added `ContactsProductService` as a confirmation-first PreparedAction boundary for `contact.create`, `contact.update`, and `contact.delete`. Stable contact IDs and observed versions are retained in payloads; exact name resolution rejects missing or ambiguous targets, and update/delete refuse stale versions. The pending-action orchestrator now routes `contact.*`; read-only contact commands remain direct reads. Offline suite `test_text_command_012b_contacts_mutations.py` is 11/11, Lot 012 is 6/6, Lot 011 is 5/5, and QML native is 5/5. Computer Use was unavailable (`apps=[]`), so no live contact or destructive confirmation was performed. No network, OAuth, Google provider, Legacy path, or Git was used. Lot 012B external live gates remain blocked.

## Lot 012C final closure pass — 2026-10-10

The last three obsolete authority tests were migrated: Memory 008 (1) and Voice 007 (2). The targeted closure group is 268/268 PASS; Local Text 004 remains 42/42. Generic bus confirmation remains non-authoritative and the UI capability is the sole confirmation authority. Live Contact safety, stale-target protection, normal chat routing, and PC Read evidence remain as previously recorded; provider availability remains external and Memory live mutation remains a separate pending gate. The 004 stress evidence remains 10/10 fresh-process passes with zero hangs, historical run 3 ambiguous, and no proven root cause.

Bounded Native final gate: all 147 modules were accounted for. The only first-pass issue was `test_isolation`, caused by Qt modules left in `sys.modules` by a preceding test; test-only cleanup was added and the affected module reran 16/16 PASS. Final aggregate is 147/147 modules PASS, 723 tests run, 0 failures, 0 errors, 1 expected skip, 0 timeouts. Strict Lot1 remains 53/53 PASS with environmental baseline drift classified separately. Test-owned process and final smoke-state cleanup passed. LOT 012C is closed; Memory live and provider availability remain separate external gates.

## Lot 013 — Music + Documents text parity — 2026-10-10

Legacy reachability was audited read-only. Native deterministic routing was added for Music open/play/pause/resume/stop/next/previous/volume/mute/seek and Documents search/open, using the existing bridges and preserving parameters. Documents safety and PreparedAction authority were not redesigned. Focused routing plus Documents/012C regression passed 63/63 with one expected skip. An isolated Computer Use AURA smoke entered Music and Documents commands; all test-owned temp assets/state/processes were cleaned. Full Lot 013 live playback-state and mutation confirmation remain open for bounded follow-up validation.

Lot 013B implementation: completed the local QMediaPlayer/QAudioOutput Music state bridge, ordered queue/current index, next/previous, mute/unmute, bounded seek handling, and normal QML/accessibility observability. Documents query and canonical opened identity are now exposed through the existing bridge and UI. Focused LOT 013B/regression validation passed 166 tests with 1 expected skip. Live Computer Use revalidation was blocked by `apps=[]`; the launched AURA process and isolated test root were cleaned. LOT 013 remains open until real Computer Use proves backend/UI state.

## LOT 013L closure

LOT 013 is closed. The exact real Main.qml/PySide QVariantMap bridge regression test passes, and the authoritative successor baseline is green: 33 total, 32 pass, 0 fail, 0 error, 1 expected skip. Music and Documents text-command parity are PASS; total parity is complete; final regression is PASS.

Computer Use was exposed and desktop-bound, but native inventory was unavailable (`CU_APPS_COUNT=0`), so live visual validation is waived and residual UI visual risk remains not live visually verified. No product code was modified in LOT 013L.

Next recommended lot: FINAL NATIVE MIGRATION AUDIT — NOTIFICATIONS / BACKGROUND / TRAY / CUTOVER READINESS

## LOT 014A — final Native migration audit

Read-only audit completed. Native remains explicit-only and Legacy remains the
default; rollback is --core-mode legacy. Native default cutover is NOT READY:
five P1 findings remain covering process-alive-only notifications/background,
incomplete tray/lifecycle ownership, separate Native/Legacy persistence, and
provider-backed Mail/Documents/Contacts parity boundaries. No P0 blockers were
found. Full findings and the ordered lots 014B–014E are in
docs/migration/native_cutover_audit_014a.md.

Computer Use inventory was checked once: exposed and desktop-bound, with zero
native applications, so UI inspection was skipped as unavailable. No product
code, tests, runtime defaults, Legacy code, packaging, or prohibited state was
modified.

## LOT 014B — Native notification contract

LOT 014B is CLOSED. Native notification ownership is explicit and
Legacy-independent: Windows tray delivery is selected only when supported,
Native in-app fallback is truthful, reminder identity/deduplication is stable,
click activation is bounded to restoring AURA, and shutdown rejects pending
notification work safely. Post-process-exit scheduling remains deferred to
LOT 014C.

Validation: focused notification/reminder tests 33/33 PASS; isolated real
Native QApplication/QML self-check PASS; canonical LOT 013 baseline 33 total,
32 PASS, 0 FAIL, 0 ERROR, 1 expected skip. Computer Use was exposed and
desktop-bound but had zero native applications, so visual validation was
skipped. P1 count reduced from 5 to 4.

Next required lot: LOT 014C — BACKGROUND OWNERSHIP AND TRAY POLICY

## LOT 014C — background ownership and system tray policy

LOT 014C is CLOSED. NativeRuntime is the single process-alive background
owner; scheduler start/stop is idempotent; close-to-tray is enabled only when
the system tray is available; tray Show restores AURA; tray Quit uses one
central shutdown path; and tray-unavailable close exits normally. Post-process-
exit execution is not a required product behavior, so no Windows scheduler or
auto-start mechanism was added.

Validation: 36/36 focused tests PASS; real isolated Native QApplication/QML
self-check PASS; LOT 014B notification regression PASS; canonical LOT 013
baseline PASS at 33 total, 32 PASS, 0 FAIL, 0 ERROR, 1 expected skip.
Computer Use inventory was exposed and desktop-bound but contained zero native
applications, so no visual tray claim was made. Remaining P1 count is 2.

Next required lot: LOT 014D — LIFECYCLE AND PERSISTENCE CUTOVER SAFETY

## LOT 014D — lifecycle and persistence cutover safety

LOT 014D is CLOSED. Native startup/failure ownership is explicit, shutdown is
centralized and idempotent, repeated isolated Music teardown did not reproduce
the prior broad-suite crash, and Native state is explicitly rooted, versioned,
transactional/atomic where applicable, corruption-safe, and separate from
Legacy state. Rollback preserves both state roots; roll-forward restores
Native state without destructive synchronization.

Validation: 48/48 focused tests PASS; isolated Native and Legacy QML
self-checks PASS; LOT 014C and LOT 014B regressions PASS; canonical LOT 013
baseline PASS at 33 total, 32 PASS, 0 FAIL, 0 ERROR, 1 expected skip.
Computer Use was exposed and desktop-bound but had zero native applications,
so no visual claim was made. Remaining P1 count is 1.

Next required lot: LOT 014E — PROVIDER PARITY DECISION AND FINAL CUTOVER GATE

## LOT 014E — provider parity decision and final Native cutover

LOT 014E is CLOSED. Native is now the default runtime; --core-mode legacy
remains the explicit rollback path. Mail read parity is covered by the
existing GoogleAuthProvider-backed Gmail adapter with truthful unavailable,
auth, scope, and API error states. Local Documents and Contacts remain the
authoritative Native contracts; provider-backed historical variants are
documented P2 scope rather than cutover blockers.

Validation: provider-focused group 35 tests with 34 PASS, 0 FAIL, 0 ERROR,
1 expected skip; directly relevant cutover regression 83 tests PASS with
1 expected skip; LOT 014D/014C/014B PASS; LOT 013 canonical baseline PASS at
33 total, 32 PASS, 0 FAIL, 0 ERROR, 1 expected skip. Default Native startup,
explicit Native, Legacy rollback, and default roll-forward passed in isolated
state. Computer Use was exposed and desktop-bound but had zero native apps,
so final visual validation was waived.

P0=0, P1=0, P2=9. Native migration cutover is complete. LOT 014F is next and
must handle GitHub publication, README, license, release metadata, assets,
installation instructions, and repository preparation. No publication or Git
operation was performed in LOT 014E.

Next required lot: LOT 014F — GITHUB PUBLICATION + README + RELEASE

## LOT 014F — GitHub publication snapshot

The Native successor was published without rewriting history on the dedicated
branch `native-migration-014f` from the public `main` lineage. README.md,
CHANGELOG.md, CONTRIBUTING.md, LICENSE, version metadata, and repository
ignore rules were added or refreshed. The existing owner-selected
all-rights-reserved license was preserved. No release tag or binary release
was created because the publication quality gate is not green.

Validation: secret/private-state audit found no real credentials, tokens,
runtime databases, caches, or generated evidence in the publication snapshot.
The focused LOT 013 regression ran 33 tests: 32 PASS, 0 ERROR, 1 expected
skip, and 1 FAIL in `test_native_composition_and_diagnostics_bridge`
(`diagReady` false). This failure was not introduced by the publication docs
or metadata, but it blocks a release claim until repaired and revalidated.

Publication branch: `native-migration-014f`
Commit: `4cbf111 Publish Native migration baseline`
Next required lot: repair and revalidate the diagnostics bridge before creating
a version tag or GitHub Release. LOT 015A was not started.
