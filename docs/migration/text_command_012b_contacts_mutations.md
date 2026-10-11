# Text Command Lot 012B — Contacts local mutations

Lot 012B adds a local, confirmation-first mutation boundary for contacts. `contact.create`, `contact.update`, and `contact.delete` are represented by `PreparedAction` records and executed only after confirmation. Payloads retain the stable `contact_id`; update and delete also retain the observed version and refuse stale targets. Name resolution is exact and ambiguous names are rejected. Reads continue to use the existing read-only Contacts service and never create a PreparedAction.

Validation is offline and isolated in temporary SQLite databases. Computer Use was unavailable (`apps=[]`), so no live AURA input or test contact was created. No Google provider, OAuth, network, Legacy path, or external process is used.

The automated 012B suite covers create/update/delete preparation, validation, cancel zero-mutation, exact IDs, stale versions, ambiguity, exactly-once execution, router separation, and payload safety. Lot 012 read-only behavior remains unchanged.

012C authority addendum: the contacts PreparedAction path remains UI-capability-only. Generic bus confirmation is a negative-security path and cannot mutate contacts; the live CRUD, cancel zero-mutation, cleanup, and stale-target evidence remains valid.
