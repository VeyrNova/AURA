# ADF Chromium -> Native audit

## Historical source recovery (2026-10-02)

Read-only comparison covered `C:\AURA GPT version` and GitHub `VeyrNova/AURA@41bc6503ff7f67bd65915d72e138aae32cdbde65`. The 21 ADF-A..H manifests, policies, provider/agent registries and bridge inventories found in both locations have identical SHA-256 values. GitHub is the canonical contract source; the local installation is corroborating evidence only. No historical runtime was executed or changed.

The current workspace contains only the native scaffold. Recovered Chromium implementation is not copied wholesale: native migration is staged behind the default-off Developer Fabric guard and retains workspace bounds, approval, staging, tests-before-apply, backup, atomic write, rollback and audit rules.

## Native classification

| Element | Status |
|---|---|
| DeveloperMode | REUSE, default off |
| WorkspaceBoundary | REUSE, policy hardening pending |
| plan/stage/diff/approval/apply/rollback | native bounded primitive |
| provider failover/quota/circuit breaker | `not_migrated` |
| agent catalog and orchestration | `not_migrated` |
| persisted jobs/resume | `not_migrated` |
| Qt/QML bridge | `not_migrated` |

Status is **PARTIAL / SOURCE_RECOVERED**, not complete parity. Legacy `.env`, credentials, audit/transaction ledgers, backups, generated Chromium bundles and local state are excluded from migration.


Macro-lot 01 adds a native offline ADF service without HTTP/Chromium. The historical source remains contract reference only.


ADF closure 04 scan: zero QtWebEngine/QWebEngineView/fetch/XMLHttpRequest/localhost/API-action references in the native ADF path.
