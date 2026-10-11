# LOT 6B-B4.1 — Google write providers offline

Calendar and Tasks write methods now exist behind the existing
PreparedAction confirmation path. Calendar uses `events.insert`, `events.patch`
and `events.delete`; Tasks uses `tasks.insert`, `tasks.patch(status=completed)`
and `tasks.delete`. Responses are normalized to native models and API status
codes are mapped to native provider errors.

No provider write is called by prepare handlers. Execution still requires a
persisted action in `confirmed` state and repository idempotence prevents
replay. SQLite and Google are not one atomic transaction; repository state is
marked executed only after the provider call succeeds.

Validation is offline only with mocked discovery services. No Google mutation,
OAuth flow or network call was executed. Write capability remains pending real
human validation in B4.2.
