# Lot 009 — commandes PC en lecture seule

Les trois commandes déterministes natives sont désormais câblées :

- `PC_LIST_WINDOWS` : fenêtres ouvertes ;
- `PC_LIST_PROCESSES` : processus en cours ;
- `PC_GET_FOREGROUND_WINDOW` : fenêtre au premier plan.

Le routeur français reste explicite et ne détourne pas les recherches Web,
les questions générales sur Windows ou l’ouverture de modules. Le dispatch
appelle directement `SystemControlService`; aucun PreparedAction, shell ou
mutation n’est utilisé. Les résultats sont structurés, bornés à 50 éléments,
et masquent HWND/PID dans la présentation utilisateur.

La grammaire historique observée dans `C:\AURA GPT version` était présente
dans le dispatcher PC legacy, mais ces lectures n’étaient pas une preuve de
parité Text Command complète. Lot 009 les classe comme amélioration Native
produit sûre.

Validation automatisée : `test_pc_read_009.py` 5/5, System Control 24/24,
Lot 1 strict 53/53. Computer Use était indisponible (`apps=[]`), donc aucune
validation live ni fenêtre de test n’a été créée. Le mode par défaut AURA et
les commandes de mutation restent inchangés.
