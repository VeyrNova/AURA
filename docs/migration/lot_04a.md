# Lot 4A — conversation native locale

La conversation native est persistée dans `paths.data_dir / aura_native.db`.
La migration SQLite v3 est idempotente. Elle conserve les tables v2, ajoute
`session_id` à `conversations`, crée `conversation_messages` avec `sequence`
et `status`, puis copie les anciens messages v2 sans les supprimer. Aucune base
ou donnée legacy externe n'est lue.

Le flux est `NativeConversationView.qml → NativeCoreBridge → LocalBus →
ConversationService → ConversationRepository → SQLite`. Les commandes prises
en charge sont `conversation.new`, `conversation.send`, `conversation.list`,
`conversation.get` et `conversation.clear`. Les événements émis sont
`conversation.created`, `conversation.message_created`,
`conversation.loaded`, `conversation.cleared` et `conversation.updated`.

Seuls les messages utilisateur sont enregistrés. Le service ne génère aucune
réponse assistant : la capacité `conversation` est `available` et `agent`
reste `not_migrated`. Le bridge expose `messages`, `messageCount`,
`conversationStatus` et `conversationAvailable`; `sendMessage` refuse un texte
vide et retourne vrai quand la commande locale est acceptée.

`NativeWorkspaceView.qml` construit `NativeConversationView.qml` pour les
workspaces `talk` et `conversation`; aucune vue `ConversationView.qml` legacy
ne participe au parcours natif.

Validation exécutée avec bytecode désactivé : 66 tests natifs, 37 tests stricts
lot 1, puis self-check QML native offscreen, tous verts. Aucun `.pyc` sous
`src/aura_native` ou `tests/native` après validation. Aucun réseau, LLM,
processus externe, AppData historique, RC4.2 ou fallback legacy n'a été ajouté.

La liste, lecture et suppression sont isolées par `session_id`; une
reconstruction de runtime sur la même base restaure le dernier historique de la
session par `refreshConversation()`. Les messages sont ordonnés par `sequence`
et seuls des messages `user` actifs sont acceptés.
