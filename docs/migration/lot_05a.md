# Lot 5A — socle agent natif

## Statut

`PASS` sous réserve des validations automatisées ci-dessous. Aucun fournisseur
d'inférence, réseau, streaming, clé API ou réponse assistant n'est inclus.

## Audit legacy

La base historique contient un gestionnaire LLM, des registres de providers,
des bridges Core/UI et des chemins HTTP/SSE. Ces composants sont couplés à
AuraCore, MainWindow et à l'ancienne architecture. Seuls les concepts de
requête immuable, états explicites, provider séparé et erreur contrôlée ont été
retenus. Aucun fichier legacy n'est importé, copié ou exécuté.

## Architecture

`NativeCoreBridge → LocalBus → AgentService → AgentRequest / NoProvider →
SQLite`. `AgentService` ne dépend pas de Qt. La migration SQLite v4 ajoute
`agent_requests`, sans secret ni copie des messages conversation. Le provider
`NoProvider` est explicitement indisponible et produit `provider_unavailable`.

États : `idle`, `queued`, `thinking`, `responding`, `completed`, `cancelled`,
`error`, `unavailable`. Lot 5A crée une requête puis la place en
`unavailable`; aucune réponse assistant n'est créée. Une requête active future
peut être annulée par `agent.cancel`; `agent.reset` publie `idle`.

Commandes : `agent.submit`, `agent.cancel`, `agent.status`, `agent.reset`.
Événements : `agent.request_created`, `agent.state_changed`,
`agent.cancelled`, `agent.error`.

## Capabilities

`foundation`, `event_bus`, `storage`, `memory`, `conversation` et `agent` sont
`available`. `agent` signifie orchestrateur local disponible. `inference` est
`not_migrated`; le provider est indisponible. Voice, music, weather, Google et
productivity restent `not_migrated`.

## UI

Le bridge expose `agentState`, `agentAvailable`, `providerAvailable`,
`agentError`, `activeRequestId`, `canCancel`, `submitToAgent` et `cancelAgent`.
La conversation indique un assistant indisponible/provider non configuré sans
spinner ni fausse réponse.
