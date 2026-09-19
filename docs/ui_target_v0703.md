# AURA — contrat visuel UI finale (v0.7.0.3)

La référence finale est une interface bureau sombre premium, structurée en cinq zones :

- barre supérieure : identité AURA, heure/date, IA locale, voix, Internet, Security Core, mode ;
- navigation verticale gauche : conversation, modules, mémoire, fichiers, statistiques, réglages ;
- conversation à gauche : historique, bulles VOUS/AURA, saisie et microphone ;
- scène centrale : grande orbe dynamique AURA, télémétrie et waveform d'état ;
- tableau de bord à droite : tâches, rappels, notes, agenda, mémoire/préférences ;
- bandeau inférieur : état global et contrôles rapides.

## Orbe
`ui/orb_widget.py` est désormais la source unique de vérité visuelle. La future refonte UI doit réutiliser ce composant plutôt que créer une seconde orbe.

États attendus :
- IDLE : respiration lente cyan/violet ;
- LISTENING : onde plus énergique cyan ;
- THINKING/PROCESSING : anneaux plus rapides et violet renforcé ;
- SPEAKING : énergie maximale et waveform active ;
- ERROR : palette rouge/rose, animation ralentie.

Le rendu doit rester original à AURA : concentriques HUD, plasma lumineux, centre sombre lisible, `AURA` et `COMPREND. ANTICIPE. AGIT.`.
