# PCC-5A — Dynamic Model Catalog

PCC-5A foundation is implemented offline. `ProviderModelDescriptor`, `FakeModelCatalogProvider` and `ModelCatalogService` provide canonical provider IDs, safe normalized metadata, explicit refresh, per-provider state, in-memory cache, stale catalog preservation on refresh errors, and generation guards. The service never selects or changes `selected_model` and never stores credentials, headers, or raw payloads.

Current validation: 5/5 focused catalog tests. No network, OAuth, real key, Git, or automatic refresh was used.

Remaining PCC-5A work: Qt/QML bridge and `ProviderModelSelector.qml`, async GUI delivery, production composition wiring, fake visual harness, and full regression validation. Existing reserves remain: Gemini STOP after `PCC4_FIRST_DELTA`, and B4.3 real UI validation.

## PCC-5A UI integration progress

The production composition now creates one side-effect-free `ModelCatalogService` instance. `NativeCoreBridge` exposes safe model lists, explicit asynchronous `refreshProviderModels`, `selectProviderModel`, and refresh/selection signals. Results cross from worker to GUI through the existing queue and GUI-owned QTimer; concurrent refreshes per provider are blocked. `ProviderModelSelector.qml` replaces the provider model field with a custom QML selector and local filtering, bounded popup, and explicit refresh. The native QML self-check passes offline. Focused integration validation: 11/11 tests.

The fake visual harness and the complete PCC-5A regression matrix are still pending; PCC-5A is not declared PASS yet. Existing reserves remain Gemini STOP after first delta and B4.3 real UI validation.

## PCC-5A fake UI validation

Added the offline harness `tests/native/_evidence/pcc5_model_catalog_ui.py` with explicit `--launch`/`--headless`, provider selection, large 60-model Gemini catalog, empty, error and stale-model fixtures. Added stable object names to `ProviderModelSelector.qml` for visual inspection. Large fake catalog headless validation returned 60 models; native QML self-check passed; focused PCC-5A/QML tests passed 8/8. No real network, OAuth, credentials or Git used.

PCC-5A remains technical/interactive-fake validation pending until the visual harness is manually observed. Debts unchanged: Gemini STOP after first delta and B4.3 real UI validation.

## PCC-5A refresh button correction

La cause racine du blocage UI était un `Text` QML avec `MouseArea` inline, sans comportement de bouton premium ni état enabled/loading fiable. Il est remplacé par `AuraButton`, avec `objectName` provider-aware, appel `refreshProviderModels(providerId)`, état `ACTUALISATION...` désactivé pendant le refresh, puis succès/erreur via les signaux du bridge. Le self-check QML et 11 tests ciblés passent offline. Commande fake Gemini : `python -B tests/native/_evidence/pcc5_model_catalog_ui.py --launch --provider gemini --state-dir tests/native/_evidence/pcc5-ui-fake`.

## PCC-5A premium popup polish

Le popup du sélecteur utilise maintenant un fond liquid-glass AURA sombre avec bordure cyan, titre et sous-titre provider, `AuraTextField` pour la recherche, lignes de modèles de 50 px avec hover/pressed/active, badges ACTIF, scrollbar sombre, dimensions bornées et fermeture Escape/clic extérieur. Le self-check QML reste vert. Backend et contrats inchangés.

## PCC-5A large catalog harness fix

La cause racine était que `--large-catalog` n'était utilisé que par le chemin headless du harness; le chemin `--launch` démarrait la composition standard, qui recréait son fake Gemini à 3 modèles. Le flag est maintenant propagé par `AURA_PCC5_LARGE_CATALOG=1` à la composition, qui configure la même instance `FakeModelCatalogProvider` injectée dans l'unique `ModelCatalogService`. Le mode normal reste à 3 modèles, le mode large retourne exactement 60 (`gemini-test-001` à `gemini-test-060`).

## PCC-5A stale model fix

Le flag `--stale-model` est désormais propagé aussi au mode `--launch` via `AURA_PCC5_STALE_MODEL=1`, avant composition. En fake, Gemini reçoit `selected_model=gemini-old-model` tandis que le refresh fournit les trois modèles standard. Le selector calcule l'état stale uniquement après un refresh réussi et si le modèle sélectionné est absent; il affiche `⚠ MODÈLE INDISPONIBLE`, conserve la valeur et ne change pas le provider actif. Le headless stale retourne 3 modèles et le self-check QML reste vert.

## PCC-5A error scenario fix

Le flag `--error` est maintenant propagé au mode `--launch` via `AURA_PCC5_ERROR=1` avant composition. Seul le fake Gemini reçoit une erreur `network_error`; le refresh retourne donc `state=error` et zéro modèle si aucun catalogue précédent n'existe. Le selector affiche `⚠ IMPOSSIBLE D’ACTUALISER LES MODÈLES`, réactive le bouton, conserve le modèle sélectionné et ne déclenche aucun état stale. Le catalogue précédent reste conservé par le service lors d'une erreur.

## PCC-5A closure regression

Validation finale offline : PCC-5 ciblé 12/12; tests/native run #1 295/295 OK; run #2 295/295 OK. Les runs incluent les tests PCC-3, PCC-4, Google Workspace/Calendar/Tasks offline, isolation et harness. Self-check QML OK et 0 `.pyc` sous `src`, `app`, `tests`, `tools`, `docs`. Le validateur LOT 1 exécute 37/37 tests verts; son audit de baseline reste non comparable au workspace historique et est conservé séparément. Aucun réseau, credential réel, OAuth ou auto-refresh n'a été utilisé.

**PCC-5A = PASS TECHNIQUE / INTERACTIVE FAKE UI VALIDATION REQUIRED.** PCC-5B ne commence pas. Dettes conservées : Gemini STOP réel après `PCC4_FIRST_DELTA`; B4.3 REAL UI validation.

## PCC-5B real catalog providers (offline implementation)

Added `OllamaModelCatalogProvider` for `/api/tags` and `GeminiModelCatalogProvider` for `models.list`. Both normalize safe descriptors, preserve authoritative model IDs, map HTTP/transport errors to normalized catalog errors, and never expose credentials. Gemini filters on `generateContent` capability and strips a leading `models/` prefix. Production composition selects these providers only when `AURA_PCC_FAKE` is inactive; creation performs no fetch and no credential lookup. The guarded manual harness is `tests/native/_evidence/pcc5_real_model_catalog.py`; it was not executed with real network consent.

Offline mock validation: 5/5 PCC-5B provider tests plus 13/13 combined catalog/QML tests. PCC-5B status: **PASS TECHNIQUE / REAL MODEL CATALOG VALIDATION REQUIRED**. Existing Gemini STOP-after-first-delta and B4.3 UI debts remain.

## PCC-5B real harness guard correction

La cause du blocage était un `main()` volontairement placeholder qui retournait toujours après affichage du message de garde, même lorsque `--confirm-real-network` était fourni. Il exécute maintenant exactement un fetch du provider demandé après le groupe mutuellement exclusif et la garde CLI. Ollama utilise `AURA_OLLAMA_HOST` ou `http://127.0.0.1:11434`; Gemini utilise le credential store réel côté Python uniquement dans ce flux manuel. La sortie est limitée à provider, succès/statut, nombre de modèles et disponibilité du modèle sélectionné. Le harness réel n'a pas été exécuté par Codex.

Tests parser/dispatch offline : 4/4; tests providers mockés PCC-5B : 5/5. Aucun secret ou argument `--api-key` n'est accepté.

## PCC-5B Ollama UI parity fix

La divergence était dans la composition production : `OllamaModelCatalogProvider` recevait uniquement `ProviderConfig.base_url`. Dans le chemin réel, ce champ pouvait être vide au moment de la construction alors que la carte et le connection tester utilisaient `AURA_OLLAMA_HOST`/le défaut local. Le harness direct recevait explicitement `http://127.0.0.1:11434`, d'où son succès. La composition utilise désormais `base_url`, puis `AURA_OLLAMA_HOST`, puis le défaut local historique avant d'injecter l'unique provider Ollama dans `ModelCatalogService`. Aucun endpoint/provider backend ni UI n'a été refondu.

Parity mock direct/service et composition : tests PCC-5B ciblés 6/6 (15 avec catalogue/UI), self-check QML OK. Aucun réseau réel exécuté.

## PCC-5B initial selected model hydration

Le selector affichait un placeholder lorsque la carte était créée avant que le modèle provider-aware ne soit résolu dans les données QML. `NativeCoreBridge` expose maintenant `getProviderSelectedModel(providerId)`, lu depuis l'unique `ProviderSettingsService`, et `ProviderSettingsCard` l'utilise comme fallback explicite lors de l'initialisation. Cette lecture est strictement read-only : aucun refresh, aucune sélection, aucune écriture SQLite et aucun changement de provider. Le modèle reste affiché avant tout catalogue; l'état stale ne s'active qu'après un refresh réussi.

Tests bridge/QML/provider : 12/12; self-check QML OK.

## PCC-5 final closure

Validation humaine réelle enregistrée : PCC-5A PASS et PCC-5B PASS. Ollama `/api/tags` a retourné 1 modèle réel (`qwen3:8b`), disponible et hydraté dans l'UI. Gemini `models.list` a retourné 44 modèles réels, avec `gemini-3.8-flash` disponible et conservé. L'hydratation initiale `selected_model` et le fallback de base_url Ollama sont validés.

Régression offline finale : tests/native 306/306 OK; tests PCC-5 ciblés 17/17 OK; LOT 1 strict 37/37 tests OK avec audit de baseline historique non comparable; self-check QML OK; bytecode nettoyé à 0 sous `src`, `app`, `tests`, `tools`, `docs`. Aucun auto-refresh, auto-sélection, secret exposé ou credential catalogue lu au boot.

**PCC-5A = PASS. PCC-5B = PASS. PCC-5 = PASS.** PCC-5B est clos. Dettes conservées : Gemini STOP réel après `PCC4_FIRST_DELTA` et B4.3 REAL UI validation.

## B4.3 real UI validation preparation

Le parsing offline exact de `Ajoute demain à 14h un rendez-vous TEST AURA UI CALENDAR pendant 30 minutes.` produit désormais le titre exact, demain, 14:00, 14:30 et 30 minutes. Un correctif mineur retire la ponctuation finale avant extraction de la durée; aucun contrat Google/PCC-5 n'est modifié. Les tests fake démontrent zéro write avant confirmation, exactement un write après confirmation et zéro write après cancel/double-confirm. Régression native : 308/308 OK; self-check QML OK; bytecode 0. Aucun réseau ou credential réel exécuté.

**B4.3 = PASS TECHNIQUE / REAL UI VALIDATION REQUIRED.**
