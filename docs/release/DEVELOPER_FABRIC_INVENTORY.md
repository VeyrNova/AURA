# AURA Developer Fabric inventory

Status: **SOURCE_RECOVERED / NATIVE PARTIAL** (2026-10-02).

Historical ADF-A..H contracts are present in both `C:\AURA GPT version` and the requested GitHub commit; all 21 matching JSON contracts have equal SHA-256. Canonical source is the GitHub commit. No credentials, `.env`, ledgers, backups, generated bundles or local state are included.

| Native component | Status | Evidence |
|---|---|---|
| DeveloperMode | active, default off | `src/aura_native/developer_fabric/fabric.py` |
| bounded plan/stage/diff/apply/rollback | active offline primitive | 6 native tests |
| provider registry/quota/failover | not_migrated | ADF-C historical contract recovered |
| coding-agent catalog | not_migrated | ADF-D, 10 agent identities |
| transaction policy hardening | partial | ADF-F policy recovered |
| audit chain | not_migrated | ADF-G policy recovered |
| Qt/QML ADF bridge | not_migrated | ADF-H historical Chromium source |

No historical module is imported by the native scaffold. Features not yet ported are explicit `not_migrated`, never a silent legacy fallback.


Macro-lot 01: native ADF service and 4 focused tests added; global headless runner remains green.


Macro-lot 02: migration 12, bridge/models Qt, resilience et sandbox agent baseline ajoutés. Statut toujours PARTIAL tant que la surface QML et les E2E complets ne sont pas validés.


Macro-lot 03: multi-file operation baseline and auto-rollback added; runner test metrics corrected. ADF remains PARTIAL.


ADF closure 04: runtime composition and native QML surface added; offscreen self-check PASS; global 182/182 PASS.


Closure 05: actionable QML workflow controls and ADF shutdown cleanup added; offscreen self-check PASS.


Closure 06: dynamic model primitives, picker validation, provider skip reasons and audit verification baseline added; global 193/193 PASS.


Closure 07: audit sequence/hash verification and explicit ADF runner metrics added.


Closure 08: command policy and bounded output added; fresh global validation 193/193 PASS.
