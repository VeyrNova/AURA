# LOT 014D — Native lifecycle and persistence cutover safety

Status: CLOSED  
Validation date: 2026-10-11

## Startup ownership and failure policy

Startup is owned by app/main.py: QApplication and argument parsing come first,
NativeRuntime composition resolves the explicit state root, NativeRuntime
starts once, bridges and QML are composed, Main.qml loads, then the reminder
background owner and tray are attached. The Native branch does not construct
Legacy services and never silently falls back to Legacy.

Fatal failures are missing/invalid Native state configuration, required
composition failure, database open/migration failure, or a missing QML root.
They return a non-zero startup result. Notification backend and tray
unavailability are degraded-but-runnable: Native in-app fallback and normal
foreground application behavior remain available.

## Shutdown and multimedia

The central Native shutdown owner is the callback installed by app/main.py and
passed to AuraTrayService. It is idempotent and orders: prevent repeated
shutdown; stop process-alive background scheduling; close notification state;
close bridges and Music/Voice resources; close the dispatcher; stop the
NativeRuntime; then request QApplication quit only for explicit tray Quit.
Normal aboutToQuit reuses the same path without re-entering app.quit().

The previous Qt multimedia failure was exercised in five repeated isolated
Music load/play/pause/stop/shutdown processes and did not reproduce. It is
classified as TEST_ONLY_CONTAMINATION, not a product shutdown defect. No
additional speculative multimedia production change was made.

MULTIMEDIA_PRODUCT_SHUTDOWN_RISK=TEST_ONLY_CONTAMINATION

## Native state inventory

All mutable Native state is rooted beneath the configured RuntimePaths state
root. The principal stores are:

| Store | Owner | Format/location | Version/lazy behavior | Secrets |
|---|---|---|---|---|
| Core data: memory, conversations, reminders, tasks, notes, prepared actions, provider settings | NativeDatabase/repositories | SQLite, state/data/aura_native.db | schema_migrations through version 13; opened on repository use | false |
| Contacts | ContactsRepository | SQLite, state/data/contacts.sqlite | SQLite user_version 1; repository-owned | false |
| ADF jobs/audit | ADFService | SQLite under state/data/adf_state | migration-backed Native schema | false |
| UI locale | LocaleService | JSON, state/config/ui_locale.json | bounded values fr-FR/en-US; lazy read | false |
| OAuth configuration reference | GoogleOAuthClientConfigService | state-owned config path | explicit config service; credentials remain in secure store | references only |
| Music/Documents runtime data | Native bridges/services | state-owned runtime objects and Documents data root | no extra persistent index claimed | false |

SQLite transactions provide database atomicity. Locale JSON uses temporary
write followed by os.replace. Corrupt optional locale data is preserved and
defaults are used; corrupt important SQLite state is not overwritten.

## State-root and schema contract

NATIVE_STATE_ROOT_CONTRACT=Every Native-owned mutable file is beneath the
explicit state-dir resolved by RuntimePaths, except intentionally external OS
credential storage. Project roots, filesystem roots, placeholders, and
protected application directories are rejected.

NATIVE_STATE_ESCAPE_FOUND=false
STATE_VERSIONING_STATUS=Native SQLite schema versioned to 13; Settings schema version 1; Locale bounded by explicit values
STATE_MIGRATION_REQUIRED_FOR_CUTOVER=false

Existing migrations are version-gated and reject databases newer than the
supported schema. Empty state initializes safely; repeated startup is safe.

CORRUPT_STATE_POLICY=Preserve important corrupt state and fail/degrade truthfully; ignore malformed optional locale and retain defaults
CORRUPT_STATE_DATA_PRESERVED=true
STATE_WRITE_ATOMICITY_STATUS=PASS for locale JSON; SQLite transactional integrity retained

## Legacy rollback and roll-forward

Legacy and Native use separate state roots in the current architecture.
Legacy state is not imported or overwritten by Native, and Native cannot read
Legacy state automatically.

ROLLBACK_DATA_POLICY=POLICY B — separate preserved state
ROLLBACK_NATIVE_STATE_PRESERVED=true
ROLLBACK_LEGACY_STATE_PRESERVED=true
ROLL_FORWARD_RESTORES_NATIVE_STATE=true

The visibility limitation is explicit: switching to Legacy returns to its own
state, while Native-created state remains intact and reappears when Native is
re-enabled. No bidirectional sync or destructive migration is required.
Because no data is transformed during cutover, a mandatory cutover backup is
not required; normal user backup remains outside this lot.

CUTOVER_BACKUP_REQUIRED=false
CUTOVER_BACKUP_REASON=Native and Legacy state are separate and no cutover transformation occurs

## Validation

EMPTY_STATE_FIRST_RUN=PASS
EMPTY_STATE_SECOND_RUN=PASS
LAZY_INITIALIZATION_CONTRACT=PASS
NORMAL_RESTART=PASS
PERSISTENCE_RESTART=PASS
RECOVERY_RESTART=PASS
LEGACY_ROLLBACK_STARTS=PASS
LEGACY_STATE_PRESERVED=PASS
NATIVE_ROLL_FORWARD_STARTS=PASS
NATIVE_STATE_PRESERVED=PASS

Focused LOT 014D group: 48/48 PASS, 0 FAIL, 0 ERROR. This includes lifecycle,
state-root, corruption/version, restart, background/tray, notification, and
reminder coverage. The real isolated Native and Legacy QML self-checks passed.
The canonical LOT 013 baseline remains 33 total, 32 PASS, 0 FAIL, 0 ERROR,
1 expected skip. Computer Use was exposed and desktop-bound but had zero
native applications, so no visual claim was made.

LIFECYCLE_CUTOVER_STATUS=PASS
PERSISTENCE_CUTOVER_STATUS=PASS
LOT_014D=CLOSED

Remaining work is LOT 014E — Provider parity decision and final cutover gate.
