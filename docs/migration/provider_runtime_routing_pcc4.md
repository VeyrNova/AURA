# PCC-4A — Routage runtime des fournisseurs

## Source de vérité

`ProviderSettingsService` est la source de vérité pour `active_provider` et le
modèle sélectionné dans la configuration de ce fournisseur. La sélection est
relue au début de chaque requête. `AURA_PROVIDER`, `AURA_MODEL` et
`AURA_OLLAMA_HOST` restent des overrides développeur explicites, prioritaires
pour le processus uniquement. Ils ne sont jamais écrits dans SQLite. Aucun
provider n'est choisi automatiquement si la sélection est vide.

## Architecture

La composition de production crée un seul `ProviderSettingsService`, un seul
store de credentials, un `RuntimeProviderRouter` et un `AgentService`. Le
bridge Settings conserve la même instance de service que le router. Le router
reconstruit une sélection effective à chaque envoi et retourne une résolution
immuable contenant le provider canonique, le modèle, un adapter interne et les
capacités annoncées. Les IDs restent `openai`, `anthropic`, `gemini`,
`ollama`, `custom_openai`.

Ollama réutilise `OllamaProvider` avec le modèle et l'hôte sélectionnés. Gemini
utilise `GeminiRuntimeProvider` via REST et streaming SSE, avec la clé chargée
depuis `ProviderCredentialStore` dans un adapter limité à la requête. Gemini
n'utilise pas Google Workspace OAuth. Les providers OpenAI, Anthropic et
Custom sont reconnus par le routeur, mais leurs adapters conversationnels ne
sont pas activés par PCC-4A.

## Requêtes, streaming et annulation

Avant de soumettre le worker, AgentService capture un `ProviderRequestSnapshot`
gelé avec provider, modèle, adapter, messages/context et snapshot mémoire. Un
changement dans Settings ne touche que les requêtes suivantes. Aucun adapter
global mutable ne sert de provider courant.

Ollama et Gemini produisent les mêmes `ProviderChunk` internes. AgentService
conserve le filtrage de deltas tardifs et de réponses assistant après STOP. La
clé n'est pas incluse dans les paramètres de conversation, les événements
LocalBus, les messages persistés, QML ou les logs. Les erreurs HTTP/runtime
sont ramenées à des codes et messages publics sûrs. Les adapters Gemini et
Ollama déclarent `supports_tools=False`; les routes AURA existantes restent
exécutées par leur routage local et les résultats d'outils sont ajoutés au
contexte quand une réponse fournisseur est demandée.

## Configuration manquante et absence de fallback

Aucun provider sélectionné renvoie `provider_not_selected` et
« Aucun fournisseur d’IA n’est sélectionné. ». Un provider API sans clé renvoie
`provider_not_configured`; un modèle vide renvoie `model_not_selected`, avec un
message Gemini qui invite à choisir un modèle. Aucun appel provider n'est fait
dans ces cas. Une erreur Gemini reste une erreur Gemini; une erreur Ollama
reste une erreur Ollama.

## Validation hors ligne

Le harness `tests/native/_evidence/pcc4_runtime_provider_routing.py` injecte
exclusivement des adapters fake et accepte `--ollama`, `--gemini`, `--switch`,
`--cancel` ou `--no-fallback`. Il ne lit pas de credentials réels et ne crée
aucune requête réseau. PCC-4A ne valide pas de conversation fournisseur réelle;
cette validation est réservée à PCC-4B.

Les tests vérifient résolution, modèle absent, credential absent, settings
persistants, overrides temporaires, changement à chaud, absence de fallback,
streaming, STOP Gemini, isolation de secret, protocoles Gemini fake, et partage
des instances en composition de production.

## Résultats de validation PCC-4A

- Tests de routage PCC-4A : 22/22 réussis.
- Harness offline : `--ollama`, `--gemini`, `--switch`, `--cancel` et `--no-fallback` réussis; les adapters sont des fakes.
- Suite `tests/native` : 270/270 réussis dans le `.venv` avec Qt offscreen. Pour préserver les profils `_evidence` existants, les trois constantes de profils des tests de bootstrap/isolation/chemins ont été redirigées en mémoire vers un chemin vierge sous `_evidence`; aucune suite n'a modifié les tests existants.
- LOT 1 strict : 37/37 réussis avec les mêmes chemins vierges injectés en mémoire.
- Self-check QML natif : réussi (`returncode=0`) avec store credentials fake et state temporaire.
- Bytecode Python : 0 fichier `.pyc` trouvé sous `src`, `tests` et `tools` après validation.

Incident de validation : une première tentative complète avec `AURA_PCC_FAKE=1` global a fait sélectionner Ollama à un test Agent qui attendait l'absence de provider. Ce test utilisait alors l'adapter de production et a pu tenter un appel loopback vers `127.0.0.1:11434`. Cette tentative a échoué et n'est pas comptée parmi les validations offline réussies. La suite complète a ensuite été relancée sans cet override global; les tests PCC-4A injectent leurs fakes individuellement. Aucun OAuth, SDK Google, credential réel, Gemini réel ou réseau externe n'a été utilisé.

Statut : **PCC-4A = PASS TECHNIQUE / VALIDATION DE CONVERSATION RÉELLE REQUISE**. La validation conversationnelle réelle reste un jalon séparé et n'a pas été lancée.

## Préparation PCC-4B

La validation réelle est préparée dans `pcc4b_real_validation.md`. Le mode
opt-in `AURA_PCC4_DEBUG=1` trace uniquement les identifiants de routage et les
transitions de cycle de vie; aucun contenu utilisateur ou secret. Le harness
réel refuse avant composition sans `--confirm-real-network`. Les tests de cette
préparation restent intégralement offline. Le statut PCC-4 global n'est pas
PASS avant observation humaine des parcours Ollama, Gemini, hot switch et STOP.
