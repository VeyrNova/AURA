# R3A — scheduler natif offline

Migration 10 ajoute `claimed_at`, `notified_at` et `expired_at` à `local_reminders`. Le scheduler `ReminderScheduler` est créé par `compose_runtime`, possède un `QTimer` single-shot et est arrêté par `NativeRuntime.stop()`.

Les heures murales sont interprétées en `Europe/Paris`, converties en UTC, avec décalage vers la première minute valide au printemps et `fold=0` en automne. La fenêtre manquée est de 24 heures et la lease de claim de 5 minutes.

La livraison utilise claim atomique, notifier offline interne et marquage persistant. Il s’agit d’une déduplication robuste, pas d’un exactly-once absolu entre SQLite et une notification externe. Aucun Windows Toast, tray, service, autostart ou réseau n’est ajouté.

Validation R3A : 10 tests explicites PASS : claim récent, claim stale, échec notifier et retry après lease, trois rappels simultanés, second `process_due`, suppression avant échéance, reschedule après création plus proche, arrêt idempotent, bornes 23:59/24:00/24:01, restart notified/expired/stale et conversion DST. La frontière de 24 h est inclusive : 24:00 est notifié, au-delà est expiré. La sémantique est at-least-once avec déduplication persistante, jamais exactly-once absolu entre SQLite et un notifier externe.

Correction R3B : `on_time_grace=60s` est distinct de la fenêtre manquée de 24 h. Une échéance à la minute est classée `missed=false` jusqu’à la limite incluse ; au-delà, elle est `missed=true` tout en restant notifiable jusqu’à 24 h.
