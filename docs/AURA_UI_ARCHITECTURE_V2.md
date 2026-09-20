# AURA UI Architecture V2

## Purpose

AURA UI Architecture V2 is a structural refactor of the Chromium product surface. The first goal is not a redesign. The first goal is to make the existing product maintainable without changing the active RC4.2 runtime.

The current production UI remains:

`ui/chromium/v0.7.2.2-rc4.2/`

The V2 foundation lives in:

`ui/chromium/v2/`

V2 is **dormant** until a later, explicit activation gate is approved.

## Non-negotiable migration rules

1. The functional RC4.2 shell remains the active UI until visual and runtime parity are proven.
2. V2 must never be selected implicitly by `AuraPaths`, the launcher, the product bootstrap, or the host lifecycle.
3. Migration is component-by-component, not patch-by-patch.
4. Each migrated surface owns one state contract, one component boundary, and one style boundary.
5. User-facing mode and Developer Mode remain separate concerns.
6. Backend state is canonical. UI animation is derived from canonical state rather than local ad-hoc timers.
7. Historical P0/P1/Rxx identifiers stay in diagnostics and migration evidence, not in normal user-facing labels.
8. Before activation, V2 requires visual regression, interaction, boot, responsive, and accessibility gates.

## Target architecture

```text
AuraApp
├── RuntimeBridge
├── AuraState
├── AuraEventBus
├── Shell
│   ├── TopBar
│   ├── PrimaryNavigation
│   ├── NeuralOrb
│   ├── Conversation
│   ├── Composer
│   ├── ActivityCenter
│   └── ApprovalSurface
├── Workspaces
│   ├── Home
│   ├── Memory
│   ├── Weather
│   ├── Maps
│   ├── Files
│   ├── Productivity
│   ├── Music
│   ├── System
│   └── Developer
└── PersonalResults
```

## Canonical UI states

The foundation defines:

- STARTUP
- IDLE
- LISTENING
- TRANSCRIBING
- THINKING
- SEARCHING
- ANALYZING
- ACTING
- WAITING_APPROVAL
- SPEAKING
- PAUSED
- SUCCESS
- WARNING
- ERROR
- OFFLINE

All state-driven visual behavior must map from this canonical set.

## Normal mode

Normal mode should minimize technical telemetry. The default product surface should emphasize:

- AURA identity and Orb
- current activity in human language
- conversation
- contextual results
- workspaces
- approvals that require user attention

Provider/model/GPU/route/event diagnostics remain available in Developer Mode.

## Developer Mode

Developer Mode may expose:

- provider and model
- route and latency
- token use
- CPU/GPU/VRAM
- STT/TTS/PCM
- event transport
- decision trace
- mission graph
- tool calls
- transaction receipts
- logs

## Migration phases

### Phase 1 — Foundation
- Create the dormant V2 module tree.
- Define state/event contracts and design tokens.
- Add a CI gate proving V2 is not active.
- Keep the production shell untouched.

### Phase 2 — Shell parity
- Reproduce TopBar, navigation, shell geometry, composer, conversation and Orb.
- Establish screenshot references from RC4.2.
- No workspace migration yet.

### Phase 3 — Workspace migration
Migrate one workspace at a time behind explicit feature flags:
1. Home
2. Conversation
3. Activity
4. Memory
5. Weather
6. Maps
7. Files/Productivity
8. Music
9. System
10. Developer

### Phase 4 — Runtime bridge
- Replace ad-hoc DOM patching with a typed event/state boundary.
- Preserve current SSE/host transport semantics.
- Prove approval and Personal Results parity.

### Phase 5 — Visual regression and performance
- Playwright screenshots.
- Keyboard navigation.
- Responsive checks.
- reduced-motion checks.
- lazy loading for non-active workspaces.
- bundle and startup budget.

### Phase 6 — Activation
V2 may become active only when:
- RC4.2 visual parity is accepted,
- boot smoke passes,
- interaction smoke passes,
- approval flows pass,
- Personal Results pass,
- all current workspaces have an explicit migration disposition,
- rollback to RC4.2 remains available.

## Success condition

The migration succeeds when AURA looks and behaves intentionally the same or better, while the implementation no longer depends on a long ordered chain of historical overlay scripts and CSS patches.
