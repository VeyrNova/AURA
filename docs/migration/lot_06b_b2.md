# Lot 6B-B2 — OAuth Google Desktop

B2 est préparé techniquement mais le login réel n'est pas lancé. `GoogleAuthProvider.connect()` utilise le flow officiel `InstalledAppFlow` par import différé, avec callback loopback `127.0.0.1`, port dynamique et ouverture du navigateur uniquement en mode explicite `--connect`. Les credentials sont sérialisés vers le secure store keyring, jamais SQLite ou plaintext. `disconnect` supprime uniquement le credential local ; aucune révocation distante n'est faite.

Les tests B2 sont entièrement offline avec FakeFlow/FakeStore : 3/3, suite native 140/140, strict lot 1 37/37, zéro bytecode. Les paquets Google/keyring sont déclarés dans `pyproject.toml` mais ne sont pas installés dans `.venv` au moment de cette validation ; aucun navigateur ni OAuth réel n'a donc été exécuté. Google reste `not_configured`. L'installation des dépendances puis le login manuel sont requis avant de déclarer B2 PASS.
