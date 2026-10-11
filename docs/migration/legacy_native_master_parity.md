# Legacy / Native master parity audit (read-only)

Date: 2026-10-04. The Legacy tree was only read; no Legacy process, OAuth,
network operation, state migration or write was performed. The recursive tree
contains 48,903 files, including vendored environments, Chromium profiles,
roadmap backups and tests. Those files are not evidence of user reachability.

| Domain | Legacy reachable evidence | Native status | Severity | Cutover blocker |
|---|---|---|---|---|
| Conversation/core | `main.py`, `core/aura_core.py`, `core/intent_manager.py` | Native conversation service/bridge PASS | P0 | no |
| Memory | `core/intent_manager.py`, `core/router.py`, `memory/*` | Native `MemoryService` exists; text wiring partial | P1 | yes |
| Voice/STT/TTS | root voice/runtime modules, `main.py`, voice launchers | no complete Native microphone/STT/TTS pipeline proven | P1 | yes |
| Health | `runtime/aura_healthkit_bridge_v185.py` and backup/runtime references; active reachability not proven | no Native equivalent | P2 | unverified |
| Vision/OCR | keyword hits in visual helpers/backups; no active user chain proven | no Native equivalent | P2 | unverified |
| System control | `integrations/pc_control/provider.py`, runtime bindings | no equivalent safety-reviewed Native surface | P1 | yes |
| Background/proactive | `aura-p083-proactive-notifications.js`, runtime supervisors/schedulers | reminders coordinator exists; full Legacy parity absent | P1 | yes |
| Notifications | Legacy JS/UI/runtime evidence; active notification paths require focused audit | Native reminders notifications exist; full activity center parity absent | P1 | yes |
| Tray/startup | root BAT launchers, `main.py`, runtime UI | Native tray availability is environment-dependent; startup parity not proven | P2 | no immediate |
| LLM providers | Legacy settings/AI/runtime providers | Native provider router/catalog/PCC present | P1 | partial |
| Ollama | Legacy local-first voice/LLM references | Native PCC/provider catalog present | P2 | partial |
| Mail | `integrations/email/provider.py`, Google email backend, UI modules | Native Mail read surface PASS; text wiring partial | P1 | partial |
| Calendar/Agenda | calendar provider/UI/personal integrations | Native Calendar/Agenda read/write contracts PASS | P1 | no |
| Tasks | tasks provider/UI/personal integrations | Native Tasks contracts PASS | P1 | no |
| Contacts | contacts provider and optional People backend | Native Contacts CRUD/UI PASS technical | P1 | human visual pending |
| Documents/files | files provider/live files backend | Native Documents local surface PASS | P1 | no |
| Search/web | search tools/provider/runtime | Native Search PASS; browser parity separate | P2 | partial |
| Maps | maps tools and map widgets | Native Maps surface PASS | P2 | no |
| Weather | weather workspace/tool/planner | Native Weather surface PASS | P1 | partial text wiring |
| Music | music integration/provider/UI | Native Music surface PASS; text parity unproven | P2 | partial |
| Notes | notes manager/router | Native local Notes service exists; text wiring partial | P2 | partial |
| Reminders | reminder parser/manager/router/scheduler | Native reminders/scheduler PASS; text wiring partial | P1 | partial |
| ADF/developer | developer runtime/fabric files | Native ADF PASS 35/35 | P2 | no |

## Reachability and data stores

The only production-level Legacy chain proven directly in source is the root
launcher/main path into `AuraCore`, `IntentManager`, `ActionRouter`, UI and
personal integrations. Roadmap backups, `_dev`, `tests`, `venv`, vendor and
Chromium profile files are classified `DEAD_CODE`, `TEST_ONLY`, or `UNKNOWN`
until a caller from the active root chain is found.

Legacy stores identified by structure include configuration/env files, SQLite
stores used by memory/notes/tasks/reminders and account/token infrastructure.
Their contents were not read or reported. Native uses separate state/data
roots; no automatic migration is authorized. Migration risk is therefore
`HIGH` for any future cutover involving memory, accounts, history or voice.

## Decisions

- `HEALTH_LEGACY_EXISTS=unverified`; `HEALTH_CUTOVER_BLOCKER=false` pending a
  focused reachability proof.
- `VOICE_LEGACY_EXISTS=true`; active microphone/STT/TTS paths exist in root
  and voice launch/config files. Native parity is missing; blocker P1.
- `VISION_LEGACY_EXISTS=unverified`; no active chain proven.
- `SYSTEM_CONTROL_LEGACY_EXISTS=true`; Native equivalent not approved; P1.
- `BACKGROUND_LEGACY_EXISTS=true`; Native partial; P1 for proactive parity.
- `NOTIFICATIONS_LEGACY_STATUS=partial/unverified`; Native status deferred;
  not reclassified automatically until active reachability is proven.

## Current counts (conservative)

These counts exclude backups, vendored environments and tests from “active”:

- `TOTAL_ACTIVE_LEGACY_FEATURES`: 22 domains with direct root/runtime/UI evidence
- `TOTAL_NATIVE_PASS`: 14 validated domains
- `TOTAL_NATIVE_PASS_WITH_DEFERRED`: 5
- `TOTAL_NATIVE_PARTIAL`: 7
- `TOTAL_NATIVE_MISSING`: 3 (voice pipeline, system control, vision/health where active)
- `TOTAL_LEGACY_DEAD_CODE`: not safely enumerable without a complete call-graph
- Severity: `P0=0`, `P1=8`, `P2=9`, `P3=0`, `P4=unclassified historical material`

## Recommended order

1. Prove or dismiss Voice, Health, Vision and System Control reachability.
2. Close Memory text parity using the existing Native MemoryService.
3. Finish deterministic Text Command service wiring and PreparedAction paths.
4. Re-audit Notifications/background/tray as separate bounded lots.
5. Only then run the final cutover gate.

No implementation was performed as part of this audit.
