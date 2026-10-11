# R2 — suppression des rappels locaux

Le DELETE d’un rappel local passe désormais par `PreparedActionRepository` avec le type stable `local_reminders.delete`. Le payload conserve uniquement `reminder_id` (UUID texte); le résumé utilisateur utilise le contenu, avec le fallback `Supprimer ce rappel AURA`.

Avant confirmation, pendant annulation et pour un identifiant absent, aucune ligne SQLite n’est supprimée. Après confirmation, la suppression est exactly-once et `remindersModel` est rafraîchi. Le parcours Google/Calendar et les autres opérations de rappel ne sont pas modifiés.

Validation ciblée : 7 tests R1/R2 verts; tests bridge/QML/Tasks ciblés verts; self-check QML natif OK; aucun réseau, OAuth, SDK Google ou credential n’a été utilisé. La suite native globale a deux échecs préexistants hors périmètre (`test_isolation` état de test et assertion statique historique `taskCount`); aucun échec R2.
