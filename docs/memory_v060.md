# Memory & Continuity Architecture — AURA v0.6

## Flux

```text
User message
   │
   ├─ IntentManager ──> commandes mémoire déterministes ──> SecurityPolicyEngine
   │                                                       │
   │                                                       └─> MemoryManager / SQLite
   │
   └─ conversation générale
         │
         ├─ MemoryManager.retrieve_for_context()
         │     ├─ recherche locale par tokens / pertinence
         │     ├─ limite de contexte
         │     └─ filtre sensible
         │
         ├─ ContinuityEngine (métadonnées de session uniquement)
         ├─ RelationshipModel (familiarité fonctionnelle bornée)
         │
         └─ ConsciousnessContextBuilder ──> Ollama local
```

## Principes

- local-first ;
- pas d'embeddings cloud ;
- pas de transcript long terme dans `conversation_sessions` ;
- provenance conservée par souvenir ;
- suppression réelle des souvenirs sur demande ;
- fail-closed pour les actions inconnues ;
- mémoire sensible non injectée automatiquement par défaut ;
- mode privé de session ;
- le `RelationshipModel` n'est qu'un signal UX et ne doit jamais être présenté comme une émotion humaine réelle.

## Schéma mémoire v0.6

La table historique `memories` est migrée non destructivement avec :

- `updated_at` ;
- `normalized_content` ;
- `status` ;
- `access_count` ;
- `last_used_context_at` ;
- `is_sensitive` ;
- `tags`.

La table `conversation_sessions` ne contient que : timestamps, compteurs de messages et indicateur de mode privé.
