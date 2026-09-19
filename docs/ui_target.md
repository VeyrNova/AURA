# Interface cible d'AURA — Phase 5 (référence visuelle)

Ce document décrit l'interface finale visée pour AURA, à partir d'un mockup
fourni par l'utilisateur. Ce n'est **pas** l'interface actuelle (v0.1-v0.4,
qui est une base fonctionnelle minimale volontairement simple) — c'est
l'objectif pour la Phase 5 ("Interface futuriste").

## Structure générale (3 colonnes)

**Bandeau supérieur**
- Logo/nom AURA + sous-titre "Adaptive Unified Reasoning Architecture"
- Horloge + date en temps réel, centrées
- Indicateurs de statut alignés à droite : `LOCAL AI ONLINE` (+ nom du
  modèle), `VOICE READY` (+ statut micro), `INTERNET CONNECTÉ` (+ débit),
  `SECURITY CORE ACTIVE` (+ niveau de protection), `MODE: NORMAL`
- Boutons fenêtre standards (réduire / agrandir / fermer)

**Colonne gauche — Conversation**
- Titre "CONVERSATION" + icône de réglages
- Historique de chat avec avatar utilisateur / avatar AURA, horodatage par
  message
- Champ de saisie en bas avec bouton "+" (pièce jointe / action) et bouton
  micro

**Zone centrale — Orb & statut système**
- Orb AURA au centre, grand, avec anneaux lumineux concentriques
  (reprend le principe déjà implémenté dans `ui/orb_widget.py`, mais
  largement enrichi visuellement)
- Indicateurs technique autour de l'orb : température du "noyau",
  fenêtre de contexte (tokens), moteur de raisonnement (statut), statut
  mémoire
- Nom "AURA" + baseline ("Écoute. Comprend. Agit.") superposés sur l'orb
- Bandeau du bas : état actuel en toutes lettres (IDLE/LISTENING/
  THINKING/SPEAKING), visualisation waveform audio, bouton micro central

**Colonne droite — Tableau de bord**
- Panneaux empilés et repliables, chacun avec un bouton "+" pour ajout
  rapide et un lien "Voir tout(e)s les ..." :
  - **TÂCHES** — 3 items visibles + échéance relative (Aujourd'hui,
    Demain, Vendredi...)
  - **RAPPELS** — 3 items visibles + tag de priorité (Important,
    Quotidien, Travail...)
  - **NOTES** — 3 items visibles + date
  - **AGENDA** — vue jour avec créneaux horaires et durée
  - **MÉMOIRE & PRÉFÉRENCES** — rappel des préférences apprises
    (résumés courts, rappels le matin, objectif courant...), avec lien
    "Gérer les préférences"

**Bandeau inférieur**
- Version du noyau AURA-CORE
- Statut global ("Toutes les fonctions opérationnelles")
- Icônes utilitaires (visualisation, son, luminosité/thème)

## Écart avec l'implémentation actuelle

| Élément du mockup | Statut actuel (v0.4) |
|---|---|
| Orb central animé | ✅ Implémenté (version simplifiée) |
| États IDLE/THINKING/SPEAKING/etc. | ✅ Implémenté |
| Chat texte avec historique | ✅ Implémenté |
| Panneau Tâches/Rappels/Notes dans le dashboard | ❌ Pas encore — actuellement uniquement accessible via commandes texte |
| Agenda visuel | ❌ Pas encore (module rendez-vous à venir) |
| Panneau Mémoire & Préférences | ❌ Pas encore (Phase 4 — mémoire long terme) |
| Indicateurs de statut (IA, voix, Internet, sécurité) | ❌ Pas encore |
| Micro / visualisation audio | ❌ Pas encore (Phase 3 — voix) |

Ce dashboard sera construit progressivement, panneau par panneau, une fois
les modules backend correspondants prêts — pas avant, pour rester fidèle à
la méthode de travail du projet ("une étape doit fonctionner avant de
passer à la suivante").
