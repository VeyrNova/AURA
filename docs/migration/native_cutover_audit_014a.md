# LOT 014A — Final Native Migration Audit

Date: 2026-10-11  
Mode: read-only audit

## Executive status

Native is not ready to become the default runtime. The current default remains
Legacy, while Native is explicitly launchable with an explicit state directory.
The rollback path is preserved by retaining --core-mode legacy; no runtime
default, Legacy code, packaging, or release behavior was changed.

The main cutover risks are bounded and concrete: Native notification delivery
and tray behavior are only partial; scheduled work is guaranteed only while the
Native process remains alive; Native shutdown does not explicitly stop the
composed runtime; and several migrated-surface reachability/parity gaps remain
documented, notably Mail and the distinction between local Native Documents/
Contacts and historical provider-backed behavior.

## Phase findings

### Notifications

Status: PARTIAL / P1_BEFORE_CUTOVER.

Native has InternalReminderNotificationCenter, NotificationCoordinator,
QtWindowsReminderNotifier, and AuraTrayService. The scheduler emits due
reminders into the internal center and selects Windows toast delivery only when
the window is inactive, minimized, or hidden and the tray supports messages;
otherwise it falls back to the in-app center. Toast click handling is wired
through QSystemTrayIcon.messageClicked to restore the window.

There is no evidence of delivery after process exit, notification permission
configuration, a persistent OS scheduler, or a complete notification action
model. The implementation is therefore reachable in Native but not cutover
equivalent to a full background notification service.

NOTIFICATIONS_NATIVE_IMPLEMENTATION=PARTIAL
NOTIFICATIONS_NATIVE_REACHABLE=YES
NOTIFICATIONS_LEGACY_DEPENDENCY=LEGACY notification paths remain separate; Native does not silently instantiate them
NOTIFICATIONS_BACKGROUND_CAPABLE=PROCESS_ALIVE_ONLY
NOTIFICATIONS_CLICK_ACTIONS=RESTORE_WINDOW
NOTIFICATIONS_CUTOVER_STATUS=P1_BEFORE_CUTOVER

### Background execution

Native uses QtReminderSchedulerAdapter/QTimer for reminders and executor
threads for selected services. The scheduler is started by the Native
composition and is stopped by the runtime service-stopper list. This supports
background work while the application process remains alive, including hidden
or minimized window states through WindowStateAdapter.

No startup task, persistent scheduled work, service process, or post-exit
execution mechanism is present. NativeRuntime.stop() closes the bus and
invokes stoppers, but several executor shutdowns use wait=False; the
application lifecycle does not explicitly call native_runtime.stop() from
the normal aboutToQuit chain.

BACKGROUND_RUNTIME_OWNER=NativeRuntime plus Qt reminder adapter
BACKGROUND_WORKERS=Reminder QTimer; service executors; voice worker where active
BACKGROUND_SURVIVES_WINDOW_HIDE=YES, process alive
BACKGROUND_SURVIVES_WINDOW_CLOSE=NOT_PROVEN; normal close ends the process
BACKGROUND_SHUTDOWN_SAFE=PARTIAL
BACKGROUND_NATIVE_PARITY=PROCESS_ALIVE_ONLY
BACKGROUND_CUTOVER_STATUS=P1_BEFORE_CUTOVER

### System tray

Native constructs one AuraTrayService after QML loads. It detects tray
availability, creates the AURA icon, provides open and quit menu actions,
restores the window, and hides/deletes the icon during close. Notification
delivery shares the same tray object.

There is no explicit close-to-tray policy in the inspected Native path, no
duplicate-instance guard, and no proof of tray behavior on systems without a
tray host beyond the availability check.

TRAY_IMPLEMENTED=YES
TRAY_NATIVE=YES
TRAY_REACHABLE=YES when QSystemTrayIcon.isSystemTrayAvailable()
TRAY_SHOW_HIDE=YES via open action and icon hide on close
TRAY_EXIT=YES
TRAY_CLOSE_BEHAVIOR=PROCESS_CLOSE; close-to-tray not implemented/proven
TRAY_DUPLICATION_RISK=UNPROVEN
TRAY_CUTOVER_STATUS=P1_BEFORE_CUTOVER

### Application lifecycle

app/main.py creates QApplication, QQmlApplicationEngine, the Native
composition, and the root QML object in a deterministic order. Native services
and bridge close hooks are connected to aboutToQuit; Music, Voice, dispatcher,
and tray cleanup are explicitly connected.

The normal quit chain does not explicitly invoke native_runtime.stop(), so
runtime service stoppers and the reminder scheduler are not centrally closed
by the application lifecycle. The earlier broad-suite Qt multimedia teardown
issue was test-process contamination and was fixed in test isolation; it was
not evidence of a product shutdown failure.

NATIVE_STARTUP_SAFE=YES for explicit Native launch with --state-dir
NATIVE_SHUTDOWN_SAFE=PARTIAL
WINDOW_CLOSE_POLICY=normal window close; no close-to-tray interception
APP_QUIT_POLICY=QApplication quit; tray QUITTER AURA also calls app.quit()
RESOURCE_TEARDOWN_SAFE=PARTIAL but explicit bridge/media hooks exist
MULTIMEDIA_PRODUCT_SHUTDOWN_RISK=NOT_PROVEN; prior issue was unittest contamination
LIFECYCLE_CUTOVER_STATUS=P1_BEFORE_CUTOVER

### Persistence and state

Native state is owned by the explicit RuntimePaths profile rooted at the
caller-provided state directory, with config/data/cache/logs/models children.
The composition uses versioned Native SQLite stores and lazy/deferred reminder
scanning. Missing state is created by the owned repositories; path validation
rejects project overlap, roots, placeholders, and files.

Legacy and Native state are separate. No automatic Legacy-to-Native migration
or reverse rollback synchronization is present. Switching back to Legacy is
operationally safe, but Native-created state is not automatically visible to
Legacy.

NATIVE_STATE_SCHEMA=versioned Native SQLite plus config/state subdirectories
STATE_INITIALIZATION_SAFE=YES for explicit isolated/owned state
STATE_MIGRATION_REQUIRED_FOR_CUTOVER=YES for continuity of existing Legacy user data
LEGACY_NATIVE_STATE_SHARED=NO
ROLLBACK_DATA_RISK=Native data is not automatically visible after Legacy rollback
PERSISTENCE_CUTOVER_STATUS=P1_BEFORE_CUTOVER

### Native / Legacy routing

The parser declares --core-mode with choices legacy and native, defaulting
to legacy. Native requires --state-dir; invalid values fail closed. There is
no auto mode and no silent fallback from Native to Legacy in the inspected
startup branch.

CURRENT_DEFAULT_CORE_MODE=legacy
NATIVE_EXPLICIT_LAUNCH_SUPPORTED=YES
LEGACY_EXPLICIT_LAUNCH_SUPPORTED=YES
NATIVE_ROLLBACK_PATH=--core-mode legacy
DEFAULT_CORE_MODE=legacy
NATIVE_MODE_FLAG=--core-mode native --state-dir <explicit path>
LEGACY_MODE_FLAG=--core-mode legacy
AUTO_MODE_BEHAVIOR=NONE
INVALID_MODE_BEHAVIOR=argparse failure; missing/invalid Native state returns 2

NATIVE_REACHABLE_LEGACY_DEPENDENCIES:

| Feature | Dependency | Why still used | Cutover blocker |
|---|---|---|---|
| None proven in Native startup | No Legacy bridge/service constructor is created in the Native branch | Native and Legacy composition branches are explicit | false |

Native remains dependent on incomplete Native replacements rather than silently
falling back to Legacy.

### Feature reachability cross-check

| Feature | Native implemented | Native reachable | Legacy fallback | Known blocker | Cutover status |
|---|---|---|---|---|---|
| Diagnostics | YES | YES | NO | none in audited scope | PASS |
| Weather | PARTIAL | YES | NO | live/provider parity not complete | P1 |
| Maps | PARTIAL | YES | NO | full native map UX/provider parity not established | P1 |
| Mail | PARTIAL | YES | NO silent fallback | provider/auth capability remains incomplete | P1 |
| Agenda | YES/PARTIAL | YES | NO | external Google parity remains governed | P1 |
| Reminders | YES local | YES | NO | notification/background process lifetime only | P1 |
| Search | YES local | YES | NO | provider behavior is bounded | P2 |
| Contacts | YES local | YES | NO | local Native scope differs from historical provider-backed scope | P1 |
| Memory | YES | YES | NO | explicit Legacy data migration is separate | P1 |
| System Control | YES bounded | YES | NO | broader historical grammar not fully migrated | P1 |
| Voice | YES bounded | YES | NO | microphone/live provider gates remain external | P1 |
| Music | YES local playback | YES | NO | advanced catalog/cloud scope excluded from Lot 013 | P2 |
| Documents | YES local filesystem | YES | NO | historical provider-backed scope differs | P1 |

## Blocker matrix

| ID | Area | Finding | Evidence | Severity | Required action |
|---|---|---|---|---|---|
| CUT-014A-01 | Notifications | Native notifications are process-alive-only and permission/action coverage is incomplete | notification_coordinator.py, windows_notifier.py, tray_service.py | P1_BEFORE_CUTOVER | Complete the approved Native notification contract and verify Windows delivery/click/fallback |
| CUT-014A-02 | Background | No post-exit scheduler/startup mechanism; hidden-window behavior is not equivalent to exited-process behavior | reminder_scheduler.py, Qt adapter, explicit QApplication lifetime | P1_BEFORE_CUTOVER | Define and implement only the required background ownership model |
| CUT-014A-03 | Tray/lifecycle | Tray exists but close-to-tray, duplicate prevention, and centralized Native runtime stop are not proven | tray_service.py, app/main.py quit wiring | P1_BEFORE_CUTOVER | Stabilize lifecycle/tray policy and prove shutdown |
| CUT-014A-04 | Persistence | Legacy rollback does not see Native-created state automatically | RuntimePaths, Native SQLite composition, explicit mode split | P1_BEFORE_CUTOVER | Decide and validate a documented state continuity/rollback policy |
| CUT-014A-05 | Feature parity | Mail and provider-backed Documents/Contacts remain incomplete relative to historical reachability | current Native composition plus migration/release parity docs | P1_BEFORE_CUTOVER | Scope and complete the required provider parity or explicitly remove it from cutover requirements |

## Cutover readiness

NATIVE_DEFAULT_CUTOVER_READY=false
CUTOVER_BLOCKER_COUNT=5
P0_BLOCKER_COUNT=0
P1_COUNT=5
P2_COUNT=0

Smallest ordered remaining plan:

1. LOT 014B — Native notification contract: permissions, delivery, fallback,
   click/action semantics, and process-lifetime requirements.
2. LOT 014C — Background ownership and tray policy: decide hidden versus
   exited-process requirements, close-to-tray behavior, duplicate prevention,
   and startup/shutdown ownership.
3. LOT 014D — Lifecycle and persistence cutover safety: central runtime stop,
   resource teardown proof, state continuity, and rollback documentation.
4. LOT 014E — Provider-backed parity decision and final cutover gate for Mail,
   Documents, Contacts, and any explicitly required external capabilities.

Packaging/release readiness is intentionally not audited beyond the boundary:
no packaging, installer, startup registration, or release changes were made.

## LOT 014B closure update

The notification P1 finding is closed by native_notifications_014b.md. Native
routing now reports truthful capability and acceptance states, selects Windows
delivery only when supported, falls back to the Native in-app center without
Legacy, applies stable reminder identity and lifecycle deduplication, and
safely closes pending notification state. Post-process-exit delivery remains
explicitly deferred to LOT 014C.

P0_BLOCKER_COUNT=0
P1_COUNT=4
NOTIFICATIONS_CUTOVER_STATUS=PASS
LOT_014B=CLOSED

## LOT 014C closure update

The background and tray P1 findings are closed. NativeRuntime is now the
single process-alive background owner; scheduler start/stop is idempotent;
tray ownership and centralized explicit quit are defined; close-to-tray is
used only when a tray is available; and tray-unavailable close exits normally.
The product contract does not require post-process-exit reminders, so no
Windows scheduler or auto-start mechanism is needed for this lot.

P0_BLOCKER_COUNT=0
P1_COUNT=2
BACKGROUND_CUTOVER_STATUS=PASS
TRAY_CUTOVER_STATUS=PASS
LOT_014C=CLOSED

## LOT 014D closure update

Lifecycle and persistence cutover safety are closed. Native startup ownership
and failure semantics are explicit; shutdown is centralized and idempotent;
the multimedia issue was not reproduced outside test-process contamination;
state roots are explicit and contained; SQLite migrations are version-gated;
corrupt important data is preserved; and separate Legacy/Native rollback and
roll-forward behavior is documented and tested.

P0_BLOCKER_COUNT=0
P1_COUNT=1
LIFECYCLE_CUTOVER_STATUS=PASS
PERSISTENCE_CUTOVER_STATUS=PASS
LOT_014D=CLOSED

## LOT 014E closure update

The final provider decision and cutover gate passed. Native Mail has the
existing GoogleAuthProvider-backed read-only Gmail contract with truthful
auth/scope/error states. Local Documents and Contacts are the exposed Native
contracts; historical provider-backed variants are explicit P2 scope and are
not required for default-runtime cutover.

The default core mode is now Native. Explicit Legacy rollback remains
available. Provider, lifecycle, persistence, background/tray, notification,
and LOT 013 regression gates pass.

P0_BLOCKER_COUNT=0
P1_COUNT=0
P2_COUNT=9
CURRENT_DEFAULT_CORE_MODE=native
LEGACY_ROLLBACK_AVAILABLE=true
NATIVE_DEFAULT_CUTOVER_READY=true
LOT_014E=CLOSED
