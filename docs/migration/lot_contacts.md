# Contacts Native — functional parity lot

Contacts Native is a local, synthetic-safe contact manager. It uses a lazy
SQLite store under the Native runtime data directory, a Qt bridge and a
dedicated `ContactsView.qml`. The Legacy provider was an in-memory synthetic
provider with list/search/read/create/update/delete; an optional historical
Google People adapter is deliberately not used here.

Deletion requires an explicit confirmation and contact edits use a version
check. Contact fields are never written to standard logs. No OAuth, Google
People request, real contact migration or default-runtime cutover is part of
this lot.
