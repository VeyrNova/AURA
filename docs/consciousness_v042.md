# AURA v0.4.2 — Consciousness Foundation

Cette version introduit une couche de conscience **fonctionnelle simulee** et non une revendication de conscience biologique.

```text
AuraIdentity
+ PersonalityEngine
+ SelfModel
+ current mode
+ current local time
+ session history
        |
        v
ConsciousnessContextBuilder
        |
        v
fresh system prompt for each LLM call
```

Le `conversation_history` ne contient plus de system prompt permanent. Un nouveau contexte systeme est construit avant chaque appel au LLM.

La securite reste hors du LLM :

```text
LLM -> proposition / conversation
ActionRouter -> SecurityPolicyEngine -> module autorise
```

La personnalite est actuellement stable et bornee. L'apprentissage persistant arrivera avec la memoire/continuite en v0.6.
