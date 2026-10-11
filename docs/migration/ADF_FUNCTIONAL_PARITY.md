# ADF functional parity

Status: **PARTIAL / SOURCE_RECOVERED**.

| Function | Native status |
|---|---|
| bounded workspace and default-off mode | implemented and tested |
| plan, stage, diff, approval, apply, rollback | offline primitive implemented |
| preimage hash, atomic transaction, automatic rollback | `not_migrated` |
| provider registry/quota/failover | `not_migrated` |
| coding-agent catalog | `not_migrated` |
| audit chain | in-memory events only |
| native Qt/QML surface | `not_migrated` |

Missing functionality is not invented and must never silently call legacy.

## Macro-lot ADF implementation 01

Implemented native transaction/job/provider/agent core in src/aura_native/developer_fabric/adf.py: preimage checks, proposal digest, symlink/outside-root rejection, atomic replace, backup/rollback, test-before-apply, SQLite jobs/audit, active project, provider failover, 10-agent catalog and fail-closed behavior. Qt bridge/models and full circuit-breaker semantics remain next gaps.

## Macro-lot 02

Migration forward-only 12 ajoutée pour developer_jobs et developer_audit; le service ADF utilise désormais storage.migrations.migrate. Ajouts natifs: bridge QObject, modèles Qt, circuit breaker, détection/sandbox agents et protections d'environnement. La surface QML complète, multi-fichier transactionnel complet, reprise crash et E2E de sécurité restent à finaliser.

## Macro-lot 03

Runner now reports discovered/executed/excluded tests. ADF supports multi-file staged operations with preimage validation and automatic rollback on injected apply failure. Full QML surface, complete restart/crash recovery and verified audit-chain API remain open.

## ADF closure 04

Runtime composition now creates one ADF service, one bridge and four shared models. DeveloperFabricView.qml is integrated on native developer routes and passes the offline QML self-check. Global runner: 182/182 executed tests PASS, 0 failed imports. Backend recovery/audit-chain and full UI workflow remain partial where not proven.

## ADF Closure 05

DeveloperFabricView now invokes real bridge plan/stage/approve/apply actions with state-derived button gates. QML syntax and native offscreen self-check pass. Runtime composition shutdown closes ADF persistence handles.

## ADF Closure 06

AuditLedger.verify_chain, dynamic model reset/insert signals, ProjectPickerService/FakeProjectPicker, provider skip policy, and structured audit/provider/picker tests added. Runner now executes 193 tests.

## ADF Closure 07

Audit sequence and verify_chain were hardened with migration 13; provider skip policy and ADF metrics are now explicit. Dynamic model primitives and structured policy/audit tests remain validated offline.

## ADF Closure 08

Audit sequence verification, provider policy skip reasons, command policy and bounded test output are now covered by explicit tests. Fresh global runner completed with 193/193 PASS and ADF metrics 26/26 executed.
