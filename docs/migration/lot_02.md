# Lot 2 — bus natif et frontière UI/Core

Statut : implémenté localement, sans commit ni publication.

## Contenu

Le noyau `aura_native.core` possède désormais des contrats versionnés avec
payloads copiés et immuables, un `LocalBus` FIFO borné et thread-safe, et un
cycle de fermeture qui refuse les entrées après arrêt. Le bus ne dépend ni de
Qt, ni du réseau, ni d'un service historique.

`aura_native.ui` contient uniquement l'adaptateur Qt : le dispatcher reçoit un
réveil par `Qt.QueuedConnection` et vide le bus sur le thread du QObject. Les
modèles Qt ne sont donc jamais modifiés depuis un worker. `NativeCoreBridge`
traduit les actions conversation/voix en résultats explicites `not_migrated`.

app/main.py accepte --core-mode legacy (rollback explicite) et
`--core-mode native --state-dir <chemin>`. Le mode native n'instancie pas
`AuraCoreBridge`, `MusicQtBridge` ou `WeatherBridge`; il ne connecte pas le
callback HTTP de fermeture musique. Il ne bascule jamais automatiquement vers
legacy en cas d'erreur de configuration.

`Main.qml` choisit un workspace séparé par `Loader`. En natif, les vues legacy
ne sont pas construites; `NativeWorkspaceView.qml` affiche conversation,
mémoire, musique, Google, météo, voix et productivité comme `not_migrated`.

## Validation exécutée

```powershell
& .\.runtime\python311\python.exe -I -S -B .\tests\native\validate_lot1.py --tests-only
$env:PYTHONPATH='src'; & .\.venv\Scripts\python.exe -m unittest discover -s tests\native -p 'test_*.py'
```

Résultats : 37 tests lot 1 réussis, puis 49 tests combinés réussis. Le test Qt
utilise `QT_QPA_PLATFORM=offscreen`, charge `app/main.py --core-mode native
--state-dir tests/native/_evidence/unused-profile --qml-self-check`, et vérifie
qu'un événement publié depuis un thread Python est appliqué par le bridge sur
le thread GUI.

`tools/native_ui_selfcheck.py --state-dir tests/native/_evidence/unused-profile`
a aussi réussi et a retourné `{"ok": true}`.

Le parcours legacy n'a pas été lancé : il démarre volontairement des composants
historiques, ce qui est interdit par les contraintes de ce lot. Sa branche de
composition est conservée et reste le défaut, mais son exécution doit être
validée séparément dans un environnement autorisé.

## Limites et suite

Le bus ne lance pas encore de handlers métier ni de workers : le lot 2 ne
migre aucune fonctionnalité. `submit()` retourne donc explicitement
`not_migrated`. Les tests d'isolation couvrent le chemin natif et les imports
du noyau; ils ne constituent pas une surveillance OS exhaustive. Le lot 3 peut
connecter une première capacité métier au bus sans réintroduire HTTP/SSE.

## Renforcement de revue

La déduplication couvre `command_id` et `correlation_id`, avec un résultat mis
en cache pour une commande répétée. Les handlers optionnels reçoivent un
`CancellationToken` coopératif; une annulation ne force jamais un thread. Le
runtime documente les transitions et recrée un bus propre au redémarrage après
arrêt.

Les tests couvrent la publication concurrente, unsubscribe pendant livraison,
fermeture sans callback tardif, payload profond immuable, métadonnées, doublons
de commande, saturation, annulation coopérative, et la branche legacy inspectée
sans instanciation de service. Les imports réseau, subprocess, WebEngine et
MainWindow sont interdits statiquement dans le package native.

## Clôture et hygiène

Les bytecodes issus des validations du lot ont été retirés sous
`src/aura_native`, `tests/native`, `app/__pycache__/main.cpython-311.pyc` et
les caches stdlib déclenchés par l'ancien essai sans `-B`. Aucun source, asset
ou fichier historique n'a été supprimé. Les caches préexistants de runtime et
`.venv`, ignorés par Git, ne font pas partie de ce nettoyage ciblé.

Le test QML enfant et `tools/native_ui_selfcheck.py` imposent `-B` et
`PYTHONDONTWRITEBYTECODE=1`. Après les 49 tests, les 37 tests lot 1 et le
self-check QML, aucun bytecode généré du périmètre source/test ne subsiste.

La baseline lot 2 est conservée hors Git dans
`tests/native/_evidence/lot2_baseline_20260927.json`; elle couvre les fichiers
de projet hors environnements, caches, runtime et preuves.
