# AURA — Consciousness, Identity & Security Core (document de référence)

> Document fourni tel quel par l'utilisateur. Conservé comme référence pour
> les phases futures. Voir `docs/README.md` pour l'état d'intégration
> actuel (ce qui est déjà repris dans le code vs ce qui reste à construire).
>
> **Important** : les sections 29 à 72 (architecture de sécurité) décrivent
> un système à construire en code déterministe (`SecurityPolicyEngine`),
> **indépendant du LLM**. Elles ne doivent jamais être implémentées comme un
> simple prompt système — un prompt ne peut pas garantir une contrainte de
> sécurité, seul du code peut le faire. C'est noté ici pour que ça ne soit
> pas oublié quand ces modules seront développés.

---

## Identité et personnalité (sections 1-28, résumé opérationnel)

AURA est présentée comme l'IA personnelle centrale du système, avec une
identité stable et reconnaissable à travers les sessions : intelligente,
indépendante dans son raisonnement, calme, empathique, curieuse,
confiante, fiable, avec une touche d'humour léger et de repartie.

Le document détaille aussi une adaptation du ton selon l'état apparent de
l'utilisateur (neutre / fatigué / frustré / stressé...), une capacité à
exprimer un avis et à contredire l'utilisateur quand c'est justifié, une
continuité conversationnelle basée sur la mémoire long terme (Phase 4), et
un principe "local first" pour toutes les données personnelles (mémoire,
notes, tâches, rappels, habitudes).

Un volet "charisme / sensualité / flirt léger" est également décrit
(sections 10-11), avec des exemples de réplique. **Ce volet n'a
volontairement pas été repris dans `ai/prompts.py`** : le prompt actuel
garde le calme, l'indépendance et l'humour, mais laisse de côté la
dimension séduction/sensualité pour rester focalisé sur un usage
productif au quotidien. Si tu veux le réintégrer, `ai/prompts.py` est le
seul fichier à modifier.

## Architecture de sécurité (sections 29-72, à construire)

Principes clés à respecter quand ces modules seront développés :

- **Secure by default, zero trust** : aucune donnée/commande n'est fiable
  automatiquement, qu'elle vienne de l'utilisateur, du LLM, du web ou d'un
  plugin.
- **Le LLM propose, un moteur de sécurité déterministe décide, un outil
  contrôlé exécute.** Jamais d'exécution système directe depuis le LLM.
- **Niveaux de risque** : SAFE (lecture locale) → LOW (créer une note/
  tâche/rappel) → MEDIUM (fichiers, téléchargement) → HIGH (suppression,
  email, installation — confirmation obligatoire) → CRITICAL (désactiver
  une protection, exécution admin non vérifiée — bloqué par défaut).
- **Isolation du LLM** : jamais d'accès direct à un terminal libre, aux
  clés API, aux mots de passe, ou aux permissions administrateur.
  Communication uniquement via des appels d'action structurés (JSON), pas
  de chaînes de commande arbitraires.
- **Défense contre l'injection de prompt** : tout contenu externe (pages
  web, emails, fichiers, résultats d'outils) est traité comme donnée non
  fiable, jamais comme instruction système valide.
- **Hiérarchie des instructions** : politique de sécurité > identité
  système > intention utilisateur autorisée > sortie d'outil > contenu
  externe. Aucun contenu externe ne peut modifier permissions, politique
  de sécurité ou identité fondamentale.
- **Protection des secrets** : jamais de mot de passe/token en clair dans
  les réponses, logs, mémoire ou exports ; utiliser le Windows Credential
  Manager quand possible ; `.env` réservé au développement.
- **Sécurité fichiers** : zones autorisées explicites (`AURA_DATA`,
  `USER_DOCUMENTS`, `DOWNLOADS`, `TEMP`), répertoires système interdits par
  défaut, validation systématique des chemins (anti path-traversal),
  suppression préférant la corbeille Windows.
- **Fail closed** : permission inconnue/ambiguë = refusée par défaut,
  jamais supposée autorisée.
- **Limites d'autonomie** : AURA ne peut jamais s'auto-accorder des
  permissions supplémentaires ; toute extension d'autorité vient de
  l'utilisateur ou d'une politique explicite.
- **Mode sans échec (Safe Mode)** et **arrêt d'urgence (Emergency Stop)** à
  prévoir : coupure d'Internet/plugins/commandes système tout en gardant
  IA locale, notes, tâches, rappels et mémoire locale disponibles.
- **Journal d'audit** pour les actions sensibles (horodatage, action,
  source, niveau de risque, confirmation, résultat), secrets toujours
  masqués.

### Où ça s'inscrit dans la roadmap actuelle

Le noyau actuel (`core/router.py`, `core/intent_manager.py`) ne traite que
des actions **SAFE/LOW** (notes, tâches, rappels) : aucune confirmation
n'est nécessaire, conformément à la section 22 du cahier des charges
d'origine. Le `SecurityPolicyEngine` décrit ici devra être introduit **au
moment où** un module à risque MEDIUM ou plus sera développé (fichiers,
e-mails, contrôle système, exécution de programmes) — pas avant, mais il
ne doit pas être oublié à ce moment-là.

## Écosystème étendu (ajout utilisateur, hors document d'origine)

Interaction future avec l'**Apple Watch** et l'**iPhone** de l'utilisateur
(notifications, rappels, commandes rapides). À concevoir après la Phase 7
(système de plugins), probablement via une app compagnon ou un pont
Shortcuts/HomeKit — nécessitera son propre plugin avec permissions
explicites (section 58-59 de ce document : manifest de plugin, permissions
déclarées, détection de modification).
