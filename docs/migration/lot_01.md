# Lot 1 — socle autonome et chemins

Statut : lot 1 implémenté et validé sous Python 3.11.9. Aucun raccordement UI.

Le package `aura_native` fournit uniquement des contrats, une configuration
explicite, des chemins et un cycle de vie minimal. Aucun Core historique n'est
copié. Le diagnostic annonce `application_ready: false` et les fonctionnalités
non raccordées comme `not_implemented`.

## Exécution depuis la racine du workspace

```powershell
& .\.runtime\python311\python.exe -I -S -B .\tools\native_core_selfcheck.py --self-check --state-dir tests/native/_evidence/unused-profile
& .\.runtime\python311\python.exe -I -S -B .\tests\native\validate_lot1.py
```

Ces commandes utilisent uniquement le Python local déjà présent. `-I -S -B`
désactive l'influence du site Python, des variables Python et la génération de
bytecode. Aucune installation ni connexion réseau n'est nécessaire. Le socle
ne lance pas de processus ; le superviseur de validation lance exactement un
interpréteur enfant pour tester le diagnostic dans un processus neuf.

Les chemins relatifs sont ancrés dans la racine du projet, jamais dans le
répertoire courant. `--state-dir` est obligatoire. Aucune variable historique,
aucun `.env`, aucune session existante ne sont consultés. Le diagnostic ne crée
pas le répertoire d'état. Un package installé hors du checkout requiert un
`--project-root` explicite ; le packaging complet de l'application est hors lot 1.

Les ressources applicatives et les environnements Python sont protégés contre
leur sélection comme répertoire d'état. Les redirections de sous-répertoires
vers l'extérieur sont rejetées. Cette validation de chemins n'est pas une
sandbox : tout futur service qui écrit devra traiter les courses filesystem et
appliquer sa propre politique d'accès.

## Vérification et preuves

Le fichier local ignoré `tests/native/_evidence/before.json` contient les SHA-256,
tailles et dates de modification des fichiers présents avant le lot 1. Les
rapports `validation_*.json` sont créés avec ouverture exclusive et conservés.
Les tests ne créent ni ne suppriment de fixtures sur disque.

Résultats : 37 tests unitaires réussis ; diagnostic exécuté dans un interpréteur
neuf avec succès. Cycle de vie `created -> running -> stopped`, périmètre
`minimal_foundation_only`, `application_ready: false`. Dix modules `aura_native`
sont chargés ; aucun import historique, Qt Widgets ou WebEngine n'est détecté.
Le reste des imports appartient à la bibliothèque standard et au superviseur.

L'inventaire initial couvre 9 954 fichiers (775 374 999 octets). Son empreinte
canonique SHA-256 est
`57d92839d0aee47aba5fbc385996f2e22656485449f343d0dea7afabc6a80a93`.
La comparaison contrôle chaque contenu, taille et date de modification, ainsi
que la présence éventuelle de nouveaux fichiers hors des emplacements autorisés.
Les rapports JSON horodatés donnent les résultats exacts de chaque exécution.

Un premier lancement du superviseur avait bloqué les descripteurs des tubes
anonymes utilisés pour capturer la sortie de l'enfant. Le contrôle a été corrigé
uniquement pour ces tubes en lecture lors du lancement déclaré. Aucun service
historique n'a été démarré. Les validations suivantes n'ont aucune violation.

Les seules écritures de la validation sont ses nouveaux rapports dans
`tests/native/_evidence`. Le diagnostic enfant n'écrit rien et ne lance aucun
processus. Les fichiers de preuve locaux sont exclus de Git et conservés ; aucune
suppression ou restauration n'est nécessaire.

Le backend de build est fixé à `setuptools==84.0.0`, version déjà observée dans
l'environnement local. Aucune construction de wheel, installation ou résolution
réseau n'a été effectuée. Le socle n'a aucune dépendance d'exécution externe.

Le superviseur bloque les écritures (sauf son nouveau rapport), mutations de
fichiers, connexions réseau, ouvertures SQLite et processus non déclarés. Il
contrôle les modules chargés et leurs origines. L'enfant applique le même
contrôle, sans aucune écriture autorisée.

Limite de preuve : les hooks d'audit Python couvrent les opérations Python des
processus supervisés, pas toute l'activité du système ni un éventuel accès
natif non exposé par ces hooks. Le socle utilise uniquement la bibliothèque
standard ; aucun composant Qt ni service applicatif n'est chargé.

## Rollback et suite

Cesser d'utiliser le nouveau diagnostic suffit : les fichiers et lanceurs
existants restent inchangés. Le lot 2 exige une autorisation distincte. Il devra
définir le bus, les garanties de thread et la frontière UI sans instancier les
ponts historiques dans le futur mode natif. Les services, bases, secrets,
fournisseurs IA et voix restent hors périmètre.
