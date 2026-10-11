# LOT 6B-B4.3 — validation réelle depuis l’interface native

The non-production launcher is
`tests/native/_evidence/lot6b_b43_ui_real.py`. It requires an explicit
`--launch`, uses the real native composition and an isolated state directory,
and does not inject PreparedActions or call Google providers directly.

Technical status: PASS TECHNIQUE / REAL UI VALIDATION REQUIRED. Manual checks
must cover Calendar create/confirm, Tasks create/confirm, cancel, double
confirm, restart with a prepared action, readback and explicit cleanup by the
returned event/task identifiers. No OAuth renewal or mutation is started by
Codex. Calendar and Tasks UI actions remain behind the existing confirmation
card and LocalBus guard.

The French Calendar create parser now separates temporal expressions from the
event title and computes explicit durations (15/30/45 minutes, one hour and
1h30). PreparedAction summaries include title, date and start/end times, so
the conversation message and confirmation card share the same human-readable
summary. Two native workspace text-input backgrounds no longer request
unsupported style customization.
