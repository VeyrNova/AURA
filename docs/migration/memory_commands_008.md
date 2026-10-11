# Lot 008 — commandes mémoire natives

## État

Le correctif initial rétablit le contrat SQLite lazy : le scheduler Qt diffère
son premier rescan jusqu'à l'exécution de la boucle Qt. La composition et les
services mémoire ne créent donc plus `aura_native.db` lors d'une composition de
test sans event loop ; la première opération mémoire initialise le schéma.

Les commandes déterministes prouvées et câblées sont :

- `souviens-toi que …`, `mémorise que …`, `retiens que …`, `garde en mémoire que …`
  → `CREATE_MEMORY` → PreparedAction `memory.create` ;
- `affiche ma mémoire`, `liste ma mémoire`, `montre ma mémoire`
  → `LIST_MEMORY` en lecture seule ;
- `cherche dans ma mémoire …` / `recherche dans ma mémoire …`
  → `SEARCH_MEMORY` en lecture seule ;
- `oublie …` / `efface de ta mémoire …`
  → `FORGET_MEMORY` avec résolution d'un identifiant stable exact avant
  création de l'action.

Les écritures passent par `PreparedActionRepository` et
`PendingActionOrchestrator`; aucune mutation n'a lieu avant confirmation et
l'exécution mémoire utilise l'identifiant stable du payload. Les commandes
ambiguës ou absentes sont refusées. Les tests UI réels et le nettoyage de
données `AURA_TEST_008_*` restent à effectuer dans la validation contrôlée.

## Limites

Le parcours Legacy a été audité en lecture seule. Aucun module Legacy n'est
importé ou exécuté et aucune migration de données n'est engagée. Aucun accès
Google, OAuth ou réseau n'est requis par ce lot.

## Lot 008B — closure gate (2026-10-10)

Lazy-init process evidence remains green in the isolated composition test and the focused Memory/History/Conversation/Agent/Text/Voice/PreparedAction/System Control/ADF suites are green. The real AURA window was launched, but Computer Use input failed because the foreground window did not expose a process id to the automation surface; no live Memory object was created and no deletion boundary was reached. Therefore the lot is not closed and no live PASS is claimed.

## Lot 008C — strict/import and Computer Use recovery (2026-10-10)

`validate_lot1.py --tests-only` executed under `-I -S -B`: 53/53 PASS. The earlier full supervisor report was caused by the supervisor's dynamic composition import inventory (`aura_native.notes`); it is not a failure of the strict test contract. Memory command imports remain safe in the strict tests.

The relaunched Native process topology was verified read-only: launcher PID 6000, runtime PID 35972, main window title `AURA Native UI POC 6H FIX2`, HWND 2687176, and `Get-Process.MainWindowHandle` matched PID 35972. Computer Use could display the window but its input adapter still rejected the foreground surface with `foreground window did not report a process id`. No test memory was created; isolated database memory count remained 0. Lot 008 live closure remains open.

## Lot 008D — Computer Use input root-cause isolation (2026-10-10)

The input matrix was executed with harmless test text only: Notepad PASS, PySide6 QWidget/QLineEdit PASS, and a minimal PySide6 QML TextField PASS. The default Native window's frameless/translucent flags produce a layered surface rejected by the Computer Use foreground adapter. A diagnostic `--windowed` launch uses the existing Qt windowed path (non-layered) and accepted Composer input; no production source change was required or applied. No PC READ, network, OAuth, Google, or user-data operation was performed.

`test_memory_commands_008.py`: 2/2 PASS. `test_memory_history_context_001.py`: 22/22 PASS. Strict Lot 1 (`validate_lot1.py --tests-only`, `-I -S -B`): 53/53 PASS. Native self-check returned `ok: true`. The isolated 008D database contains zero memories and no prepared action; the live Memory create/list/search/cancel/forget flow was not completed because the Computer Use session could not be reattached after the diagnostic smoke test. No deletion boundary was reached and no live PASS is claimed.

## Lot 008E — final live closure attempt (2026-10-10)

A fresh AURA Native instance was launched with the existing `--windowed` mode (runtime PID 11080, HWND 1903048). The Computer Use runtime in this session exposed no native-app binding methods after reset (`getApp` unavailable and inventory empty), so the required Composer interaction could not be performed. No Memory object was created, no forget action was prepared, and no destructive confirmation was reached. The automated required groups remain green: Memory commands 2/2, Memory/history 22/22, Conversation/Agent/PreparedAction/PendingAction/System Control/Developer Fabric/Voice targeted suites green, Lot1 strict 53/53. PYC remained 21 before and after, with 0 new. Lot 008 remains open and no cutover is claimed.
