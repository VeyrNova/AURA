# Lot 6B-B1 — fondation OAuth Google native

B1 ajoute les dépendances déclaratives `google-auth`, `google-auth-oauthlib`, `google-api-python-client` et `keyring`, sans installation ni import réseau pendant la validation. `GoogleOAuthConfig` valide uniquement un client Desktop `installed` choisi explicitement ; aucun fichier historique n'est recherché.

Les scopes Calendar/Tasks et leur version sont centralisés. `GoogleCredentialStore` abstrait le stockage ; `FakeGoogleCredentialStore` sert aux tests et `KeyringGoogleCredentialStore` refuse tout fallback plaintext. Les modèles publics exposent uniquement des métadonnées, jamais les tokens. `GoogleAuthProvider` prépare l'état, la validation et le futur flow sans l'exécuter.

Validation : tests B1 et E2E offline, suite native **137/137**, strict Lot 1 **37/37**, self-check QML OK, zéro bytecode. Aucun navigateur, OAuth réel, SDK chargé, réseau Google, credential historique ou token SQLite. Google reste `not_configured`. Prochaine étape : B2 uniquement après autorisation.
