# Lot 4B — validation fonctionnelle conversation

## Résultat

Statut : `PARTIAL`.

Les validations automatisées ont réussi le 28 septembre 2026 : 37 tests
stricts du lot 1, 71 tests natifs, self-check QML natif et hygiène bytecode.
Le parcours natif ne construit toujours aucun composant legacy et aucun test
n'a détecté RC4.2, HTTP/SSE, MainWindow ou WebEngine.

## Correction du compositeur Home

Le compositeur commun reste visible sur l'accueil en mode natif. Il était
désactivé par une condition qui excluait systématiquement le mode `native`,
alors que `NativeCoreBridge.conversationAvailable` était déjà vrai. Ce n'était
pas une indisponibilité du runtime.

`Composer.qml` distingue maintenant la capacité de conversation locale de
`interactionReady` : la saisie et l'envoi utilisent
`connected && conversationAvailable` en mode natif. `interactionReady` reste
faux et continue de protéger la voix et les futures interactions agent. Un
envoi appelle le vrai `NativeCoreBridge.sendMessage`, affiche le seul message
utilisateur dans la conversation native et ne fabrique aucune réponse
assistant. L'agent demeure `not_migrated`.

La présentation native annonce `conversation · available` et indique que
l'assistant et la voix ne sont pas migrés.

## Commande native contrôlée

```powershell
.\.venv\Scripts\python.exe -B .\app\main.py --core-mode native --state-dir .\tests\native\_evidence\lot4b-state-a --windowed
```

Le processus a été démarré avec ce state-dir isolé. Il est resté actif mais
aucune fenêtre n'a été exposée au contrôleur Windows disponible dans cette
session (inventaire d'applications vide, aucune fenêtre principale). Le
processus de test a donc été arrêté avant toute saisie ou écriture de message.

Par conséquent, les cas visuels interactifs — saisie QML, Entrée/bouton,
scroll, thèmes sombre/clair, tailles de fenêtre, persistance après fermeture
via UI et clear via UI — restent à vérifier sur un bureau Windows où la fenêtre
Qt est targetable. Ils ne sont pas déclarés réussis ici.

## Contrôles couverts automatiquement

- message vide refusé par le bridge ;
- message utilisateur persistant, sans message assistant ;
- séquence déterministe, isolation de session, clear et reconstruction runtime ;
- chargement QML natif offscreen ;
- `agent` demeure `not_migrated` ;
- le contrat du compositeur Home autorise la saisie native par
  `conversationAvailable`, tout en gardant la voix liée à `interactionReady` ;
- aucun `.pyc` sous `src/aura_native` ou `tests/native`.

## Git

Le workspace n'est pas un dépôt Git ; aucun commit, push ou initialisation n'a
été tenté.
