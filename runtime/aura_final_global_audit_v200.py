"""AURA A200-R25 final global audit and AURA v2.0 certification.

This module is audit-only. It creates no execution authority and performs no
PC mutation. Certification is emitted by the installer only after every
read-only audit assertion passes.
"""

from __future__ import annotations

A200_R25_MARKER = "AURA_A200_R25_FINAL_GLOBAL_AUDIT_AURA_V2_CERTIFICATION_V1"

AUDIT_ONLY = True
REAL_PC_MUTATION_ALLOWED = False
RUNTIME_AUTHORITY_MUTATION_ALLOWED = False
DEPLOYED_UI_MUTATION_ALLOWED = False
ROADMAP_SCHEDULE_MUTATION_ALLOWED = False
CERTIFICATE_CREATION_ALLOWED = True

REQUIRE_R12_CERTIFICATE = True
REQUIRE_R13_TO_R24_PASS_CHAIN = True
REQUIRE_PROTECTED_HASH_CHAIN = True
REQUIRE_READ_ONLY_RUNTIME_PROBE = True
REQUIRE_RUNTIME_READY = True
REQUIRE_ZERO_PENDING_RECOVERY = True
REQUIRE_ZERO_RUNNING_IDEMPOTENCY = True
REQUIRE_ZERO_PENDING_APPROVALS = True


def assert_r25_contract() -> None:
    if not AUDIT_ONLY:
        raise RuntimeError("R25 must remain audit-only")
    if REAL_PC_MUTATION_ALLOWED:
        raise RuntimeError("R25 may not mutate Windows")
    if RUNTIME_AUTHORITY_MUTATION_ALLOWED:
        raise RuntimeError("R25 may not mutate runtime authorities")
    if DEPLOYED_UI_MUTATION_ALLOWED:
        raise RuntimeError("R25 may not mutate deployed UI")
    if ROADMAP_SCHEDULE_MUTATION_ALLOWED:
        raise RuntimeError("R25 may not mutate roadmap schedule")
    if not CERTIFICATE_CREATION_ALLOWED:
        raise RuntimeError("R25 must be able to emit the final certificate")
    if not all(
        (
            REQUIRE_R12_CERTIFICATE,
            REQUIRE_R13_TO_R24_PASS_CHAIN,
            REQUIRE_PROTECTED_HASH_CHAIN,
            REQUIRE_READ_ONLY_RUNTIME_PROBE,
            REQUIRE_RUNTIME_READY,
            REQUIRE_ZERO_PENDING_RECOVERY,
            REQUIRE_ZERO_RUNNING_IDEMPOTENCY,
            REQUIRE_ZERO_PENDING_APPROVALS,
        )
    ):
        raise RuntimeError("R25 final certification requirements incomplete")
