# LOT 014E — Provider parity decision and final Native cutover gate

Status: CLOSED
Validation date: 2026-10-11

Native is now the default runtime. Legacy remains explicitly available
through --core-mode legacy, and explicit --core-mode native remains supported.
Production default Native state resolves to %LOCALAPPDATA%/AURA-NATIVE when no
state-dir is supplied. Tests use isolated state roots.

Mail has Native read-only Gmail integration through the existing
GoogleAuthProvider and secure credential ownership, with truthful
disconnected, missing-scope, unavailable, and API error states. Send/draft
mutations remain governed and are not required for this cutover.

Local Documents and Local Contacts are the exposed Native contracts. Historical
provider-backed Documents and Contacts synchronization/CRUD are explicit P2
scope, not default-runtime regressions.

NATIVE_PROVIDER_AUTH_OWNER=GoogleAuthProvider plus Native Gmail/Google bridges
NATIVE_PROVIDER_LEGACY_AUTH_DEPENDENCY=false

| Feature | Native status | Default ready | P2 gaps |
|---|---|---:|---|
| Diagnostics | PASS | YES | advanced hardware sensors |
| Weather | PASS/PARTIAL | YES | broader provider/live visual scope |
| Maps | PARTIAL | YES | richer map UX/provider scope |
| Mail | PASS read-only Gmail | YES | send/archive/labels |
| Agenda | PASS/PARTIAL | YES | broader external writes |
| Reminders | PASS local | YES | none required post-exit |
| Search | PASS bounded | YES | provider expansion |
| Contacts | PASS local | YES | cloud sync/provider CRUD |
| Memory | PASS | YES | explicit Legacy data migration |
| System Control | PASS bounded | YES | broader historical grammar |
| Voice | PASS bounded | YES | physical microphone/provider gates |
| Music | PASS local playback | YES | cloud/catalog helpers |
| Documents | PASS local filesystem | YES | provider-backed files |
| Notifications | PASS | YES | post-exit delivery not required |
| Background | PASS process-alive | YES | post-exit execution not required |
| Tray | PASS with unavailable fallback | YES | shell-specific visual confirmation |
| Persistence | PASS separate preserved state | YES | no cross-runtime live visibility |

FINAL_P0_COUNT=0
FINAL_P1_COUNT=0
FINAL_P2_COUNT=9

Provider-focused group: 35 tests, 34 PASS, 0 FAIL, 0 ERROR, 1 expected skip.
The directly relevant cutover regression group passed with 1 expected skip.
LOT 014D, LOT 014C, LOT 014B, and LOT 013 all passed. LOT 013 is 33 total,
32 PASS, 0 FAIL, 0 ERROR, 1 expected skip.

Default startup without --core-mode, explicit Native, explicit Legacy rollback,
and default Native roll-forward passed with isolated state. Native and Legacy
QML self-checks passed. No provider credentials, OAuth flow, network mutation,
or real provider data was used.

GITHUB_REPOSITORY_STATE=Not inspected through Git; no Git operation performed
README_STATUS=Missing
LICENSE_STATUS=Missing
GITIGNORE_STATUS=Present
CHANGELOG_STATUS=Missing
VERSIONING_STATUS=No dedicated release version source identified
RELEASE_ASSETS_STATUS=Docs/assets exist; release packaging inventory deferred

LOT 014F must prepare README, LICENSE, CHANGELOG, versioning, repository
metadata, dependency/install instructions, release assets, and publication.
No publication or Git history work was performed here.

CURRENT_DEFAULT_CORE_MODE=native
LEGACY_ROLLBACK_AVAILABLE=true
NATIVE_DEFAULT_CUTOVER_READY=true
NATIVE_MIGRATION_CUTOVER=COMPLETE
LOT_014E=CLOSED
REMAINING_P1_COUNT=0

Next required lot: LOT 014F — GitHub publication + README + release.
