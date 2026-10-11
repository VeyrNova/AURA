# Macro-lot Notes et nettoyage QML

Notes locales utilisent la migration SQLite 11 (`local_notes`),
`LocalNotesRepository`, `LocalNotesService` et `LocalNotesModel`. CREATE,
UPDATE et DELETE passent par `PreparedAction` et `PendingActionOrchestrator`;
aucune mutation UPDATE/DELETE n'est effectuée avant confirmation.

UPDATE est exposé par `NativeCoreBridge.updateNote(note_id, title, content)`.
Le résumé est humain et le payload conserve l'identifiant technique.

Le warning d'ancrage de `MemoryView` a été corrigé en retirant les anchors du
Text enfant de la Column et en utilisant width/height/verticalAlignment.
Les traces Agenda de géométrie et de dates de diagnostic ont été retirées;
les traces de lecture/reconstruction utiles restent limitées.

Validation ciblée Notes UPDATE : PASS. Self-check QML natif : PASS.
Validation interactive Notes : NOT VERIFIED dans cet environnement sans surface
GUI Windows exploitable. Aucun réseau, OAuth, SDK Google ou credential n'a été
utilisé.
