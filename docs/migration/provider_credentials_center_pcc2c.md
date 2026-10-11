# Provider Credentials Center — PCC-2C

PCC-2C ajoute l’import local du client OAuth Google sans découverte historique.
Le fichier est validé avant écriture, puis remplacé atomiquement sous le dossier
de credentials injecté (fake launcher) ou `%LOCALAPPDATA%/AURA/credentials`.
Les erreurs sont normalisées et aucun secret n’est exposé au bridge ou à QML.

Validation offline : 187 tests native réussis, self-check QML réussi, aucun
OAuth, réseau, SDK Google ou credential réel utilisé. Le launcher visuel dédié
est `tests/native/_evidence/provider_credentials_center_ui.py` et reste à
lancer manuellement pour la validation visuelle.
