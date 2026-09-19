# AURA v0.8.6.3 D1.1 — Clean Runtime Metadata Audit

Le D1 initial a volontairement ratissé large, mais les résultats sont pollués par les anciens rapports, `vendor`, payloads et artefacts de test.

Ce D1.1 est **lecture seule** et limite l'analyse à :

- code runtime Core ;
- `main.py` et launchers AURA ;
- UI active résolue par `%LOCALAPPDATA%\AURA\ui\current.json` ;
- `src/` et `tools/` de cette UI active ;
- métadonnées actives dans le code.

Il distingue :

- candidats à la version applicative ;
- révisions de modules/contrats (`VERSION`, `SCHEMA`, `GATE_REVISION`) ;
- release/build UI ;
- chemins/ports/URLs réellement actifs ;
- anciens marqueurs présents seulement dans commentaires/docstrings.

Aucun fichier du projet ou de l'UI n'est modifié.

## Exécution

Lancer :

`RUN_AURA_V0_8_6_3_D1_1_CLEAN_RUNTIME_METADATA_AUDIT.bat`

Puis envoyer :

`AURA_V0_8_6_3_D1_1_CLEAN_RUNTIME_METADATA_RESULT.json`

## License

AURA is distributed under an **All Rights Reserved** proprietary license. See `LICENSE` for details.
