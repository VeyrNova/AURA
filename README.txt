AURA P0.8.5.4.7.2 R1 — END-TO-END RUNTIME ACCEPTANCE PREFLIGHT HOTFIX

Objet
-----
Correction du certificat uniquement. Aucun fichier runtime AURA n'est modifié.

Corrections R1
--------------
- Les marqueurs VERSION/BUILD sont enregistrés sous leurs formes réelles et normalisés.
- Une divergence de format VERSION/BUILD génère un WARN mais ne bloque plus le test si les chemins et hashes critiques sont conformes.
- Ollama reste diagnostiqué mais n'est plus un gate global : le test d'intelligence valide le provider réellement configuré.
- Les checks critiques restent stricts : core actif, UI rc4.2, hash index UI, hash installed_model_policy, AuraPaths, base SQLite.

Utilisation
-----------
1. Fermer AURA.
2. Extraire cette archive dans C:\AURA GPT version en remplaçant les fichiers de certification précédents si demandé.
3. Lancer CERTIFIER_RUNTIME_END_TO_END.bat.
4. Suivre les tests affichés.
5. Envoyer AURA_P0_8_5_4_7_2_RUNTIME_ACCEPTANCE_RESULT.json.
