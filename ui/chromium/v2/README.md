# AURA Chromium UI V2 Foundation

Status: **DORMANT / NOT ACTIVE**

This directory is the clean modular foundation for the next AURA Chromium shell. It is intentionally not referenced by the current product launcher or runtime path resolver.

The active production UI remains:

`../v0.7.2.2-rc4.2/`

## Foundation boundaries

- `src/app/` — application composition
- `src/components/` — reusable product surfaces
- `src/runtime/` — canonical UI state and event contracts
- `src/styles/` — design tokens and shell styles
- `migration-manifest.json` — explicit migration/activation contract

Do not wire this directory into `AuraPaths`, `RUN_AURA.bat`, A200 host lifecycle, or the UI launcher until the V2 activation criteria in `docs/AURA_UI_ARCHITECTURE_V2.md` are satisfied.
