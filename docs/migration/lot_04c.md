# Lot 4C — finition UI conversation native

## Statut

`PARTIAL` : les contrôles automatisés sont requis et la validation visuelle
Windows reste à confirmer par l'utilisateur. Le moteur assistant ne fait pas
partie de ce lot.

## Audit et correction

`Main.qml` instancie un seul `Composer` premium global. La conversation native
créait en plus un `TextField` et des boutons Qt de saisie : c'était l'origine
du double composer. `NativeConversationView.qml` est désormais uniquement une
surface d'historique avec un contrôle `EFFACER` QML, discret et adapté aux
thèmes sombre/clair. Le chemin reste : Composer global →
`NativeCoreBridge.sendMessage` → LocalBus → ConversationService → SQLite →
événements → historique.

`Main.qml` calculait déjà `workspaceSafeLeft` depuis la largeur réelle du dock,
mais ne le transmettait pas au workspace natif. Il est maintenant injecté dans
`NativeWorkspaceView`, puis appliqué à la carte conversation avec une marge de
sécurité. Le dock conserve sa position et les messages commencent à sa droite.

Les messages utilisateur restent chronologiques, persistants et sans réponse
assistant simulée. La conversation locale est `available`; l'agent reste
`not_migrated`. Ni SQLite, ni ConversationService, ni le bridge métier ne sont
modifiés.

## Contrats de non-régression

`tests/native/test_native_composer_contract.py` vérifie qu'il n'existe qu'un
composer global, que la vue conversation ne contient pas de saisie concurrente
ni d'appel direct à `sendMessage`, et que ses marges viennent de la safe-zone
calculée dans `Main.qml`. Le test du bridge confirme aussi l'effacement local,
en plus de l'envoi et des capacités conversation/agent.

## Validation automatisée

- 73 tests sous `tests/native` réussis ;
- 37 tests stricts du lot 1 réussis ;
- self-check QML natif offscreen réussi ;
- 10 tests d'isolation native supplémentaires réussis ;
- aucun bytecode sous `src` ou `tests`, et aucun bytecode écrit durant cette
  validation.

## Validation manuelle attendue

```powershell
.\.venv\Scripts\python.exe -B .\app\main.py --core-mode native --state-dir .\tests\native\_evidence\lot4b-state-a --windowed
```

Vérifier la conversation en fenêtre normale et maximisée, les thèmes sombre et
clair, l'absence de chevauchement par le dock, l'envoi via le composer global,
le scroll et l'effacement persistant. Aucun parcours legacy ne doit être
exécuté.
