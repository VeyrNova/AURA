# Interactive RC checklist

- Notes: CREATE, UPDATE, restart, DELETE, restart.
- Tray visible, minimize reminder, Windows notification, click restore.
- Tray open and quit.
- Music: load local file, play, pause, seek, volume, mini-player, restart.

These checks require a real Windows desktop. They are not claimed automated
when only the offscreen platform is available.

## Developer Fabric acceptance reserve

ADF source recovery is complete at contract level. Native bridge, provider failover, agent catalog, persistence and audit-chain UI remain 
ot_migrated; interactive acceptance must wait for those phases.


## Runtime Parity 05 — 2026-10-02 (état actuel)

Music : getter playbackState() corrigé, vrais contrôles QML et test Windows normal PASS. Modules : vraie route/vue et signaux raccordés. Settings : LocaleService natif fr-FR/en-US, signal et persistance config/ui_locale.json, clic QML PASS. Global offline sélectionné : 462 découverts, 214 exécutés, 248 exclus ; 214 PASS, 0 FAIL, 0 import failures, 0 timeouts, complete ; ADF 35/35. Six self-checks QML PASS, 0 pyc. Mail = NATIVE_PARITY_BLOCKER : backend Gmail historique fonctionnel absent du natif. Documents/Contacts : helpers UI mais backends historiques réels, parité métier non établie. Computer Use apps=[] : NOT_AVAILABLE. BAT inchangé, défaut legacy, aucun cutover ; post-cutover NON_APPLICABLE. LOT1 strict ne peut pas être déclaré 37/37 : import Qt scheduler bloqué par son garde existant. Voir docs/release/NATIVE_RUNTIME_PARITY.md pour les 72 contrôles et preuves. Aucun Git/réseau réel/OAuth/Google write. STOP ; pas de nouveau lot.


Validation finale fraîche après les derniers ajustements : 214/214 PASS, 462 tests découverts, 248 exclus, 0 import failure, 0 timeout, status=complete ; durée 76.937 s. Deux timeouts Qt ont été observés sur un run intermédiaire à budget 15 s (test_live_module_qml et test_local_reminders_r1). Le test QML a repassé isolément ; le runner conserve une borne de 30 s pour les modules Qt autorisés, 15 s pour les autres. Aucun résultat de run incomplet ou en échec n’est utilisé pour la clôture. Les tests Settings et runtime wiring sélectionnent explicitement le FakeProviderCredentialStore, avec state-dir de test ; aucune préférence utilisateur réelle n’est changée.
