# Lot 5D — contexte intelligent natif

Le provider natif reçoit désormais un contexte assemblé localement : prompt
système, bloc mémoire, historique récent, puis message utilisateur courant.
`ContextBuilder` ne lit que SQLite native et ne lance aucun transport.

## Sélection mémoire

La sélection est déterministe et limitée à cinq enregistrements. Elle combine
le chevauchement de tokens avec l'importance, la confiance et une préférence
mineure pour le scope actif. Les mémoires `user/default` et `session/<session
active>` sont éligibles. Un scope `project/<project actif>` ne l'est que si le
client fournit explicitement `metadata.project_id`. Les mémoires d'une autre
session et les mémoires sensibles sont exclues.

Le contenu est injecté dans un bloc `<user_memory>` et le prompt système le
déclare comme donnée contextuelle, sans autorité d'instruction.

## Contrat

`ContextSnapshot` garde les identifiants de mémoires, les identifiants des
messages réellement retenus, la version `aura-native-5d-v1` du prompt et son
horodatage. Il est conservé en mémoire par requête pour le diagnostic du
runtime ; il ne duplique ni texte de mémoire ni données utilisateur en base.

L'historique est limité à seize messages, en conservant le message courant une
seule fois à la fin. Le streaming, STOP, annulation et persistance assistant
restent gérés par `AgentService` sans changement de transport.

## Validation attendue

Les tests `test_agent_context.py` couvrent mémoire vide/pertinente/non
pertinente, limite, scopes, sensible, ordre, snapshot, provider et streaming.
Validation automatisée : 99 tests natifs, 37 tests stricts du lot 1 et
self-check QML vert avec `-B` et `PYTHONDONTWRITEBYTECODE=1`. Les tests
d'isolation restent verts et les sources du lot ne font appel ni au legacy,
ni à WebEngine, ni à HTTP/SSE historique. Le shell de validation ne contenait
pas les variables `AURA_PROVIDER`, `AURA_MODEL` et `AURA_OLLAMA_HOST` : aucun
appel Ollama réel n'a donc été effectué et le lot reste `PARTIAL` jusqu'à ce
test fonctionnel local.
