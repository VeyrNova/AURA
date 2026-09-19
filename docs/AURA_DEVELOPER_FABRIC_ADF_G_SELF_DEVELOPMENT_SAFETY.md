# AURA Developer Fabric — ADF-G

ADF-G governs AURA modifying its own code.

It adds risk classification, exact approval hierarchy, cryptographic patch-bound challenges, constitutional release gating, forbidden audit/certification targets, SHA-256 chained audit events, durable self-development receipts, and explicitly approved rollback.

ADF-F staging/tests/backups remain mandatory and cannot be bypassed.

Risk levels: standard, elevated, critical, constitutional, forbidden.

Critical changes require both the base `APPLY txn...` approval and a second `AUTHORIZE SELF ...` phrase derived from the proposal digest. Constitutional changes additionally require `release_mode` and `AUTHORIZE RELEASE ...`.

Certification/result files, transaction backups, `.aura_audit`, `.git`, secrets and key material cannot be self-modified.


## R2 — Developer mode by voice or text

Developer mode is disabled by default.

The same deterministic command parser accepts typed text and STT transcripts, including:

- `Aura, active le mode développeur`
- `Aura, passe en mode développeur`
- `Aura, désactive le mode développeur`
- `Aura, repasse en mode normal`

Activating developer mode is only permission to enter developer mode. It does not grant permission to write: ADF-F staging/tests and every ADF-G approval gate remain mandatory.

After a successful self-development transaction, the receipt returns a short `spoken_summary` intended for the existing AURA TTS layer, for example:

`J’ai modifié aura_fabric_http_gateway.py. Les tests sont passés.`

Hashes, receipts, audit-chain details and verbose technical logs are never intended to be spoken.

ADF-H is responsible for live binding of the existing text/STT router to this controller and forwarding `speak` / `spoken_summary` to TTS.
