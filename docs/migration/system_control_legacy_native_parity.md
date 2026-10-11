# System Control legacy/native parity

Legacy provider: `integrations.pc_control.provider.PcControlWindowsProvider`, adapter `runtime.aura_pc_control_windows_v131.WindowsPcControlAdapter`. The registry contains the provider and its six typed capabilities; no shell, PowerShell, arbitrary executable, shutdown, restart, logoff, sleep, clipboard, brightness or process-kill capability is exposed by this provider.

| Capability | Legacy reachability | Native status | Risk | Confirmation |
|---|---|---|---|---|
| discover windows | REGISTERED_BUT_UNPROVEN (registry/provider path) | foundation | R0 | no |
| discover processes | REGISTERED_BUT_UNPROVEN | foundation | R0 | no |
| foreground window | REGISTERED_BUT_UNPROVEN | foundation | R0 | no |
| focus exact HWND/title | REGISTERED_BUT_UNPROVEN | foundation | R1 | yes |
| minimize exact HWND/title | REGISTERED_BUT_UNPROVEN | foundation | R1 | yes |
| maximize exact HWND/title | REGISTERED_BUT_UNPROVEN | foundation | R1 | yes |
| restore window state | REGISTERED_BUT_UNPROVEN | deferred | R1 | existing receipt layer required |

No capability is classified ACTIVE_REACHABLE without a live invocation trace. Text/voice router wiring remains deferred to the Text Command lot. The native service accepts typed requests only, rejects malformed targets, requires confirmation for mutations, and never evaluates shell text.

`SYSTEM_CONTROL_PARITY=PARTIAL`
`SYSTEM_CONTROL_CUTOVER_BLOCKER=true`

## System Control 002 validation (2026-10-10)
- Static provider path is `REGISTERED_AND_ROUTABLE` through the Legacy integration registry; historical live execution evidence remains unavailable because Legacy was not executed.
- `restore_window_state` is an internal recovery helper, not an external capability. External count: 6.
- Native typed adapter now lazily uses Win32 `user32` APIs for safe discovery/foreground/focus/minimize/maximize; no shell or external process execution.
- Live Windows API smoke returned SUCCESS for discover windows, discover processes, and foreground query without printing titles or process details.
- Targeted tests: 4/4 PASS. Natural-language/text/voice wiring and PreparedAction remain deferred.

## System Control 003 validation (2026-10-10)
- Test-owned live harness: `tests/native/_evidence/system_control_003_live.py` creates a uniquely titled PySide6 child window and targets only its exact PID/HWND.
- Native targeted tests: 20/20 PASS. Lot 1 strict validator: 53/53 PASS.
- Live safe API results: discover windows PASS; discover processes PASS; foreground query PASS; minimize/maximize owned window PASS; focus request was denied by Windows foreground policy in this non-interactive harness context and is reported as `DENIED_BY_WINDOWS_POLICY`, not treated as success.
- Pre-confirmation for focus/minimize/maximize returns `CONFIRMATION_REQUIRED`; no mutation occurs before confirmation. Closing the owned child yields stale target `NOT_FOUND` without a second process or window mutation.
- PID/HWND cross-check PASS; handle reuse was not reproduced; exact PID/HWND validation remains the defense. No shell, `shell=True`, process kill, shutdown, restart, logoff, sleep or hibernate path exists.
- Product integrations, PreparedAction, Text Command and Voice wiring remain deferred by design.

`SYSTEM_CONTROL_PARITY=PARTIAL_LIVE_API`
`SYSTEM_CONTROL_CUTOVER_BLOCKER=true`
