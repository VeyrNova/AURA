# PCC-4B — validation manuelle des conversations réelles

## Statut

**READY FOR MANUAL REAL CONVERSATION VALIDATION**

Cette étape prépare la validation réelle sans l'exécuter. Codex n'a lancé ni
conversation fournisseur réelle, ni OAuth, ni lecture de credential réel. Le
harness est un outil de diagnostic secondaire; la validation finale doit être
faite dans la vraie Conversation AURA.

## Lancement de la vraie AURA

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; $env:AURA_PCC4_DEBUG='1'; .\.venv\Scripts\python.exe -B app\main.py --core-mode native --state-dir "$env:LOCALAPPDATA\AURA-NATIVE"
```

`AURA_PCC4_DEBUG=1` n'imprime que le type d'étape, `request_id`, `provider`,
`model` et un éventuel code d'erreur normalisé. Le prompt, la réponse, les
credentials, l'historique, le contexte mémoire et les URLs ne sont jamais
journalisés.

## Parcours manuel Ollama → Gemini → Ollama

1. Dans **IA & INTÉGRATIONS**, sélectionner Ollama, l'hôte
   `http://127.0.0.1:11434` et le modèle `qwen3:8b`.
2. Dans Conversation, envoyer `Réponds uniquement : AURA OLLAMA OK`.
3. Vérifier streaming visible, une seule réponse assistant, et la trace
   `provider=ollama model=qwen3:8b`.
4. Sélectionner Gemini et choisir manuellement `gemini-3.8-flash`. Cette valeur
   appartient uniquement au scénario de validation; elle n'est pas un défaut
   global.
5. Envoyer `Réponds uniquement : AURA GEMINI OK`. Vérifier une seule réponse,
   la trace Gemini et l'absence de bascule Ollama. Cet appel peut être facturé.
6. Revenir à Ollama, envoyer de nouveau le prompt Ollama et vérifier la trace
   Ollama. Chaque requête commencée conserve son propre snapshot.

Pour prouver un changement pendant le streaming, démarrer une réponse Ollama
longue, sélectionner Gemini avant sa fin, puis envoyer une nouvelle requête.
La première trace doit rester Ollama et la suivante doit être Gemini.

## STOP et absence de résultat tardif

Avec chaque fournisseur, demander manuellement une réponse longue puis cliquer
STOP après le premier fragment. Les traces attendues sont
`PCC4_CANCEL_REQUESTED` puis `PCC4_CANCELLED`. La carte de réponse ne doit plus
recevoir de fragment, aucun message assistant final ne doit être persisté, et
une nouvelle requête doit rester possible. Gemini peut ne pas fermer sa socket
immédiatement; le contrat AURA filtre néanmoins tout delta et résultat final
après annulation.

## Absence de fallback

Cette vérification reste manuelle et ne doit pas arrêter un service depuis un
test automatique. Avec Ollama sélectionné mais inaccessible, AURA doit afficher
`provider_unavailable` ou `network_error` sans appeler Gemini. L'inverse vaut
pour Gemini. Aucun changement de fournisseur ne doit survenir sans action
explicite de l'utilisateur.

## Harness réel protégé

Le fichier `tests/native/_evidence/pcc4_real_conversation_validation.py`
accepte exactement un fournisseur, un state-dir explicite et la garde
`--confirm-real-network`. Il utilise un prompt sentinelle fixe et n'affiche
jamais le texte généré. Gemini annonce `external_paid_api_possible=true` avant
l'appel.

Ces commandes sont fournies pour exécution manuelle et n'ont pas été lancées :

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -B tests\native\_evidence\pcc4_real_conversation_validation.py --ollama --confirm-real-network --state-dir "$env:LOCALAPPDATA\AURA-NATIVE"
```

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -B tests\native\_evidence\pcc4_real_conversation_validation.py --gemini --confirm-real-network --state-dir "$env:LOCALAPPDATA\AURA-NATIVE"
```

Ajouter `--cancel-after-first-delta` à l'une de ces commandes teste STOP. Sans
la garde réseau, le parser refuse avant de composer le runtime ou de lire un
credential.

## Contrôles après chaque réponse

- un message utilisateur et un message assistant exactement;
- provider et modèle enregistrés sur la requête, sans secret;
- même pipeline historique/mémoire pour Ollama et Gemini;
- aucun payload HTTP brut dans Conversation;
- aucune route métier locale transformée en function calling fournisseur;
- aucune réponse brute ou métadonnée de raisonnement injectée dans Conversation.

L'incident PCC-4A reste documenté : un ancien run échoué avec le seed global
`AURA_PCC_FAKE=1` a pu tenter une connexion Ollama locale vers
`127.0.0.1:11434`. Le run final PCC-4A et toutes les validations automatiques
PCC-4B utilisent des fakes et aucun réseau fournisseur réel.

## Diagnostic Gemini streaming avant premier delta

Le client Gemini mappe désormais 400 vers `invalid_response`, 401 vers
`authentication_failed`, 403 vers `permission_denied`, 404 vers
`model_not_found`, 408 vers `timeout`, 429 vers `rate_limited` et 500/502/503/
504 vers `provider_unavailable`. Les timeouts d'ouverture et de lecture sont
distingués; DNS/TLS/reset deviennent `network_error`; un flux SSE malformé
après HTTP 200 devient `invalid_response`.

L'endpoint est
`https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse`.
L'authentification passe par l'en-tête `x-goog-api-key`; la clé n'est jamais
placée dans l'URL, le body, les logs ou les événements.

Le body convertit `assistant` en `model`, conserve `user`, place le system
prompt dans `systemInstruction` et ignore les rôles internes inconnus. Les
messages utilisateur consécutifs, notamment un message annulé sans réponse
assistant, sont fusionnés pour produire un historique Gemini valide. Le
parseur SSE accepte keepalive, événements multiples et fragments JSON
bufferisés.

## Validation automatique de la préparation

- PCC-4B préparation ciblée : 6/6 tests offline réussis.
- Diagnostic Gemini ciblé : 6/6 tests offline réussis.
- PCC-4A + PCC-4B ciblés : 28/28 réussis.
- Suite native complète : 283/283 réussis.
- LOT 1 strict : 37/37 réussis.
- Self-check QML natif : réussi, code retour 0.
- Hygiène bytecode : 0 `.pyc` sous `src`, `app`, `tests`, `tools` et `docs`.
- Diagnostic Gemini PCC-4B : tests de statut HTTP, transport, SSE et historique
  mixte réussis.

Les tests complets ont utilisé des profils vierges injectés en mémoire pour les
tests historiques de résolution de chemins, afin de conserver intacts les
profils `_evidence` déjà présents. Aucun harness réel, GUI interactif, appel
Ollama/Gemini, OAuth ou lecture de clé réelle n'a été exécuté.

## PCC-4B — retry transitoire avant le premier delta

GeminiRuntimeProvider applique au plus trois tentatives pour provider_unavailable, network_error, timeout et rate_limited avant le premier delta texte. Le délai est exponentiel, borné, avec jitter configurable; Retry-After numérique est également borné. L'attente respecte l'annulation. Après le premier delta, aucune nouvelle requête n'est envoyée. Les erreurs 400/401/403/404 restent en tentative unique et aucun fallback vers Ollama/OpenAI n'est effectué. Les traces opt-in PCC4_RETRY_SCHEDULED et PCC4_RETRY_STARTED sont sanitisées.

Validation retry offline : 6/6 tests verts.

## PCC-4B — hermetic test isolation

Les trois échecs précédents provenaient de `test_isolation.IsolationTests.test_importing_launcher_does_not_start_or_change_paths`, `test_runtime_creates_no_threads_or_state` et `test_paths.PathTests.test_resolution_creates_nothing`. Ils pointaient tous vers `tests/native/_evidence/unused-profile-lot5b`, déjà créé par des preuves antérieures. Les tests utilisent désormais des répertoires temporaires uniques (hors `_evidence`), avec un chemin strict non créé pour le validateur LOT 1. Les données `_evidence` n'ont pas été supprimées. Deux exécutions consécutives de `unittest discover -s tests/native -p test_*.py` ont donné 289/289 OK. Les scénarios PCC4 retry restent 6/6 OK. Aucun réseau réel n'est utilisé.
