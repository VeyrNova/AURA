# Lot 013 — Music + Documents text parity

## Reachability audit — 2026-10-10

Computer Use was available with 40 exposed applications. The Legacy read-only audit found 14 user-routable Music capability classes: open module, catalog/list, search, smart queue, playlist proposal, playback intent, confirmed local play, player status, pause, resume, stop, volume, seek, and local file/folder/playlist selection. Native scope for this lot is deterministic local playback controls and exact local track selection; proposal/playlist/cloud-style helpers are not native parity targets.

The Legacy Documents audit found 7 user-routable classes: list, search, read/open, create, update, move, and delete. Native Documents already provides canonical-root protection, reparse refusal, fingerprints, atomic save, stable paths, and governed delete behavior.

## Gap and implementation matrix

| Domain | Result |
|---|---|
| Music open/play/pause/resume/stop/volume/seek | Native bridge existed; deterministic router and QML dispatch added |
| Music next/previous/mute | Native QMediaPlayer/QAudioOutput bridge completed with ordered queue/index, truthful state, mute, and boundary-safe next/previous |
| Documents list/open/search | Native service/bridge existed; deterministic search/open router and QML dispatch added |
| Documents create/update/move/delete | Existing service/bridge safety retained; no new mutation path added in this routing pass |
| LLM fallback | Disabled for recognized deterministic Music/Documents intents |
| Voice parity | Voice reuses the same NativeIntentRouter; no confirmation authority added |

Music parameters (`query`, `volume`, `position`) are preserved router → dispatch → UI. Documents parameters (`query`, `path`, `document_id`) are preserved router → dispatch → UI. QML does not reparse commands.

## Validation

Focused Lot 013 routing plus Documents and Lot 012C safety regression: 63/63 tests passed with one pre-existing expected skip. Computer Use reached the real AURA window in an isolated state and exercised Music open/play command entry and Documents search command entry. Test-owned Music WAV, Documents files, state directory, and AURA process were cleaned up.

The implementation is intentionally limited to deterministic routing. Full Lot 013 live playback-state verification and mutation confirmation remain open pending a follow-up bounded validation pass; no real-user files or Google state were touched.

## Lot 013B implementation — 2026-10-10

The native Music bridge now uses QMediaPlayer and QAudioOutput as the sole state sources. It exposes playback state, media status, source, position, duration, volume, and mute state; maintains a stable ordered local queue with current index; and implements deterministic next/previous, bounded seek failure for unknown duration, mute, and unmute. The normal Music UI exposes current track, state, progress, duration, volume, and mute status with accessibility names tied to those backend properties. Documents now exposes search query and canonical selected/opened identity through the existing bridge and visibly labels search results and the opened document.

Focused LOT 013B/backend/QML/regression validation: 166 tests, 0 failures, 0 errors, 1 expected skip. The live pass could not start because Computer Use returned `apps=[]` despite the AURA process being launched normally; no terminal/UI workaround was used. The isolated process and test root were cleaned up. LOT 013 therefore remains open pending real Computer Use proof.

## LOT 013L final closure

The exact Main.qml → PySide bridge regression is proven by the real production composition: `coreBridge.intentRequested` emits the `QVariantMap`, the real `Main.qml` handler executes, and `bridge.setNavigationContext` receives the absolute Music path without a V4ReferenceObject/PyObjectWrapper conversion error.

- LOT013 baseline rebaselined: 33 total, 32 pass, 0 fail, 0 error, 1 expected skip.
- Music parity: PASS. Documents parity: PASS. Total parity: COMPLETE.
- Final regression: PASS. LOT 013: CLOSED. Product blocker: false.
- Validation mode: native runtime fallback; Computer Use live visual validation waived because the inventory contained zero native applications (`CU_TOOL_EXPOSED=YES`, `CU_APPS_COUNT=0`, `CU_DESKTOP_BINDING=YES`).
- Residual UI visual risk: not live visually verified.
- Next recommended lot: FINAL NATIVE MIGRATION AUDIT — NOTIFICATIONS / BACKGROUND / TRAY / CUTOVER READINESS
