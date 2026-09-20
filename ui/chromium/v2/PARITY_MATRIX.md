# AURA UI V2 — Shell Parity Matrix

The V2 shell is still dormant. This matrix maps the visible RC4.2 shell into clean component ownership.

| RC4.2 surface | V2 owner | Phase 2 status |
| --- | --- | --- |
| `.topbar` | `src/components/top-bar.js` | scaffolded |
| P0702 left rail | `src/components/primary-nav.js` | scaffolded |
| Neural core / Orb | `src/components/neural-orb.js` | scaffolded |
| `.telemetry` / SYSTEM LIVE | `src/components/telemetry-panel.js` | scaffolded |
| `#conversation` | `src/components/conversation-surface.js` | scaffolded |
| `#composer` | `src/components/composer.js` | scaffolded |
| workspace shell geometry | `src/components/aura-shell.js` | scaffolded |
| runtime state projection | `src/runtime/aura-state.js` | scaffolded |
| host/SSE transport | future RuntimeBridge | not migrated |
| real messages/actions | future conversation contract | not migrated |
| approvals | future ApprovalSurface | not migrated |
| Personal Results | future PersonalResults | not migrated |

## Phase 2 acceptance

This phase proves structure and shell geometry only. It does not claim functional parity.

Before the V2 runtime can be activated, later gates must still prove:
- real runtime transport parity,
- conversation rendering parity,
- approvals,
- Personal Results coexistence,
- workspace behavior,
- screenshot regression,
- keyboard/accessibility behavior,
- performance budgets,
- rollback to RC4.2.
