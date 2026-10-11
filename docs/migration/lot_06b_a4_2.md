# Lot 6B-A4.2 — carte QML pending action

`app/qml/components/PendingActionCard.qml` est intégrée dans `Main.qml`, au-dessus du Composer. Elle est visible uniquement quand `coreBridge.hasPendingAction` est vrai, utilise `pendingActionSummary`, et appelle exclusivement `confirmPendingAction()` ou `cancelPendingAction()`.

Les boutons sont désactivés pendant `confirmed`, les états finaux font disparaître la carte, l'erreur reste générique, et la carte respecte les thèmes sombre/clair, le wrapping et une largeur bornée. La restauration après redémarrage est fournie par A4.1.

Validation structurelle A4.2 : 3/3 ; bridge A4.1/A3.4 : 8/8 ; suite native : 129/129 ; strict lot 1 : 37/37 ; self-check QML natif : OK ; bytecode : 0. Aucune validation visuelle interactive n'a été observée dans cette session : PASS technique, validation visuelle à effectuer.

Harness offline : `tests/native/_evidence/lot6b_a42_visual.py --state-dir tests/native/_evidence/a42-visual --scenario prepared`. Il prépare une action FakeCalendarProvider dans SQLite puis le lancement réel se fait avec `app/main.py --core-mode native`. Le service Computer Use n'a pas exposé de fenêtre Windows dans cette session, donc aucun clic réel n'a pu être observé.

Correction visuelle : boutons ANNULER/CONFIRMER remplacés par des rectangles et MouseArea QML explicites, avec états hover/pressed/disabled et palettes dark/light. Les summaries Calendar/Tasks sont maintenant user-friendly (ex. Créer l’événement « Dentiste »). Tests A4.2 et suite native restent verts ; self-check QML OK. Une nouvelle capture interactive est encore requise avant PASS visuel.
