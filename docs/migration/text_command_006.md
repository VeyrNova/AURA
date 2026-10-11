# Text Command 006 — contrats locaux et temps français

Lot limité aux commandes Notes/Tasks/Reminders locales, au routage des recherches de notes et aux paramètres déjà portés par les intentions. Aucun changement Voice, Memory, PC READ, Google, Calendar, Gmail ou hygiène `.pyc`.

Le parsing temporel est centralisé dans `src/aura_native/reminders/temporal_fr.py`. Il retourne un résultat typé (`OK`, `NEEDS_TIME`, `INVALID_DATE`, `INVALID_PAST_TIME`, `INVALID_DURATION`, `UNSUPPORTED_RECURRENCE`) et reçoit une horloge injectable. Les calculs sont faits en `Europe/Paris`, avec des dates conscientes et les règles DST existantes.

Contrats pris en charge : dates absolues françaises et numériques, heure seule (aujourd'hui si future, sinon demain), offsets minutes/heures/jours/semaines, aujourd'hui/demain/après-demain à heure explicite, jours de la semaine et parties de journée. Les heures par défaut produit sont matin 08:00, après-midi 15:00 et soir 19:00. Une partie de journée passée est rejetée ; une date passée est rejetée. Les récurrences restent `UNSUPPORTED_RECURRENCE` car le modèle local ne les représente pas.

La commande `cherche dans mes notes ...` (ainsi que `trouve ma note ...` et `recherche une note ...`) produit `SEARCH_NOTE`, exécuté en lecture seule par `LocalIntentProduct` via le service local. Elle ne passe plus par `WEB_SEARCH`. `cherche sur internet ...` reste `WEB_SEARCH`.

Les rappels valides créent seulement une PreparedAction ; le trigger canonique est résolu au moment de la préparation et le résumé affiche une date lisible. La confirmation reste explicite et l'exécution n'interprète jamais à nouveau la phrase relative.

Tests automatisés ajoutés : `tests/native/test_text_command_006.py` (7 tests, 49 avec la régression Local Text Command 004). Les tests ciblés passent, ainsi que Lot 1 strict 53/53 et le self-check QML headless. La validation Windows a préparé et confirmé deux rappels `AURA_TEST_*` et annulé un troisième ; les cartes ont affiché les dates résolues et aucune mutation n'a eu lieu avant confirmation. Les scénarios invalid-date, needs-time, recherche locale et chat normal n'ont pas encore été validés dans cette session. Les deux rappels confirmés doivent être supprimés via l'UI après confirmation d'action au moment de la suppression ; aucune suppression hors préfixe de test ne sera faite.

## Clôture 006B — validation native live (2026-10-10)

- Matrice temporelle locale : 11 tests / 40+ cas, PASS. Absolu, relatif, jour de semaine, partie de journée, protection date invalide/passée et immutabilité de l'heure préparée sont validés. Récurrence reste `UNSUPPORTED_RECURRENCE`.
- Validation live : `LIVE_REMINDER_RELATIVE_TIME=PASS`, `LIVE_REMINDER_TOMORROW=PASS`, `LIVE_REMINDER_CANCEL_ZERO_MUTATION=PASS`, `LIVE_REMINDER_INVALID_DATE=PASS`, `LIVE_REMINDER_NEEDS_TIME=PASS`, `LIVE_LOCAL_NOTE_SEARCH=PASS`.
- Nettoyage Computer Use strictement ciblé : les deux rappels autorisés et la note autorisée ont été confirmés dans l'UI puis vérifiés absents de SQLite par leurs IDs exacts. Aucun autre élément n'a été supprimé. `LIVE_TEST_DATA_CLEANUP=PASS`.
- Vérifications négatives : `AURA_TEST_006_INVALID`, `AURA_TEST_006_NEEDS_TIME` et le rappel annulé ne sont pas présents.
- Chat : `TEXT_CHAT_ROUTING_LIVE=PASS`, `TEXT_CHAT_PREPARED_ACTION_LEAK=ABSENT`, `TEXT_CHAT_PROVIDER_RESPONSE_LIVE=BLOCKED_PROVIDER_UNAVAILABLE` (aucun fournisseur Gemini disponible pendant l'observation ; aucune modification de code Chat).
- Statut : `TEXT_COMMAND_006=PASS_NATIVE_LIVE`, `REMINDER_NATURAL_TIME_PARITY=PASS_NATIVE_SCOPED`, `REMINDER_NATURAL_TIME_CUTOVER_BLOCKER=false`. Le blocage global `TEXT_COMMAND_CUTOVER_BLOCKER=true` reste dû aux écarts Voice local, Memory commands, PC READ grammar et autres écarts prouvés. Lot 007 non commencé.
- Régressions : tests ciblés 53/53 PASS, Lot 1 strict 53/53 PASS, self-check QML exit 0/PASS, exécutions contrôlées avec `-B` et `PYTHONDONTWRITEBYTECODE=1` (0 nouveau `.pyc`).

Le lot ne clôt pas le blocage global Text Command : Memory, PC READ et plusieurs routes déterministes restent hors périmètre. Aucun cutover n'est proposé.
