# W132 LIVE ACCEPTANCE

Milestone: W132 - PC Control Acceptance & Recovery
Version: v1.3.2
Accepted at: 2026-09-04T19:49:56+02:00

## Real Win32 acceptance
- Temporary owned windows only; no user application was closed.
- Exact-HWND focus: PASS
- Minimize + exact state rollback: PASS
- Maximize + exact state rollback: PASS
- Focus + prior-foreground rollback: PASS
- Canonical ActionReceipt lifecycle for restore: PASS
- Personal Result source/status/title truth: WINDOWS / succeeded / RESTAURATION
- Rollback token is one-use and bounded: PASS
- Changed/stale target fail-closed: PASS (permanent R8 invariant)
- PC failure Personal Result truth + receipt visibility: PASS (R7 invariant)
- CLOSE_WINDOW remains denied/unregistered: PASS
- TERMINATE_PROCESS remains denied/unregistered: PASS
- Raw shell/executable material remains denied: PASS
- Multi-screen live acceptance: DEFERRED_SINGLE_MONITOR_TOPOLOGY

LIVE_ACCEPTANCE: PASS
ROADMAP_CERTIFICATION_ELIGIBLE: YES
NEXT_GATE: O140 - Obsidian Creative Studio
