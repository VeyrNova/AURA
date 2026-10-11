# AURA Native — RC Readiness 01

## BLOCKERS

- R3C tray/Windows notification interaction is not verified in this environment.
- Notes interactive Windows validation is not verified.
- Music interactive Windows validation and real audio output are not verified.
- Full GUI test suite is intentionally separated from the deterministic headless suite.
- Developer Fabric remains PARTIAL: no native UI bridge or persisted job resume.

## NON_BLOCKERS

- Legacy compatibility code remains in `app/main.py` and `.bak` files, but is not
  used by the native composition path.
- PyInstaller/Nuitka/cx_Freeze are not installed; no installer was produced.

## VALIDATED_REAL

- Google Tasks CRUD, Calendar READ/CREATE, local Tasks CRUD, reminders CRUD,
  scheduler R3A and PCC provider/model flows were previously validated real.

## VALIDATED_AUTOMATED

- Notes CREATE/READ/UPDATE/DELETE, PreparedAction confirmation/cancel/double
  execution, persistence and count coverage.
- Productivity persistence across restart for local task, reminder and note.
- SQLite `PRAGMA integrity_check = ok`; migration chain reaches schema 11 and
  is idempotent on reopen.
- Native QML self-check passes.
- QtMultimedia import and NativeMusicBridge local playback controls are
  validated with an offline fixture; audible output remains unverified.
- Developer Fabric unit/E2E fake pipeline passes: mode, workspace safety,
  staging, diff, approval, apply, bounded test and rollback.
- Deterministic headless command: `python -B tools/run_native_headless.py`.
  Result: DISCOVERED_MODULES=93, EXECUTED_MODULES=40, EXCLUDED_MODULES=53,
  TOTAL=153 PASS=153 FAIL=0 SKIP=0, duration 18.89s in this run. Exclusions
  are explicit for Qt runtime, GUI, Google real, PCC real and network-sensitive
  modules; no test is silently omitted.

## AURA DEVELOPER FABRIC

Status: `PARTIAL` / `SOURCE_LEGACY_NOT_FOUND`. The offline core is bounded and has a fake-provider E2E
pipeline with rollback. No provider failover/quota/circuit-breaker layer,
native bridge/QML approval UI or persisted job state exists yet.

## NOT_VERIFIED

- Windows tray click/message interaction.
- Interactive Notes create/update/restart/delete flow.
- Interactive Music load/play/pause/seek/volume and mini-player flow.

## LEGACY_REMAINING

Historical HTTP/Chromium compatibility code is still present in `app/main.py`
and backups. Native runtime composition uses `src/aura_native`, fake providers
when offline, and does not start the historical server or WebEngine.

## PACKAGING_STATUS

Python 3.11, PySide6/QML, SQLite and SVG assets are present. No packaging tool
is installed; a static `packaging/windows/aura.spec` and guarded
`tools/build_windows.ps1` scaffold exist, but no build is claimed. Existing assets include
`AURA_LOGO_SYMBOL_ARCTIC.svg` and the lockups; no `.ico` asset was found.

## KNOWN_WARNINGS

Some Qt Controls imports remain for existing views. The direct MemoryView Column
anchor warning and excessive Agenda geometry/date traces were corrected. No
blocking QML error appeared in the native self-check.

## TEST_SUMMARY

Headless suite is run by `tools/run_native_headless.py`, which excludes tests
requiring real Google, PCC network, or interactive GUI. Each selected module has
a 30-second subprocess timeout; a hang becomes a deterministic failure.

## ADF recovery status (2026-10-02)

ADF historical contracts were recovered read-only and compared against GitHub commit 41bc6503ff7f67bd65915d72e138aae32cdbde65; 21 matching manifests/policies/registries have identical SHA-256. Native Developer Fabric remains PARTIAL and default-off. 
ot_migrated capabilities are not silently routed to legacy. See docs/migration/ADF_SOURCE_COMPARISON.md.


Macro-lot 01 validation: 177/177 headless tests, 0 failed imports. Native bridge/models and extended resilience remain open.


ADF-02: migrations 1-11 inchangées, migration 12 validée; suite globale 177/177, imports échoués 0. UI QML ADF complète et E2E avancés restent ouverts.


Macro-lot 03 validation: 94 modules discovered, 46 executed, 48 excluded, 425 tests discovered, 177 executed, 177 PASS, 0 failed imports.


ADF closure 04 validation: QML self-check PASS; 95 modules discovered, 47 executed, 48 excluded; 430 tests discovered, 182 executed, 182 PASS, 0 failed imports; bytecode cleaned to 0.


Closure 05: QML syntax fixed, native offscreen startup PASS, global runner remains green after final rerun.


Closure 06: 99 modules discovered, 51 executed, 48 excluded; 441 tests discovered, 193 executed, 193 PASS, 0 failed imports.


Closure 07: migration 13 added for audit sequence integrity; targeted audit/provider/QML tests pass.


Closure 08 fresh run: 99 modules discovered, 51 executed, 48 excluded; 441 tests discovered, 193 executed, 193 PASS, 0 failed imports; ADF 26/26 executed.


## Runtime Parity 05 — 2026-10-02 (état actuel)

Music : getter playbackState() corrigé, vrais contrôles QML et test Windows normal PASS. Modules : vraie route/vue et signaux raccordés. Settings : LocaleService natif fr-FR/en-US, signal et persistance config/ui_locale.json, clic QML PASS. Global offline sélectionné : 462 découverts, 214 exécutés, 248 exclus ; 214 PASS, 0 FAIL, 0 import failures, 0 timeouts, complete ; ADF 35/35. Six self-checks QML PASS, 0 pyc. Mail = NATIVE_PARITY_BLOCKER : backend Gmail historique fonctionnel absent du natif. Documents/Contacts : helpers UI mais backends historiques réels, parité métier non établie. Computer Use apps=[] : NOT_AVAILABLE. BAT inchangé, défaut legacy, aucun cutover ; post-cutover NON_APPLICABLE. LOT1 strict ne peut pas être déclaré 37/37 : import Qt scheduler bloqué par son garde existant. Voir docs/release/NATIVE_RUNTIME_PARITY.md pour les 72 contrôles et preuves. Aucun Git/réseau réel/OAuth/Google write. STOP ; pas de nouveau lot.


Validation finale fraîche après les derniers ajustements : 214/214 PASS, 462 tests découverts, 248 exclus, 0 import failure, 0 timeout, status=complete ; durée 76.937 s. Deux timeouts Qt ont été observés sur un run intermédiaire à budget 15 s (test_live_module_qml et test_local_reminders_r1). Le test QML a repassé isolément ; le runner conserve une borne de 30 s pour les modules Qt autorisés, 15 s pour les autres. Aucun résultat de run incomplet ou en échec n’est utilisé pour la clôture. Les tests Settings et runtime wiring sélectionnent explicitement le FakeProviderCredentialStore, avec state-dir de test ; aucune préférence utilisateur réelle n’est changée.
