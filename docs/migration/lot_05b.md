# Lot 5B — robustesse agent offline

`FakeProvider` fournit un provider entièrement déterministe et sans transport
pour les validations natives. Sans `AURA_PROVIDER=ollama`, la composition
conserve `NoProvider`; avec une configuration native complète, elle compose
`OllamaProvider` sans probe réseau. Un provider de test est injecté
explicitement.

Le flux validé est `user → conversation.send → agent.submit → FakeProvider →
assistant`. La réponse assistant est persistée avec son rôle, sans réseau. Les
soumissions agent sont idempotentes par session et `user_message_id`; une
annulation terminale empêche la création d'un assistant tardif. Les requêtes
actives interrompues sont marquées `recovered_interrupted` lors de la première
opération agent après reconstruction du runtime.

`providerAvailable` est désormais une propriété dynamique du bridge mise à
jour par les événements agent. La vue QML conserve son contrat d'état et ne
fait aucune découverte de provider.

Validation : 83 tests natifs avec `-B`, 37 tests stricts du lot 1, self-check
QML natif et contrôle bytecode. `ready_for_real_provider_test = true` : la
seule étape restante est la configuration native puis un unique test réel.
