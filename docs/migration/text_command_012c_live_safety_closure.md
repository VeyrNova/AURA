# Text Command Lot 012C — live safety closure

## Final closure pass — 2026-10-10

The confirmation boundary is structural: `UiPreparedActionConfirmer` is the only confirmation capability. The generic `pending_action.confirm` bus route is intentionally non-authoritative; source strings and `confirmed=True` cannot grant authority. This supersedes the earlier generic-bus confirmation and intermediate `source == "qml"` check, after spoofability was identified.

Contact, Reminder, Memory 008, and Voice 007 tests now model the same flow: proposal creates a PreparedAction, the generic bus is rejected with zero mutation, and an explicit UI capability performs confirmation. Voice, Agent, Router, Tool, LLM, and background paths cannot confirm.

The targeted closure regression is 268/268 PASS, including Local Text 004 at 42/42. The authority tests pass. The complete obsolete-confirmation audit found no remaining obsolete generic-bus success test; remaining confirmation references are negative-security, UI-capability, bridge-contract, document/system-control, or unrelated assertions.

Previously proven live evidence remains: Contact CRUD, cancel zero-mutation, stale-target protection, normal chat routing without PreparedAction leakage, and PC Read windows/processes/foreground. Provider response remains blocked by provider availability. Memory live mutation remains a separate pending gate.

Canonical execution uses `unittest` with `PYTHONDONTWRITEBYTECODE=1`; pytest is not required. The 004 stress result remains 10/10 fresh processes, 42/42 each, zero hangs. Historical run 3 remains ambiguous; no root cause is invented and the current hang blocker is false.

## Bounded Native suite final gate — 2026-10-10

All 147 Native test modules were accounted for in fresh, externally bounded unittest processes. The first pass was 146/147 modules green; `test_isolation` exposed test-process Qt module pollution after a scheduler lifecycle test. The smallest test-only cleanup was applied and the affected module rerun passed 16/16. Final aggregate: 147/147 modules PASS, 723 tests run, 0 failures, 0 errors, 1 expected skip, 0 timeouts. The issue was a TEST_REGRESSION in test isolation cleanup, not a product authority defect.

Lot1 strict execution also passed 53/53; its validator's baseline-drift report was environmental harness evidence only. Test-owned processes and the isolated final smoke state were cleaned up. LOT 012C is closed; Memory live validation and provider availability remain separate external gates.
