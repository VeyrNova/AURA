# Google Daily Hub — conception native

Le Daily Hub agrège Calendar, Gmail et Tasks par date locale via
`GoogleDaySummaryService`. Les compteurs sont fondés sur des métadonnées; les
corps Gmail ne sont jamais chargés pour les cellules Agenda. Une absence de
permission Gmail est exposée comme `permission_required`, jamais comme zéro.

`MailSummaryService` est local, borné et injecté; il utilise un fallback
snippet/objet si Ollama est indisponible. Les liens Gmail et Tasks sont
construits par `mail.links` et aucun identifiant n'est interpolé en JavaScript.
Le parcours legacy reste inchangé et aucune écriture Google n'est déclenchée.

Le popup expose maintenant les trois listes, les états permission/empty, les
liens d'ouverture et les résumés locaux asynchrones. La file de résumé est
limitée à deux workers; un identifiant de génération ignore les résultats d'un
jour quitté. Le cache ne conserve que clé message/date/modèle et résumé, jamais
le corps complet.

Validation ciblée: 4 tests Daily Hub verts et self-check QML natif vert.
