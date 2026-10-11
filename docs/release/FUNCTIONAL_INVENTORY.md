# AURA functional inventory

The native base is functional for the validated Native lots and the bounded Developer Fabric scaffold. Historical ADF functionality has been recovered as contracts and classified in `docs/migration/ADF_FUNCTIONAL_PARITY.md`; provider failover, agent orchestration, persistent jobs, audit chain and the Qt/QML ADF surface remain `not_migrated`.

No legacy Chromium runtime, RC4.2 service, old MainWindow, credential store or old AppData is used by the native Developer Fabric path.


ADF-02 ajoute la persistance de schéma 12, le bridge/modèles Qt et les primitives resilience/sandbox. La fonctionnalité reste explicitement partielle.


Developer Fabric is now reachable through native developer routes with shared composition objects and a QML surface. Advanced recovery/audit gates remain explicitly partial.


## Runtime Parity 05 — 2026-10-02 (état actuel)

Music : getter playbackState() corrigé, vrais contrôles QML et test Windows normal PASS. Modules : vraie route/vue et signaux raccordés. Settings : LocaleService natif fr-FR/en-US, signal et persistance config/ui_locale.json, clic QML PASS. Global offline sélectionné : 462 découverts, 214 exécutés, 248 exclus ; 214 PASS, 0 FAIL, 0 import failures, 0 timeouts, complete ; ADF 35/35. Six self-checks QML PASS, 0 pyc. Mail = NATIVE_PARITY_BLOCKER : backend Gmail historique fonctionnel absent du natif. Documents/Contacts : helpers UI mais backends historiques réels, parité métier non établie. Computer Use apps=[] : NOT_AVAILABLE. BAT inchangé, défaut legacy, aucun cutover ; post-cutover NON_APPLICABLE. LOT1 strict ne peut pas être déclaré 37/37 : import Qt scheduler bloqué par son garde existant. Voir docs/release/NATIVE_RUNTIME_PARITY.md pour les 72 contrôles et preuves. Aucun Git/réseau réel/OAuth/Google write. STOP ; pas de nouveau lot.


Validation finale fraîche après les derniers ajustements : 214/214 PASS, 462 tests découverts, 248 exclus, 0 import failure, 0 timeout, status=complete ; durée 76.937 s. Deux timeouts Qt ont été observés sur un run intermédiaire à budget 15 s (test_live_module_qml et test_local_reminders_r1). Le test QML a repassé isolément ; le runner conserve une borne de 30 s pour les modules Qt autorisés, 15 s pour les autres. Aucun résultat de run incomplet ou en échec n’est utilisé pour la clôture. Les tests Settings et runtime wiring sélectionnent explicitement le FakeProviderCredentialStore, avec state-dir de test ; aucune préférence utilisateur réelle n’est changée.
