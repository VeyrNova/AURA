# Lot 010 — matrice canonique de portée Text Command

Le compteur historique `150` est un inventaire de lignes Legacy, pas un
compteur de fonctionnalités. Les alias sont regroupés par capacité avant
classification. Les 17 routes Roadmap sont conservées comme `ROADMAP_ONLY`.

| DOMAIN | CANONICAL_CAPABILITY | LEGACY_REACHABILITY | NATIVE_CORE | NATIVE_ROUTER | NATIVE_DISPATCH | NATIVE_UI | NATIVE_VOICE | SAFETY_MODEL | STATUS | BLOCKER_TYPE | EVIDENCE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SYSTEM_CONTROL | fenêtres/processus/foreground | USER_ROUTABLE | PASS | PASS | PASS | PARTIAL live | shared | read-only typed | NATIVE_PASS | EXTERNAL_LIVE_GATE_ONLY | `pc_read_text_command_009.md`, `test_pc_read_009.py` |
| SYSTEM_CONTROL | focus/minimize/maximize | USER_ROUTABLE | PASS | PASS | PASS | PASS | shared | PreparedAction + confirmation | NATIVE_PASS | none | system-control suites |
| NOTES | create/list/search/delete | USER_ROUTABLE | PASS | PASS | PASS | PASS | shared | local PreparedAction | NATIVE_PASS | none | 004/006 suites |
| TASKS | create/list/complete/delete | USER_ROUTABLE | PASS | PASS | PASS | PASS | shared | local PreparedAction | NATIVE_PASS | none | 004/006 suites |
| REMINDERS | explicit ISO create/list/delete | USER_ROUTABLE | PASS | PASS | PASS | PASS | shared | local PreparedAction | NATIVE_PASS | none | 006 suites |
| REMINDERS | natural offsets/dayparts/recurrence | USER_ROUTABLE Legacy | PASS | PARTIAL | PARTIAL | PASS | shared | local PreparedAction | NATIVE_PARTIAL | TRUE_MISSING | text-command-005 audit |
| MEMORY | create/list/search/forget | USER_ROUTABLE | PASS | PASS | PASS | PASS | shared | PreparedAction | NATIVE_PASS | EXTERNAL_LIVE_GATE_ONLY | memory 008 docs |
| SEARCH | Web/note/memory disambiguation | USER_ROUTABLE | PASS | PASS | PASS | PASS | shared | read-only | NATIVE_PASS | none | 006/008/010 tests |
| WEATHER | query with location parameter | USER_ROUTABLE | PASS | PASS | PARTIAL parameter path | PASS | shared | read-only | NATIVE_PARTIAL | TRUE_MISSING | 005 audit |
| DOCUMENTS | local list/open/search | USER_ROUTABLE Native | PASS | PASS | PASS | PASS | shared | guarded local operations | NATIVE_PASS | none | Native docs tests |
| MAIL/CALENDAR | deterministic text read/write | USER_ROUTABLE Legacy | PASS | PARTIAL | PARTIAL | PASS | shared | provider-specific | NATIVE_PARTIAL | TRUE_MISSING | parity matrix |
| CONTACTS | deterministic text CRUD/search | USER_ROUTABLE Legacy | PASS | PARTIAL | PASS | PASS | shared | provider-specific | NATIVE_PARTIAL | TRUE_MISSING | parity matrix |
| MUSIC | playback controls | USER_ROUTABLE Native | PASS | PARTIAL | PARTIAL | PASS | shared | local controls | NATIVE_PARTIAL | TRUE_MISSING | music contracts |
| NAVIGATION | module open with parameters | USER_ROUTABLE | PASS | PARTIAL | PARTIAL | PASS | shared | read-only routing | NATIVE_PARTIAL | TRUE_MISSING | Main.qml parameter audit |
| ROADMAP | 17 roadmap endpoints | ROADMAP_ONLY | N/A | N/A | N/A | N/A | N/A | deferred endpoint | ROADMAP_ONLY | OTHER_DOMAIN_BLOCKER | parity matrix |
| HEALTH/VISION | health/vision helpers | UNREACHABLE | absent | absent | absent | absent | absent | none | LEGACY_UNREACHABLE | none | no active root chain |
| NOTIFICATIONS/BACKGROUND | proactive/tray paths | USER_ROUTABLE UI/background | partial | N/A | N/A | partial | N/A | separate migration | NATIVE_PARTIAL | OTHER_DOMAIN_BLOCKER | master parity audit |

Canonical native deterministic inventory includes the local notes/tasks/
reminders/memory commands, Google Calendar/Tasks prepared actions, system
control mutations, PC read-only commands, module navigation, Weather,
Documents, Search, and shared Voice parsing. Read-only PC commands never
create a PreparedAction.

`DETERMINISTIC_MUTATION_UNSAFE_LLM_FALLBACK=false`: malformed deterministic
mutations return validation/not-found/ambiguous outcomes and do not fall
through to unrestricted conversation execution.

The static 150-row Legacy inventory is therefore reduced to a smaller set of
canonical capabilities. No new broad feature family was added in Lot 010.

## Lot 011 — parameter-preserving routing (2026-10-10)

Weather, Search and parameterized OPEN_MODULE routes now preserve structured location/date/query slots. `AuraBridge.navigationContext` carries the payload to the UI boundary. No Mail/Calendar/Contacts, Music, Documents expansion, Reminder, Voice, Memory, PC Read core, Google or default-window changes were made. Automated parameter tests pass; Computer Use was unavailable, so live propagation remains pending.

## Lot 012 — Mail/Calendar/Contacts text dispatch (2026-10-10)

Read-only Mail, Calendar and Contacts intents are now routed to the existing services with structured parameters and truthful provider-unavailable states. Gmail/Calendar writes remain explicitly deferred and disabled; no contact mutation path was added without complete proven UI governance. See `docs/migration/text_command_012_productivity.md`.
