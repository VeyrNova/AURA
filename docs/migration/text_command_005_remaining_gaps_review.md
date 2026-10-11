# Text Command 005 — revue ciblée des écarts

Date : 10 octobre 2026, contexte Europe/Paris. Audit/classification uniquement. Aucune modification de code production, aucun Legacy exécuté/importé, aucun réseau, credential, OAuth, Git, micro ou suppression de .pyc. Tests isolés et self-check headless écrivent seulement leurs états temporaires/de preuve.

## Rappels : contrat réellement supporté

Native reconnaît CREATE_REMINDER, mais seule la forme **rappelle-moi <contenu non vide> [le] YYYY-MM-DDTHH:MM** fournit un payload temporel valide. Exemple éprouvé : `rappelle-moi de tester 2026-10-15T14:00`. Date impossible refusée ; `Z`, offset `+02:00`, secondes, texte naturel et absence de contenu ne font pas partie de ce contrat. Identifier une intention CREATE_REMINDER n'est pas supporter son expression temporelle : `needs_explicit_datetime` refuse la création.

Les quinze formes demandées sont actuellement **UNSUPPORTED** en Native. L'ambiguïté de « demain », « ce soir », « le mois prochain », « à 15h » ou de la récurrence est une question de politique future ; elle ne transforme pas leur refus actuel en support partiel.

Preuves : router.py parse(), LocalIntentProduct.dispatch(), LocalRemindersService._trigger(), helper local_trigger_to_utc et scheduler. Pour vérifier le Legacy sans l'exécuter en place, seul l'AST de la classe pure ReminderParser et de sa constante weekdays a été évalué dans le processus de preuve, avec imports stdlib fournis. Aucun module Legacy importé, aucune construction d'AuraCore/manager/provider. Horloge de sonde fixée au **2026-10-10 14:00**, samedi, valeurs Legacy naïves.

Les phrases demandées ne contiennent souvent aucun contenu de rappel. Le rapport JSON conserve le résultat brut et une seconde sonde explicitement synthétique `rappelle-moi de tester ...` pour distinguer parsing temporel et contenu vide ; aucune sonde ne crée de rappel.

| Forme française après « rappelle-moi » | Native | Legacy : date avec contenu de test | Qualité Legacy / limite |
|---|---|---|---|
| le 15 octobre à 14h | UNSUPPORTED | 2026-10-11T14:00:00 | INCORRECT : date absolue ignorée, ne retient que 14h ; choisit le 11/10. |
| demain à 15h | UNSUPPORTED | 2026-10-11T15:00:00 | SUPPORTED_EXACT avec contenu. |
| demain | UNSUPPORTED | 2026-10-11T09:00:00 | SUPPORTED_PARTIAL : heure implicite 09:00 selon politique Legacy. |
| ce soir | UNSUPPORTED | aucune | UNSUPPORTED. |
| cet après-midi | UNSUPPORTED | aucune | UNSUPPORTED. |
| lundi à 9h | UNSUPPORTED | 2026-10-12T09:00:00 | SUPPORTED_EXACT : prochain lundi, 12/10. |
| lundi prochain à 9h | UNSUPPORTED | 2026-10-12T09:00:00 | SUPPORTED_PARTIAL : weekday reconnu, « prochain à 9h » reste dans le contenu ; heure par défaut 09:00, résultat correct par coïncidence. |
| dans 20 minutes | UNSUPPORTED | 2026-10-10T14:20:00 | SUPPORTED_EXACT : offset minutes. |
| dans 2 heures | UNSUPPORTED | 2026-10-10T16:00:00 | SUPPORTED_EXACT : offset heures. |
| dans 3 jours | UNSUPPORTED | aucune | UNSUPPORTED. |
| le mois prochain | UNSUPPORTED | aucune | UNSUPPORTED. |
| tous les lundis à 8h | UNSUPPORTED | 2026-10-11T08:00:00 | INCORRECT : une occurrence dimanche 11/10 à 08:00 ; aucune récurrence. |
| chaque matin | UNSUPPORTED | aucune | UNSUPPORTED. |
| à 15h | UNSUPPORTED | 2026-10-10T15:00:00 | SUPPORTED_EXACT pour prochaine 15:00 avec contenu ; prochain jour si heure passée. |
| le 10/11 à 14h30 | UNSUPPORTED | 2026-10-10T14:30:00 | INCORRECT : date 10/11 ignorée ; ne retient que heure 14:30 du 10/10. |

REMINDER_ABSOLUTE_DATETIME=SUPPORTED_EXACT_ISO_LOCAL_ONLY
REMINDER_RELATIVE_TIME=UNSUPPORTED
REMINDER_DAYPART=UNSUPPORTED
REMINDER_RECURRENCE=UNSUPPORTED
REMINDER_TIMEZONE_HANDLING=PASS_FIXED_EUROPE_PARIS_NO_OFFSET_INPUT
REMINDER_NATURAL_TIME_PARITY=PARTIAL_PROVEN_LEGACY_NATURAL_SUPPORT
REMINDER_NATURAL_TIME_CUTOVER_BLOCKER=true

Native n'utilise pas d'horloge/date locale dans le parser, puisqu'il ne résout ni offsets ni « demain ». Le scheduler utilise explicitement Europe/Paris et UTC. Résultats du helper réel :

- 2026-10-15T14:00 Paris → 2026-10-15T12:00:00+00:00.
- 2026-03-29T02:30 inexistant → première minute valide 03:00 Paris → 2026-03-29T01:00:00+00:00.
- 2026-10-25T02:30 ambigu → fold=0 → 2026-10-25T00:30:00+00:00.

Ce contrat ne supporte pas le choix d'un autre fuseau. Legacy ReminderParser travaille avec datetime.now() naïf/horloge de l'hôte, sans politique DST explicite. Ne pas réintroduire ses dates ignorées, ses défauts de récurrence ou ses minutes DST. Le futur lot doit définir les politiques ambiguës et distinguer absolute_datetime / relative_offset / daypart / recurrence, plutôt que recycler son regex générique d'heure. Les offsets minutes/heures, demain à heure explicite, weekday à heure et demain matin/soir étaient réellement dans la chaîne active AuraCore → ActionRouter._create_reminder → ReminderParser ; cette partie naturelle est donc CUTOVER_BLOCKING. Les formes jamais supportées correctement en Legacy (ce soir, cet après-midi, récurrence, dans 3 jours, mois prochain, dates écrites) sont POST_CUTOVER_ENHANCEMENT sauf décision explicite de produit, et ne justifient pas de copier un comportement incorrect.

## Grammaire et dispatch : écarts établis

La matrice canonique complète se trouve uniquement dans [text_command_prepared_action_parity.md](text_command_prepared_action_parity.md), section 005. JSON de preuve : tests/native/_evidence/text-command-005-audit.json, 157 lignes, 150 capacités de comparaison + 7 exclusions. Des lignes PARTIAL indiquent un sous-système Native existant sans preuve de dispatch texte équivalent ; elles ne déclarent pas ce sous-système défectueux.

| Entrée | Résultat Native réel du parser | Différence prouvée |
|---|---|---|
| Aura, note que Test | NONE | Préfixe assistant accepté en Legacy, absent en Native. |
| prends une note Test | NONE | Alias de création Legacy manquant. |
| je dois tester | NONE | Alias CREATE_TASK Legacy manquant. |
| marque la tâche Test comme terminée | COMPLETE_TASK raw=Test comme terminée | Suffixe non retiré ; résolution exacte ne trouve pas la tâche Test. Défaut de cible, pas du repository. |
| montre-moi mes notes | NONE | Variante LIST_NOTES Legacy absente. |
| ouvre mes tâches | NONE | Route Legacy existante ; alias tasks absent de Native._open. |
| cherche dans mes notes test | WEB_SEARCH query=dans mes notes test | Mauvais domaine : SEARCH_NOTE Legacy existe. Aujourd'hui Main.qml ouvre Search sans exécuter/transmettre le query ; risque à traiter avant tout dispatch Web automatique. |
| souviens-toi que Test | NONE | CREATE_MEMORY texte non raccordé malgré service mémoire validé. |

Autre différence de source de vérité : PersonalIntegrationDispatcher s'exécute avant IntentManager en Legacy. « liste mes tâches » peut être consommé par **tasks.list Google** avant le LIST_TASKS local. Native 004 traite cette grammaire comme local. La parité du service local ne prouve donc pas la parité du choix local/Google ; ce choix doit être rendu explicite dans un futur lot, sans fusion des modèles.

Navigation ≠ requête métier : Main.qml onIntentRequested ouvre Weather/Search/Contacts/Documents et **ignore les paramètres** location/query. Une vue correctement affichée ne prouve pas le résultat de la commande. L'état validé des modules métier reste conservé. OPEN_MODULE et DOCUMENTS_LIST sont des ajouts Native, pas des identifiants présents dans IntentManager Legacy ; les vrais comportements Legacy sont les routes dédiées Conversation, files.list et les services/planners.

## PC READ : véritable écart texte

SYSTEM_CONTROL_READ_ONLY_TEXT_PARITY=PARTIAL_MISSING_USER_GRAMMAR

Preuves Legacy : PersonalIntegrationDispatcher._dispatch_w131_pc_text, lignes 1472–1569, appelé par dispatch_integration puis handle_text puis AuraCore.try_handle_intent.

- « liste les fenêtres », « affiche les fenêtres », « fenêtres windows » → pc.discover_windows.
- « liste les processus », « montre les processus » → pc.discover_processes.
- « quelle fenêtre est active », « fenêtre active », « application active » → pc.get_foreground_window.
- « restaure la fenêtre Windows » / « annule … Windows » → pc.restore_window_state, si recovery présent ; mutation distincte derrière contrôle de cible.

Les trois premières sondes Native retournent NONE. Le service/adapter READ est validé structurellement, mais il manque le raccordement normal. La conclusion NOT_REQUIRED_FOR_TEXT_COMMAND_USER_PARITY serait incorrecte. Le rollback n'est pas présent dans l'enum Native ; il est DEFERRED. Les trois mutations PC déjà validées restent PASS_NATIVE_LIVE ; aucun retest OS n'est effectué ici. OPEN_SAFE_APP n'est pas promu en fonction active sur la seule présence d'un helper d'ownership/recording sans appel trouvé dans cette chaîne.

## Voice : gate local distinct du cœur validé

VOICE_CORE=PASS_NATIVE_LIVE
VOICE_LOCAL_INTENT_LIVE=NOT_AVAILABLE
VOICE_LOCAL_INTENT_PARITY=PARTIAL_TERMINAL_STATE_AND_LIVE_GATE
VOICE_PREPARED_ACTION_CONFIRMATION=UI_ONLY_NO_AUTOMATIC_VOCAL_CONFIRMATION

Skill Computer Use et API sky inspectés : API souris/clavier/fenêtres, sans mécanisme de fourniture physique d'une phrase au micro. list_windows n'a retourné aucune fenêtre AURA pendant cette revue. Aucun GUI lancé et aucun micro ouvert ; aucune injection de STT ne sert de preuve live.

Chaîne existante : _VoiceWorker.stop → transcriptReady → NativeVoiceBridge.transcriptReady → connexion Qt.QueuedConnection de app/main.py:3474 → NativeCoreBridge.dispatchLocalTranscript → shared NativeIntentRouter → LocalIntentProduct → PreparedAction → PendingActionCard. Aucun mot vocal ne confirme automatiquement une action.

**Défaut découvert, non corrigé :** VoiceController.submit_transcript conserve THINKING et _pending_confirmation pour une intention requires_confirmation. La terminalisation UI de la PreparedAction n'est pas reliée à ce pending/state du contrôleur. La sonde offline, sans AudioInput ni STT, a produit : state_before_cancel=thinking ; pending_action_state=cancelled ; state_after_cancel=thinking ; local_record_count=0. Preuve : text-command-005-voice-state.json. NativeVoiceBridge.startListening refuse un nouvel appui hors IDLE/ERROR, donc le nouveau parcours local peut rester occupé. Cela n'invalide pas les scénarios Voice core/Conversation déjà validés ; c'est un gate nouveau du produit local Voice.

Validation réelle à prévoir après autorisation du lot approprié : prononcer « crée une note … » puis annuler la carte et vérifier IDLE/reprise PTT ; répéter tâche ; rappel seulement avec forme temporelle supportée/approuvée ; aucune confirmation vocale automatique. Sans capture vocale réelle, ne pas attribuer PASS live à ce nouveau raccordement.

## PreparedAction UI et statuts historiques

PREPARED_ACTION_UI_LIVE=PASS
Preuves réelles 004 : clics Confirm pour trois créations locales et completion ; clic Cancel avec zéro écriture ; confirmations de suppression note/rappel autorisées par l'utilisateur au moment de l'action. Le gate de surface partagée ancien NOT_AVAILABLE/PENDING est supplanté. Les anciens rapports restent datés ; le rapport canonique désigne explicitement la supersession. Les dettes Gemini STOP réel et B4.3 REAL UI ne sont pas clôturées par cette preuve locale.

## Bytecode : dette d'hygiène séparée

PYC_TOTAL=1987
PYC_SOURCE_TREE=11 (app 1 + src 10)
PYC_RUNTIME_STATE=1974 (.runtime 218 + .venv 1756 ; aucun AppData historique scanné)
PYC_TEST_EVIDENCE=2
PYC_NEW_DURING_CONTROLLED_RUN=0
PYC_CHANGED_DURING_CONTROLLED_RUN=0
PYC_CUTOVER_BLOCKER=false

225 emplacements de cache : .runtime 26, .venv 192, app 1, src 5, tests/_evidence 1. L'inventaire détaillé figure dans le JSON. Tous les caches étaient présents dans la snapshot avant tests. Leur origine historique précise n'est pas démontrable à partir du seul mtime ; ils sont des résidus préexistants à ce contrôle, sans nouvelle génération pendant celui-ci. On ne peut pas généraliser ce résultat à chaque launcher manuel ou processus externe.

Contrôle effectué avec `-B` et `PYTHONDONTWRITEBYTECODE=1`, tests offline puis self-check QML headless. Les noms, tailles et mtime_ns des .pyc avant/après sont identiques. Les SHA-256 des sources production src/app (Python/QML/JS/SVG) sont identiques : source_changes=[] ; aucune suppression. Le runtime généré n'est pas du code versionnable ; aucun Git inspecté/exécuté.

## Tests de revue

- Local Text Command 004 : 42/42 PASS.
- PreparedAction repository + expanded 003 : 19/19 PASS.
- Conversation : 6/6 PASS.
- Total ciblé : **67/67 PASS**.
- Lot 1 strict : **53/53 PASS**.
- QML self-check Native, state-dir dédié evidence : **exit 0 / PASS**.
- Probes parser/temps et contrôle de sources/caches : PASS de collecte ; les défauts de parité ci-dessus ne sont pas masqués par le succès de collecte.
- Pas de relance globale 215 : aucun code production n'a changé. La baseline 215/215 reste celle du 004.

## Lots recommandés — non commencés

1. **Text Command 006 : contrats locaux et rappels temporels.** Spec puis lot borné pour les alias Legacy, suffixe COMPLETE_TASK, séparation SEARCH_NOTE/Web, distinction local/Google et temps naturels Legacy correctement supportés. Faire approuver heure implicite/date de référence/fuseau/DST/ambiguïtés ; ne pas ajouter de récurrence ni cloner les bugs Legacy pour rendre un statut vert.
2. **Voice local integration gate : terminalisation puis microphone réel.** Réparer uniquement après autorisation le nouveau raccordement Voice↔PreparedAction avec tests Confirm/Cancel/Error/Expired et retour utilisable ; ensuite validation humaine de trois phrases sûres, sans confirmation vocale automatique. Ne pas rouvrir audio/PTT/STT/TTS.

Ensuite, lots indépendants à planifier : commandes mémoire et PC READ ; dispatch métier Weather/Search/Contacts/Documents et Google ; choix explicite du périmètre browser/media/workspace/creative/learning/Roadmap. Le catalogue révèle plusieurs écarts, donc l'issue B (« plusieurs vrais domaines restent incomplets ») s'applique ; aucune clôture Text Command ni cutover n'est proposé. La dette .pyc peut être traitée par une autorisation d'hygiène séparée.
