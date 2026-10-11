# Text Command + Prepared Action parity

**État courant : section « Text Command 005 — état canonique » en fin de document. Les sections 001–004 sont historiques.**

Audit and foundation date: 2026-10-10. Legacy was inspected read-only. No Legacy execution, Git operation, shell dispatch or real window mutation was performed.

### Matrice historique du lot 001 — ne pas utiliser comme état courant

| INTENT | LEGACY_REACHABILITY | NATIVE_PARSE | NATIVE_DISPATCH | TARGET_SERVICE | MUTATING | RISK | CONFIRMATION | TEXT | VOICE | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|
| OPEN_MODULE | ACTIVE_REACHABLE | PASS | navigation route | Main/QML navigation signal | no | R0 | none | yes | same router | PASS |
| WEATHER_QUERY | ACTIVE/route evidence | PASS | route only | Weather | no | R0 | none | yes | same router | PARTIAL |
| WEB_SEARCH | ACTIVE/route evidence | PASS | route only | Search | no | R0 | none | yes | same router | PARTIAL |
| CONTACT_SEARCH | ACTIVE/route evidence | PASS | route only | Contacts | no | R0 | none | yes | same router | PARTIAL |
| DOCUMENTS_LIST | registered | PASS | route only | Documents | no | R0 | none | yes | same router | PARTIAL |
| LIST_NOTES/TASKS/REMINDERS | registered | PASS | route only | local services | read | R0 | none | yes | same router | PARTIAL |
| CREATE_NOTE/TASK/REMINDER | Legacy evidence requires per-command verification | PASS for grammar | no canonical dispatcher binding | local service | mutation | R1 | required where service supports it | yes | same router | DEFERRED |
| PC_MINIMIZE_WINDOW | native capability proven; Legacy command path not proven | PASS typed title slot | PreparedAction factory contract only | SystemControlService | mutation | R1 | required | yes | same router | PARTIAL |
| PC_MAXIMIZE_WINDOW | native capability proven; Legacy command path not proven | PASS typed title slot | PreparedAction factory contract only | SystemControlService | mutation | R1 | required | yes | same router | PARTIAL |
| PC_FOCUS_WINDOW | native capability proven; Legacy command path not proven | PASS typed title slot | PreparedAction factory contract only | SystemControlService | mutation | R1 | required | yes | same router | PARTIAL |
| NONE | ACTIVE conversation fallback | PASS | unchanged fallback | ConversationService/Agent | no | R0 | none | yes | yes | PASS |

## Contrats historiques du lot 001 (supplantés par la section canonique 005)

`NativeIntentRouter` is pure and deterministic. It performs no I/O, Qt calls, provider calls or mutation. `IntentResult` now carries typed slots, deterministic flag, source and request correlation ID. Keyboard and voice use the same parser; confirmation remains UI-bound for this lot.

`NativeActionDispatcher` returns explicit `HANDLED`, `NAVIGATED`, `PREPARED_ACTION_CREATED`, `UNAVAILABLE` or `UNSUPPORTED` result types. It can create a PreparedAction only through an injected factory; it has no shell or operating-system fallback.

System Control mutation grammar extracts only a candidate window title. A future product resolver must resolve and persist exact HWND/PID before creating an action. Confirmation must call the existing pending-action orchestrator with the exact action ID. No natural-language reparse is permitted at execution time.

PreparedAction storage already persists action ID, typed JSON payload, summary, state and expiry. Existing orchestrator/repository tests prove confirmation, cancellation, expiration, provider failure and no mutation before confirmation. Product-level System Control wiring remains deliberately incomplete until target resolution and the existing UI confirmation surface are connected.

The LLM/Agent path remains separate: `intent == NONE` goes to ConversationService. No provider or Agent tool receives `confirmed=True`, no shell string is stored, and no direct LLM-to-Windows mutation path was added.

## Security and fallback

Shell-like text (`shutdown /s`, `powershell`, `&&`, `;`, `del`) is treated as data. No shell API, arbitrary executable, shutdown/restart/logoff/sleep/hibernate or process termination is reachable from the router or dispatcher. Recognized but unavailable or invalid mutations remain structured failures; they do not silently fall through to Gemini.

## Validation

- Text/prepared-action foundation tests: 20/20 PASS.
- Existing text command tests: 4/4 PASS.
- PreparedAction repository tests: 3/3 PASS.
- System Control regression: 20/20 PASS.
- Conversation regression: 5/5 PASS.
- Agent Context regression: 9/9 PASS.
- Memory/history regression: 22/22 PASS.
- Lot 1 strict: 53/53 PASS.
- No live end-to-end System Control product path was run in this lot; the existing test-owned window harness remains available separately.

`TEXT_COMMAND_ROUTER_PARITY=PASS_NATIVE_FOUNDATION`
`TEXT_COMMAND_DISPATCH_PARITY=PARTIAL`
`PREPARED_ACTION_PARITY=PASS_EXISTING_CONTRACT_PARTIAL_PRODUCT_WIRING`
`SYSTEM_CONTROL_PRODUCT_INTEGRATION=PARTIAL`
`VOICE_TEXT_COMMAND_INTEGRATION=PASS_SHARED_ROUTER_CONTRACT`
`CONVERSATION_FALLBACK_PARITY=PASS`
`TEXT_COMMAND_CUTOVER_BLOCKER=true`

## Text Command + Prepared Action 002
- Exact-title WindowTargetResolver and SystemControlProductService are implemented. Resolution never selects an arbitrary candidate: zero, one exact match, or explicit ambiguity.
- PreparedAction payload contains operation, HWND, PID, safe display title, source and request correlation. Execution revalidates the stored identity through SystemControlService.
- Existing PendingActionOrchestrator is the only confirmation executor; QML/LLM cannot set `confirmed=True` directly.
- Live owned-window minimize validation passed: action created, no mutation before confirmation, minimize after exact confirmation, terminal state executed.
- Remaining gate: interactive confirmation surface and additional live cancel/double-confirm/stale/maximize/focus scenarios.

## Text Command + Prepared Action 002 live evidence (2026-10-10)
- Test-owned window product path executed end to end for minimize: exact-title resolution, PreparedAction persistence, no mutation before confirmation, exact action-ID confirmation, SystemControlService revalidation and actual minimize all PASS.
- Focus remains truthful Windows-policy dependent. UI visual live validation was not performed by Codex. Additional live cancel/double-confirm/stale/maximize scenarios remain recommended before declaring cutover.
- Generic execution failures now transition PreparedAction to `error` and publish structured `pending_action.error`; they no longer escape as uncaught exceptions.

## Text Command + Prepared Action 002 completion evidence (2026-10-10)
- Live owned-window matrix completed with unique child windows: minimize PASS, maximize PASS, focus PASS in this session, cancel zero mutation PASS, double confirmation exactly once PASS, stale target after close PASS.
- Every live scenario verified no mutation before confirmation. Confirmations were submitted by exact action ID through the existing PendingActionOrchestrator.
- État historique 002 : UI non inspectée à ce stade. Gate partagé supplanté par 004 : `PREPARED_ACTION_UI_LIVE=PASS`; les clics réels Confirm/Cancel sont documentés dans la section canonique 005.

## Text Command + Prepared Action 003 UI status
- `PendingActionCard.qml` is the production confirmation surface and is bound to `pendingActionId`, `pendingActionSummary`, `pendingActionState` and `pendingActionError`.
- Confirm and cancel use exact action IDs through dedicated Qt slots. Terminal error/expired actions are not left actionable.
- Human visual test instructions are in `text_command_prepared_action_ui_live_test.md`.

## Text Command 004 — local product wiring (2026-10-10)

Local services are reused without new repositories: LocalNotesService / LocalNotesRepository / LocalNotesModel; LocalTasksService / LocalTasksRepository / LocalTasksModel; LocalRemindersService / LocalRemindersRepository / LocalRemindersModel. Storage is the selected native state-dir/data/aura_native.db. Domain IDs are UUID strings (note_id, task_id, reminder_id). APIs: list(), create(title,content) / create(title,due) / create(content,trigger_at), prepare_delete(), prepare_complete() for tasks, execute_prepared_action(). Notes update and Tasks update/delete remain existing UI contracts.

Legacy read-only reachability: core/aura_core.py imports and constructs IntentManager, calls detect(text), then ActionRouter.route(intent,params). core/router.py routes all nine scoped intents to existing managers subject to SecurityPolicyEngine. LIST_NOTES, LIST_TASKS, LIST_REMINDERS, CREATE_NOTE, CREATE_TASK, CREATE_REMINDER, COMPLETE_TASK, DELETE_NOTE, DELETE_REMINDER are ACTIVE_REACHABLE (static reachability; no Legacy execution).

Native keyboard and existing voice transcript share NativeIntentRouter and NativeActionDispatcher with LocalIntentProduct. List results contain structured display fields without internal IDs; existing TasksView renders the local models. Six mutations use the existing PreparedActionRepository, PendingActionOrchestrator and PendingActionCard. Resolution is exact UUID or exact normalized label; ambiguity never selects the first record. Execution uses the stored ID only; stale entities error without touching replacements. No new LLM tools or confirmation intents are registered.

Time policy: the native router had no natural-language date parser. This lot accepts explicit YYYY-MM-DDTHH:MM and rejects missing, malformed or relative datetime requests as INVALID. Existing local reminder service/scheduler timezone policy remains authoritative. Natural-language reminder parsing parity remains deferred.

Automated: local suite 40/40; expanded regression batch 207/207 (before six additional local tests), Lot 1 strict 53/53, QML self-check PASS. Real Computer Use: note/task/reminder creation confirmed once, zero records before confirmation, task completion, cancel zero mutation and normal Gemini chat PASS. Notes/Tasks/Reminders views displayed created records without restart. Test-owned IDs: note 308e2ff5-287b-4b11-bb5c-cfaab379ab49; task 68b01661-3232-4d8f-aad6-6364d2c7dd41; reminder 1c0e0749-6bbc-468e-9448-bb3e6d8f50e1. Test labels use AURA_TEST_*_004_1430. Superseded by final validation below: authorized live UI deletes and exact-record cleanup PASS.

TEXT_COMMAND_LOCAL_MUTATION_PARITY=PASS_NATIVE (scoped intents; explicit datetime only)
TEXT_COMMAND_ROUTER_PARITY=PARTIAL_REMINDER_NATURAL_TIME
TEXT_COMMAND_DISPATCH_PARITY=PARTIAL_GLOBAL_MATRIX
TEXT_COMMAND_CUTOVER_BLOCKER=true

### Lot 007B live transcript-path closure (2026-10-10)

The real Native UI was exercised through the production-shared correlated
transcript signal using the diagnostics-only probe. Voice local cancel and
confirm reached the real PendingActionCard and terminalized Voice to `IDLE`;
keyboard-origin cancellation remained isolated. The authorized test note was
removed through the UI and verified absent by stable ID and exact title. No
microphone, network, OAuth, Google, Legacy or Git operation was used. The
global text cutover blocker remains true for previously identified gaps.
VOICE_PREPARED_ACTION_CONFIRMATION=DEFERRED
No Git, Legacy writes, Voice internals changes, Google mutations or cutover.

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



## Text Command 005 — état canonique au 10 octobre 2026

Cette section remplace les statuts courants des sections historiques 001–004, sans invalider leurs preuves dans leur périmètre. Audit uniquement : aucune correction production, aucun Git, aucune exécution de l'installation Legacy, aucune lecture de credentials, aucun réseau, aucune suppression de bytecode ni de données utilisateur.

### Périmètre et décompte

Une ligne représente une capacité métier routable unique, pas chaque regex, alias, rôle Qt ou outil interne. Les capacités PC sont normalisées vers les noms provider ; les variantes de contrôle musique sont regroupées par action. Les protocoles confirm/cancel et erreurs ne sont pas de nouvelles capacités métier. Le fallback NONE est hors dénominateur déterministe.

Décompte conservateur : **150 capacités de comparaison Legacy** = 11 PASS_NATIVE dans leur grammaire validée + 45 PARTIAL + 94 DEFERRED. Sept lignes supplémentaires NOT_REQUIRED sont explicitement hors dénominateur. Ce décompte signifie obligations de comparaison dans le catalogue statique, pas 150 fonctionnalités exécutées en Legacy ou une décision d'implémenter toutes ces extensions.

Parmi les 150, **17 Roadmap** sont exposées par l'endpoint authentifié RC4.2 `/api/roadmap-conversation`; le handler source est établi, mais leur passage depuis le Composer normal n'est pas établi. Elles restent conservativement dans l'inventaire, avec cette réserve, jusqu'à décision de périmètre. Les autres **133** proviennent des chaînes normales MainWindow/AuraCore, du dispatcher d'intégrations et du planner Internet. Les providers dépendent de configuration/connexion ; aucune disponibilité réelle Legacy n'a été testée.

Chaîne source vérifiée : MainWindow._on_user_message → AuraCore.try_handle_intent → browser_route_binding / PersonalIntegrationDispatcher.handle_text (workspace puis chaîne des wrappers dispatch_integration) → IntentManager.detect → ActionRouter.route. Les routes Internet sont planifiées dans InternetToolManager.plan et le planner Agent compose ces mêmes capacités. Les constantes d'ownership seules ne sont pas une preuve d'exécution. Des routes bornées nouvellement ajoutées en Native ne prouvent pas une parité de toutes les formulations Legacy.

PASS_NATIVE des huit intentions locales hors CREATE_REMINDER et des trois mutations PC conserve les validations 004/System Control, avec grammaire bornée. Les différences d'alias ci-dessous empêchent une parité exhaustive du routeur. La validation Memory/History/Context du stockage et du contexte demeure PASS : elle ne vaut pas preuve de raccordement des commandes texte mémoire Legacy.

### Matrice canonique unique

Les catégories décrivent l'effet métier demandé, hors écritures de logs/receipts. LOCAL_MUTATION inclut les workflows persistés et la sélection de médias qui modifie le catalogue. READ_ONLY_QUERY peut produire une proposition en mémoire, sans exécution d'action externe. Un provider/domain Native existant justifie PARTIAL uniquement comme composant disponible, pas comme exécuteur texte équivalent : notamment Documents local ≠ Google Drive et Contacts local ≠ Google Contacts.

| Capacité | Nature Legacy | Statut Native texte | Preuve source Legacy | Écart / limite |
|---|---|---|---|---|
| ANSWER_MEMORY_QUERY | READ_ONLY_QUERY | DEFERRED | [core/router.py:49](<C:/AURA GPT version/core/router.py:49>) | no matching Native text execution |
| COMPLETE_TASK | LOCAL_MUTATION | PASS_NATIVE | [core/router.py:77](<C:/AURA GPT version/core/router.py:77>) | 004 validated bounded grammar; alias gaps tracked separately |
| CONVERSATION_CLOSE | NAVIGATION_ONLY | DEFERRED | [ui/display_policy.py:37](<C:/AURA GPT version/ui/display_policy.py:37>) | Legacy UI interception; Native _open aliases omit conversation/home |
| CONVERSATION_OPEN | NAVIGATION_ONLY | DEFERRED | [ui/display_policy.py:37](<C:/AURA GPT version/ui/display_policy.py:37>) | Legacy UI interception; Native _open aliases omit conversation/home |
| CREATE_MEMORY | LOCAL_MUTATION | PARTIAL | [core/router.py:43](<C:/AURA GPT version/core/router.py:43>) | service exists, deterministic text path absent |
| CREATE_NOTE | LOCAL_MUTATION | PASS_NATIVE | [core/router.py:65](<C:/AURA GPT version/core/router.py:65>) | 004 validated bounded grammar; alias gaps tracked separately |
| CREATE_REMINDER | LOCAL_MUTATION | PARTIAL | [core/router.py:79](<C:/AURA GPT version/core/router.py:79>) | explicit datetime only; Legacy natural time missing |
| CREATE_TASK | LOCAL_MUTATION | PASS_NATIVE | [core/router.py:73](<C:/AURA GPT version/core/router.py:73>) | 004 validated bounded grammar; alias gaps tracked separately |
| DELETE_NOTE | LOCAL_MUTATION | PASS_NATIVE | [core/router.py:71](<C:/AURA GPT version/core/router.py:71>) | 004 validated bounded grammar; alias gaps tracked separately |
| DELETE_REMINDER | LOCAL_MUTATION | PASS_NATIVE | [core/router.py:83](<C:/AURA GPT version/core/router.py:83>) | 004 validated bounded grammar; alias gaps tracked separately |
| DEVELOPER_MODE_DISABLE | LOCAL_MUTATION | PARTIAL | [runtime/aura_developer_live_bridge.py:84](<C:/AURA GPT version/runtime/aura_developer_live_bridge.py:84>) | ADF native remains validated; Legacy text-toggle/workspace grammar not connected to Native router |
| DEVELOPER_MODE_ENABLE | LOCAL_MUTATION | PARTIAL | [runtime/aura_developer_live_bridge.py:84](<C:/AURA GPT version/runtime/aura_developer_live_bridge.py:84>) | ADF native remains validated; Legacy text-toggle/workspace grammar not connected to Native router |
| DEVELOPER_WORKSPACE_OPEN | NAVIGATION_ONLY | PARTIAL | [runtime/aura_developer_live_bridge.py:84](<C:/AURA GPT version/runtime/aura_developer_live_bridge.py:84>) | ADF native remains validated; Legacy text-toggle/workspace grammar not connected to Native router |
| DOCUMENTS_LIST | READ_ONLY_QUERY | NOT_REQUIRED | [core/intent_manager.py:148](<C:/AURA GPT version/core/intent_manager.py:148>) | Native addition; Legacy files.list is a separate business query |
| EXPLAIN_MEMORY | READ_ONLY_QUERY | DEFERRED | [core/router.py:57](<C:/AURA GPT version/core/router.py:57>) | no matching Native text execution |
| FORGET_ALL_MEMORIES | LOCAL_MUTATION | DEFERRED | [core/router.py:55](<C:/AURA GPT version/core/router.py:55>) | no matching Native text execution |
| FORGET_MEMORY | LOCAL_MUTATION | PARTIAL | [core/router.py:51](<C:/AURA GPT version/core/router.py:51>) | service exists, deterministic text path absent |
| FORGET_MEMORY_ALL | LOCAL_MUTATION | DEFERRED | [core/router.py:53](<C:/AURA GPT version/core/router.py:53>) | no matching Native text execution |
| KNOWLEDGE_REFERENCE_LOCAL | READ_ONLY_QUERY | DEFERRED | [tools/internet_manager.py:202](<C:/AURA GPT version/tools/internet_manager.py:202>) | Native services/tools do not prove deterministic Composer argument dispatch; Main.qml routes only |
| LIST_MEMORIES | READ_ONLY_QUERY | PARTIAL | [core/router.py:45](<C:/AURA GPT version/core/router.py:45>) | service exists, deterministic text path absent |
| LIST_NOTES | READ_ONLY_QUERY | PASS_NATIVE | [core/router.py:67](<C:/AURA GPT version/core/router.py:67>) | 004 validated bounded grammar; alias gaps tracked separately |
| LIST_REMINDERS | READ_ONLY_QUERY | PASS_NATIVE | [core/router.py:81](<C:/AURA GPT version/core/router.py:81>) | 004 validated bounded grammar; alias gaps tracked separately |
| LIST_TASKS | READ_ONLY_QUERY | PASS_NATIVE | [core/router.py:75](<C:/AURA GPT version/core/router.py:75>) | 004 validated bounded grammar; alias gaps tracked separately |
| MAPS_DIRECTIONS | READ_ONLY_QUERY | PARTIAL | [tools/internet_manager.py:202](<C:/AURA GPT version/tools/internet_manager.py:202>) | Native services/tools do not prove deterministic Composer argument dispatch; Main.qml routes only |
| MAPS_LOCATE | READ_ONLY_QUERY | PARTIAL | [tools/internet_manager.py:202](<C:/AURA GPT version/tools/internet_manager.py:202>) | Native services/tools do not prove deterministic Composer argument dispatch; Main.qml routes only |
| MEMORY_STATUS | READ_ONLY_QUERY | DEFERRED | [core/router.py:59](<C:/AURA GPT version/core/router.py:59>) | no matching Native text execution |
| NONE | CONVERSATION_FALLBACK | NOT_REQUIRED | [core/intent_manager.py:148](<C:/AURA GPT version/core/intent_manager.py:148>) | not deterministic; unchanged native live Conversation baseline PASS |
| OPEN_MODULE | NAVIGATION_ONLY | NOT_REQUIRED | [ui/display_policy.py:37](<C:/AURA GPT version/ui/display_policy.py:37>) | generic Native addition; Legacy Conversation UI has dedicated routes |
| OPEN_SAFE_APP | SYSTEM_MUTATION | NOT_REQUIRED | [runtime/route_contract.py:128](<C:/AURA GPT version/runtime/route_contract.py:128>) | ownership constant/recording helper does not prove caller or normal grammar |
| ROADMAP_ADD | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:461](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:461>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_ARCHIVE | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:301](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:301>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_ARCHIVE_PHASE | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:331](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:331>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_BLOCKED | READ_ONLY_QUERY | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:265](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:265>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_DELETE | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:310](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:310>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_FINISH | READ_ONLY_QUERY | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:235](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:235>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_HISTORY | READ_ONLY_QUERY | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:294](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:294>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_NEXT | READ_ONLY_QUERY | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:231](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:231>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_OPEN | NAVIGATION_ONLY | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:216](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:216>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_PHASE | READ_ONLY_QUERY | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:284](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:284>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_RENAME_PHASE | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:479](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:479>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_RESTORE_MILESTONE | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:424](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:424>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_SCHEDULE | READ_ONLY_QUERY | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:251](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:251>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_SHIFT | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:410](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:410>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_STATUS | READ_ONLY_QUERY | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:227](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:227>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_UPDATE_PROGRESS | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:380](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:380>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| ROADMAP_UPDATE_STATUS | LOCAL_MUTATION | DEFERRED | [runtime/aura_roadmap_conversation_v25f.py:357](<C:/AURA GPT version/runtime/aura_roadmap_conversation_v25f.py:357>) | RC4.2 /api/roadmap-conversation handler present; normal Composer submission not established |
| SEARCH_MEMORY | READ_ONLY_QUERY | PARTIAL | [core/router.py:47](<C:/AURA GPT version/core/router.py:47>) | service exists, deterministic text path absent |
| SEARCH_NOTE | READ_ONLY_QUERY | DEFERRED | [core/router.py:69](<C:/AURA GPT version/core/router.py:69>) | no matching Native text execution |
| SET_MEMORY_NORMAL_MODE | LOCAL_MUTATION | DEFERRED | [core/router.py:63](<C:/AURA GPT version/core/router.py:63>) | no matching Native text execution |
| SET_MEMORY_PRIVATE_MODE | LOCAL_MUTATION | DEFERRED | [core/router.py:61](<C:/AURA GPT version/core/router.py:61>) | no matching Native text execution |
| WEB_FETCH | READ_ONLY_QUERY | PARTIAL | [tools/internet_manager.py:202](<C:/AURA GPT version/tools/internet_manager.py:202>) | Native services/tools do not prove deterministic Composer argument dispatch; Main.qml routes only |
| WEB_KNOWLEDGE_REFERENCE | READ_ONLY_QUERY | DEFERRED | [tools/internet_manager.py:202](<C:/AURA GPT version/tools/internet_manager.py:202>) | Native services/tools do not prove deterministic Composer argument dispatch; Main.qml routes only |
| WEB_SEARCH | READ_ONLY_QUERY | PARTIAL | [tools/internet_manager.py:202](<C:/AURA GPT version/tools/internet_manager.py:202>) | Native services/tools do not prove deterministic Composer argument dispatch; Main.qml routes only |
| WEB_WEATHER | READ_ONLY_QUERY | PARTIAL | [tools/internet_manager.py:202](<C:/AURA GPT version/tools/internet_manager.py:202>) | Native services/tools do not prove deterministic Composer argument dispatch; Main.qml routes only |
| browser.click | EXTERNAL_MUTATION | DEFERRED | [runtime/browser_route_binding_v096.py:193](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:193>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.download | EXTERNAL_MUTATION | DEFERRED | [runtime/browser_route_binding_v096.py:241](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:241>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.extract | READ_ONLY_QUERY | DEFERRED | [runtime/browser_route_binding_v096.py:144](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:144>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.fill | EXTERNAL_MUTATION | DEFERRED | [runtime/browser_route_binding_v096.py:210](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:210>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.navigate | NAVIGATION_ONLY | DEFERRED | [runtime/browser_route_binding_v096.py:175](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:175>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.open | NAVIGATION_ONLY | DEFERRED | [runtime/browser_route_binding_v096.py:159](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:159>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.read | READ_ONLY_QUERY | DEFERRED | [runtime/browser_route_binding_v096.py:127](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:127>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.search | READ_ONLY_QUERY | DEFERRED | [runtime/browser_route_binding_v096.py:108](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:108>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.submit | EXTERNAL_MUTATION | DEFERRED | [runtime/browser_route_binding_v096.py:225](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:225>) | existing Legacy browser text resolver; do not reintroduce Chromium |
| browser.workflow | EXTERNAL_MUTATION | NOT_REQUIRED | [runtime/browser_route_binding_v096.py:27](<C:/AURA GPT version/runtime/browser_route_binding_v096.py:27>) | registered orchestration; no text resolver branch |
| calendar.create_event | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:849](<C:/AURA GPT version/runtime/personal_integrations.py:849>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| calendar.delete_event | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:888](<C:/AURA GPT version/runtime/personal_integrations.py:888>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| calendar.free_busy | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:801](<C:/AURA GPT version/runtime/personal_integrations.py:801>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| calendar.list | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:779](<C:/AURA GPT version/runtime/personal_integrations.py:779>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| calendar.read_event | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:816](<C:/AURA GPT version/runtime/personal_integrations.py:816>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| calendar.respond_invitation | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:873](<C:/AURA GPT version/runtime/personal_integrations.py:873>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| calendar.search_events | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:281](<C:/AURA GPT version/runtime/personal_integrations.py:281>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| channel.compare_formats | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2453](<C:/AURA GPT version/runtime/personal_integrations.py:2453>) | dispatch wrapper chain present; Native equivalent text route absent |
| channel.editorial_mix | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2477](<C:/AURA GPT version/runtime/personal_integrations.py:2477>) | dispatch wrapper chain present; Native equivalent text route absent |
| channel.publishing_windows | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2464](<C:/AURA GPT version/runtime/personal_integrations.py:2464>) | dispatch wrapper chain present; Native equivalent text route absent |
| channel.recommendation_matrix | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2523](<C:/AURA GPT version/runtime/personal_integrations.py:2523>) | dispatch wrapper chain present; Native equivalent text route absent |
| contacts.create | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:720](<C:/AURA GPT version/runtime/personal_integrations.py:720>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| contacts.delete | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:760](<C:/AURA GPT version/runtime/personal_integrations.py:760>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| contacts.read | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:692](<C:/AURA GPT version/runtime/personal_integrations.py:692>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| contacts.search | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:301](<C:/AURA GPT version/runtime/personal_integrations.py:301>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| contacts.update | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:748](<C:/AURA GPT version/runtime/personal_integrations.py:748>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.archive | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:513](<C:/AURA GPT version/runtime/personal_integrations.py:513>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.create_draft | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:445](<C:/AURA GPT version/runtime/personal_integrations.py:445>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.forward | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:498](<C:/AURA GPT version/runtime/personal_integrations.py:498>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.list_attachments | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:433](<C:/AURA GPT version/runtime/personal_integrations.py:433>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.read | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:422](<C:/AURA GPT version/runtime/personal_integrations.py:422>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.reply | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:486](<C:/AURA GPT version/runtime/personal_integrations.py:486>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.search | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:342](<C:/AURA GPT version/runtime/personal_integrations.py:342>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.send | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:461](<C:/AURA GPT version/runtime/personal_integrations.py:461>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| email.trash | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:524](<C:/AURA GPT version/runtime/personal_integrations.py:524>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| files.create | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:615](<C:/AURA GPT version/runtime/personal_integrations.py:615>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| files.delete | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:541](<C:/AURA GPT version/runtime/personal_integrations.py:541>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| files.list | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:382](<C:/AURA GPT version/runtime/personal_integrations.py:382>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| files.move | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:557](<C:/AURA GPT version/runtime/personal_integrations.py:557>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| files.read | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:634](<C:/AURA GPT version/runtime/personal_integrations.py:634>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| files.search | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:364](<C:/AURA GPT version/runtime/personal_integrations.py:364>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| files.update | EXTERNAL_MUTATION | PARTIAL | [runtime/personal_integrations.py:585](<C:/AURA GPT version/runtime/personal_integrations.py:585>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| learning.approve_candidate | LOCAL_MUTATION | DEFERRED | [runtime/personal_integrations.py:2769](<C:/AURA GPT version/runtime/personal_integrations.py:2769>) | dispatch wrapper chain present; Native equivalent text route absent |
| learning.consolidate_candidate | LOCAL_MUTATION | DEFERRED | [runtime/personal_integrations.py:2815](<C:/AURA GPT version/runtime/personal_integrations.py:2815>) | dispatch wrapper chain present; Native equivalent text route absent |
| learning.consolidation_plan | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2692](<C:/AURA GPT version/runtime/personal_integrations.py:2692>) | dispatch wrapper chain present; Native equivalent text route absent |
| learning.list_candidates | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2660](<C:/AURA GPT version/runtime/personal_integrations.py:2660>) | dispatch wrapper chain present; Native equivalent text route absent |
| learning.list_conflicts | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2676](<C:/AURA GPT version/runtime/personal_integrations.py:2676>) | dispatch wrapper chain present; Native equivalent text route absent |
| learning.list_consolidated | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2830](<C:/AURA GPT version/runtime/personal_integrations.py:2830>) | dispatch wrapper chain present; Native equivalent text route absent |
| learning.propose_candidate | LOCAL_MUTATION | DEFERRED | [runtime/personal_integrations.py:2636](<C:/AURA GPT version/runtime/personal_integrations.py:2636>) | dispatch wrapper chain present; Native equivalent text route absent |
| learning.resolve_conflict | LOCAL_MUTATION | DEFERRED | [runtime/personal_integrations.py:2784](<C:/AURA GPT version/runtime/personal_integrations.py:2784>) | dispatch wrapper chain present; Native equivalent text route absent |
| longform.chapter_context | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2233](<C:/AURA GPT version/runtime/personal_integrations.py:2233>) | dispatch wrapper chain present; Native equivalent text route absent |
| longform.chapter_revision_report | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2314](<C:/AURA GPT version/runtime/personal_integrations.py:2314>) | dispatch wrapper chain present; Native equivalent text route absent |
| longform.chapter_transition | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2331](<C:/AURA GPT version/runtime/personal_integrations.py:2331>) | dispatch wrapper chain present; Native equivalent text route absent |
| longform.context_search_pack | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2268](<C:/AURA GPT version/runtime/personal_integrations.py:2268>) | dispatch wrapper chain present; Native equivalent text route absent |
| longform.continuity_audit | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2220](<C:/AURA GPT version/runtime/personal_integrations.py:2220>) | dispatch wrapper chain present; Native equivalent text route absent |
| longform.manuscript_outline | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2212](<C:/AURA GPT version/runtime/personal_integrations.py:2212>) | dispatch wrapper chain present; Native equivalent text route absent |
| longform.manuscript_revision_report | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2346](<C:/AURA GPT version/runtime/personal_integrations.py:2346>) | dispatch wrapper chain present; Native equivalent text route absent |
| longform.revision_brief | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2250](<C:/AURA GPT version/runtime/personal_integrations.py:2250>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.catalog_summary | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2908](<C:/AURA GPT version/runtime/personal_integrations.py:2908>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.control.next | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3189](<C:/AURA GPT version/runtime/personal_integrations.py:3189>) | real player control text wrappers; Native routing absent |
| media.control.pause | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3438](<C:/AURA GPT version/runtime/personal_integrations.py:3438>) | real player control text wrappers; Native routing absent |
| media.control.previous | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3189](<C:/AURA GPT version/runtime/personal_integrations.py:3189>) | real player control text wrappers; Native routing absent |
| media.control.resume | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3449](<C:/AURA GPT version/runtime/personal_integrations.py:3449>) | real player control text wrappers; Native routing absent |
| media.control.seek_percent | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3486](<C:/AURA GPT version/runtime/personal_integrations.py:3486>) | real player control text wrappers; Native routing absent |
| media.control.stop | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3460](<C:/AURA GPT version/runtime/personal_integrations.py:3460>) | real player control text wrappers; Native routing absent |
| media.control.volume_down | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3189](<C:/AURA GPT version/runtime/personal_integrations.py:3189>) | real player control text wrappers; Native routing absent |
| media.control.volume_mute | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3189](<C:/AURA GPT version/runtime/personal_integrations.py:3189>) | real player control text wrappers; Native routing absent |
| media.control.volume_percent | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3473](<C:/AURA GPT version/runtime/personal_integrations.py:3473>) | real player control text wrappers; Native routing absent |
| media.control.volume_up | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3189](<C:/AURA GPT version/runtime/personal_integrations.py:3189>) | real player control text wrappers; Native routing absent |
| media.list_items | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:3096](<C:/AURA GPT version/runtime/personal_integrations.py:3096>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.pick_local_folder | LOCAL_MUTATION | DEFERRED | [runtime/personal_integrations.py:3290](<C:/AURA GPT version/runtime/personal_integrations.py:3290>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.pick_local_music | LOCAL_MUTATION | DEFERRED | [runtime/personal_integrations.py:3266](<C:/AURA GPT version/runtime/personal_integrations.py:3266>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.pick_local_playlist | LOCAL_MUTATION | DEFERRED | [runtime/personal_integrations.py:3278](<C:/AURA GPT version/runtime/personal_integrations.py:3278>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.play_confirmed | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:3124](<C:/AURA GPT version/runtime/personal_integrations.py:3124>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.playback_intent | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:3005](<C:/AURA GPT version/runtime/personal_integrations.py:3005>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.player_status | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:3145](<C:/AURA GPT version/runtime/personal_integrations.py:3145>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.playlist_proposal | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2979](<C:/AURA GPT version/runtime/personal_integrations.py:2979>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.search | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2932](<C:/AURA GPT version/runtime/personal_integrations.py:2932>) | dispatch wrapper chain present; Native equivalent text route absent |
| media.smart_queue | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2954](<C:/AURA GPT version/runtime/personal_integrations.py:2954>) | dispatch wrapper chain present; Native equivalent text route absent |
| obsidian.creative_snapshot | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:1956](<C:/AURA GPT version/runtime/personal_integrations.py:1956>) | dispatch wrapper chain present; Native equivalent text route absent |
| obsidian.discover_vaults | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:1952](<C:/AURA GPT version/runtime/personal_integrations.py:1952>) | dispatch wrapper chain present; Native equivalent text route absent |
| obsidian.search_context | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:1971](<C:/AURA GPT version/runtime/personal_integrations.py:1971>) | dispatch wrapper chain present; Native equivalent text route absent |
| pc.destructive_unbound | SYSTEM_MUTATION | NOT_REQUIRED | [runtime/personal_integrations.py:1457](<C:/AURA GPT version/runtime/personal_integrations.py:1457>) | Legacy explicitly denies close/kill |
| pc.discover_processes | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:1509](<C:/AURA GPT version/runtime/personal_integrations.py:1509>) | dispatch wrapper chain present; Native equivalent text route absent |
| pc.discover_windows | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:1479](<C:/AURA GPT version/runtime/personal_integrations.py:1479>) | dispatch wrapper chain present; Native equivalent text route absent |
| pc.focus_window | SYSTEM_MUTATION | PASS_NATIVE | [runtime/personal_integrations.py:1583](<C:/AURA GPT version/runtime/personal_integrations.py:1583>) | System Control product live baseline; bounded title grammar |
| pc.get_foreground_window | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:1549](<C:/AURA GPT version/runtime/personal_integrations.py:1549>) | dispatch wrapper chain present; Native equivalent text route absent |
| pc.maximize_window | SYSTEM_MUTATION | PASS_NATIVE | [runtime/personal_integrations.py:1578](<C:/AURA GPT version/runtime/personal_integrations.py:1578>) | System Control product live baseline; bounded title grammar |
| pc.minimize_window | SYSTEM_MUTATION | PASS_NATIVE | [runtime/personal_integrations.py:1576](<C:/AURA GPT version/runtime/personal_integrations.py:1576>) | System Control product live baseline; bounded title grammar |
| pc.restore_window_state | SYSTEM_MUTATION | DEFERRED | [runtime/personal_integrations.py:1439](<C:/AURA GPT version/runtime/personal_integrations.py:1439>) | Legacy text rollback exists; Native action enum has no restore operation |
| publishing.create_workflow_plan | LOCAL_MUTATION | DEFERRED | [runtime/personal_integrations.py:2504](<C:/AURA GPT version/runtime/personal_integrations.py:2504>) | dispatch wrapper chain present; Native equivalent text route absent |
| publishing.workflow_status | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2552](<C:/AURA GPT version/runtime/personal_integrations.py:2552>) | dispatch wrapper chain present; Native equivalent text route absent |
| runtime.status.preview | READ_ONLY_QUERY | NOT_REQUIRED | [runtime/aura_conversation_intent_handoff_v200.py:229](<C:/AURA GPT version/runtime/aura_conversation_intent_handoff_v200.py:229>) | A200 explicit adjacent preview, direct natural language execution disabled |
| tasks.list | READ_ONLY_QUERY | PARTIAL | [runtime/personal_integrations.py:315](<C:/AURA GPT version/runtime/personal_integrations.py:315>) | Native domain/UI exists; no canonical same-capability text dispatch (provider identity not assumed) |
| workspace.activate | LOCAL_MUTATION | DEFERRED | [runtime/workspace_live_conversation_bridge_v130.py:68](<C:/AURA GPT version/runtime/workspace_live_conversation_bridge_v130.py:68>) | Legacy handle_text invokes workspace bridge; Native ADF is not equivalent grammar |
| workspace.active | READ_ONLY_QUERY | DEFERRED | [runtime/workspace_live_conversation_bridge_v130.py:68](<C:/AURA GPT version/runtime/workspace_live_conversation_bridge_v130.py:68>) | Legacy handle_text invokes workspace bridge; Native ADF is not equivalent grammar |
| workspace.list | READ_ONLY_QUERY | DEFERRED | [runtime/workspace_live_conversation_bridge_v130.py:68](<C:/AURA GPT version/runtime/workspace_live_conversation_bridge_v130.py:68>) | Legacy handle_text invokes workspace bridge; Native ADF is not equivalent grammar |
| workspace.resume | READ_ONLY_QUERY | DEFERRED | [runtime/workspace_live_conversation_bridge_v130.py:68](<C:/AURA GPT version/runtime/workspace_live_conversation_bridge_v130.py:68>) | Legacy handle_text invokes workspace bridge; Native ADF is not equivalent grammar |
| youtube.channel_snapshot | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2379](<C:/AURA GPT version/runtime/personal_integrations.py:2379>) | dispatch wrapper chain present; Native equivalent text route absent |
| youtube.next_upload_brief | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2381](<C:/AURA GPT version/runtime/personal_integrations.py:2381>) | dispatch wrapper chain present; Native equivalent text route absent |
| youtube.opportunity_board | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2380](<C:/AURA GPT version/runtime/personal_integrations.py:2380>) | dispatch wrapper chain present; Native equivalent text route absent |
| youtube.publishing_cadence | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2382](<C:/AURA GPT version/runtime/personal_integrations.py:2382>) | dispatch wrapper chain present; Native equivalent text route absent |
| youtube.scorecards | READ_ONLY_QUERY | DEFERRED | [runtime/personal_integrations.py:2383](<C:/AURA GPT version/runtime/personal_integrations.py:2383>) | dispatch wrapper chain present; Native equivalent text route absent |

### Décision de parité globale

TEXT_COMMAND_GLOBAL_MATRIX_COMPLETE=PASS_STATIC_ROUTABLE_PERIMETER
LEGACY_REQUIRED_DETERMINISTIC_INTENTS=150 (inventaire conservateur, dont 17 endpoints Roadmap)
NATIVE_PASS_INTENTS=11
NATIVE_PARTIAL_INTENTS=45
NATIVE_DEFERRED_INTENTS=94
NOT_REQUIRED_INTENTS=7
TEXT_COMMAND_ROUTER_PARITY=PARTIAL_PROVEN_GRAMMAR_GAPS
TEXT_COMMAND_DISPATCH_PARITY=PARTIAL_PROVEN_DOMAIN_GAPS
TEXT_COMMAND_CUTOVER_BLOCKER=true

Blocages précis : (1) parser temporel naturel des rappels ; (2) SEARCH_NOTE et onze intentions mémoire non raccordées au Composer ; (3) lecture PC fenêtres/processus/foreground et rollback Windows non raccordés ; (4) WEATHER/WEB_SEARCH/CONTACT_SEARCH ouvrent un module sans lui transmettre/exécuter les arguments ; (5) commandes métier Google Mail/Calendar/Contacts/Drive/Tasks sans dispatcher texte équivalent ; (6) commandes de navigation Conversation/Accueil et Developer non raccordées ; (7) grammaire et wrappers des extensions browser, workspace, media, Obsidian, longform, YouTube/publishing et learning absents ; (8) périmètre Roadmap à décider explicitement ; (9) terminalisation du nouveau parcours local Voice et validation vocale réelle manquantes. Le statut n'est plus « matrice globale incomplète ».

Les mutations externes/système doivent rester derrière une confirmation Native adaptée. Les routes browser ne nécessitent pas de réintroduire Chromium. Aucune nouvelle fonctionnalité ni réintroduction de confirmation vocale automatique n'est autorisée par cet audit.

### Statuts UI et baselines préservés

PREPARED_ACTION_UI_LIVE=PASS
Preuve : Computer Use 004 a réellement cliqué CONFIRMER pour créer note/tâche/rappel, compléter la tâche et supprimer note/rappel autorisés ; ANNULER a été cliqué avec zéro mutation. Cette preuve clôture le gate de la surface PendingActionCard partagée. Elle ne vaut pas un nouveau test live de tous les domaines.

VOICE_CORE=PASS_NATIVE_LIVE (baseline utilisateur conservée)
SYSTEM_CONTROL=PASS_NATIVE_LIVE (baseline conservée)
MEMORY_HISTORY_CONTEXT=PASS_NATIVE (baseline conservée)
TEXT_CHAT=PASS_NATIVE_LIVE (baseline conservée)
LOCAL_TEXT_COMMANDS=PASS_NATIVE_SCOPED (baseline 004 conservée)
VOICE_LOCAL_INTENT_LIVE=NOT_AVAILABLE
VOICE_LOCAL_INTENT_PARITY=PARTIAL_TERMINAL_STATE_AND_LIVE_GATE
VOICE_PREPARED_ACTION_CONFIRMATION=UI_ONLY_NO_AUTOMATIC_VOCAL_CONFIRMATION

Détails des formes temporelles, différences de grammaire, sonde vocale, tests et bytecode : voir [revue 005](text_command_005_remaining_gaps_review.md). Aucun lot suivant commencé.

## Lot 007 — Voice local PreparedAction

Le défaut de terminalisation Voice a été corrigé par une corrélation explicite `voice_request_id` → `prepared_action_id`. Les issues `cancelled`, `executed`, `error` et `expired` libèrent Voice vers `IDLE` une seule fois ; les actions clavier restent isolées. La validation automatisée ciblée est verte. Le microphone physique n'est pas contrôlable par Computer Use, donc aucun PASS micro live n'est revendiqué. Voir `docs/migration/voice_local_prepared_action_007.md`.
## Lot 006 status

The local French temporal parser and local note-search routing are implemented in `text_command_006.md`. This does not close the global parity gate: Memory commands, PC READ grammar and other proven deterministic Legacy routes remain outside this lot.
## Lot 006B — clôture native live (2026-10-10)

Le périmètre local Notes/Tasks/Reminders et le parsing temporel français sont validés en natif. Les deux rappels de test et la note de test autorisés ont été supprimés via l'interface après confirmation, puis contrôlés absents par leurs IDs exacts dans SQLite. Aucun autre enregistrement n'a été touché. `TEXT_COMMAND_006=PASS_NATIVE_LIVE`; récurrence demeure `UNSUPPORTED_RECURRENCE`; aucun lot 007 n'est commencé.

## Lot 008 — Memory command wiring (2026-10-10)

Native now recognizes the proven remember/store, list/show, search/find and forget grammar subset. Read/search calls MemoryService directly; create/forget create `memory.*` PreparedActions and are executed only after PendingAction confirmation with exact stable `memory_id` binding for forget. The Qt scheduler first scan is deferred to the event loop so composition remains lazy until a database operation. Full live Computer Use validation is pending because no AURA window was available in the current desktop session.

## Lot 008B live gate (2026-10-10)

The live AURA Native process was started with an isolated state directory. Computer Use located the window but could not inject input because the foreground window did not report a process id. Consequently no live Memory create/read/search/cancel/delete was attempted, no test data was created, and no cleanup was necessary. Focused offline validation passed; the strict Lot1 validator currently reports forbidden import `aura_native.notes` and exits 1. Lot 008B is not PASS and Lot 009 has not started.

## Lot 009 — PC read-only text commands (2026-10-10)

Native deterministic intents `PC_LIST_WINDOWS`, `PC_LIST_PROCESSES`, and `PC_GET_FOREGROUND_WINDOW` now route directly to the existing SystemControlService. No PreparedAction, shell, mutation, Google, or Voice change is involved. Results are structured and bounded; raw HWND/PID are hidden from presentation. Automated PC read tests are 5/5 and Lot1 remains 53/53. Computer Use was unavailable (`apps=[]`), so no live AURA interaction or test window was performed.

## Lot 010 — final reachability gate (2026-10-10)

The canonical classification is in `text_command_010_final_reachability.md`. The historical 150-row inventory is reduced by alias collapse and reachability evidence; it is not a 150-feature blocker count. Native deterministic aliases added in this lot are `Aura, note que`, `prends une note`, `je dois ...`, `montre-moi mes notes`, `ouvre mes tâches`, and the `comme terminée` task suffix. PC read remains automated with an external Computer Use live gate. Natural reminder time, provider-specific Mail/Calendar/Contacts text dispatch, Weather parameter propagation, Music text parity, and module navigation parameter propagation remain true partial gaps; Roadmap endpoints remain Roadmap-only.

## Lot 011 — parameter-preserving routing (2026-10-10)

Implemented the scoped Weather/Search/Navigation parameter contract. Router-to-dispatch and dispatch-to-UI payloads retain location/date/query; text and voice share the same semantic slots. `test_text_command_011_parameters.py` is 5/5; QML Native and Lot1 strict remain green. Live Computer Use validation was unavailable (`apps=[]`).

## Lot 012 — productivity text dispatch (2026-10-10)

Added deterministic read routes for Mail, Calendar and Contacts. No Google write, OAuth scope change, Voice change, or core redesign. Automated productivity tests 6/6; targeted regressions and Lot1 53/53 pass. Computer Use unavailable (`apps=[]`), so live read validation remains external.

## 012C authority closure addendum — 2026-10-10

The final parity model is structural: `UiPreparedActionConfirmer` delegates to the orchestrator's internal UI confirmation capability, while `pending_action.confirm` remains intentionally non-authoritative regardless of its source field. The migrated Memory 008 and Voice 007 tests assert generic-bus rejection followed by simulated explicit UI confirmation.
