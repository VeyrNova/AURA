# LOT 014C — Native background ownership and system tray policy

Status: CLOSED  
Validation date: 2026-10-11

## Authoritative process-lifetime contract

NativeRuntime is the single background owner. Its explicit lifecycle is:

STARTING/created → RUNNING → background RUNNING → STOPPING → STOPPED.

The reminder scheduler is started once by the Native runtime and is
idempotent. It continues while the process remains alive, including when the
window is hidden or minimized. Explicit shutdown stops background work before
closing the Native runtime. No post-process-exit execution is provided or
claimed.

## Tray policy

AuraTrayService is the sole QSystemTrayIcon owner. When the system tray is
available, the Native window close event is intercepted to hide the window and
keep the process alive. The tray Show action restores and foregrounds the
window. Tray Quit uses the centralized shutdown callback and terminates AURA.
Tray cleanup is idempotent.

When the system tray is unavailable, QApplication keeps its normal
quit-on-last-window-closed behavior: closing the window exits rather than
creating an invisible process.

## Background and reminder behavior

The LOT 014B NotificationCoordinator remains the only reminder notification
route. The hidden-window policy preserves exactly one reminder request through
the Native coordinator, with the existing identity/deduplication contract.
No Legacy fallback exists.

Explicit quit stops the scheduler, closes notification state, disposes the
tray, closes Native bridges/runtime resources, and requests QApplication quit
once. Repeated shutdown calls are safe.

## Post-exit and startup decisions

BACKGROUND_POST_PROCESS_EXIT_REQUIRED=false
BACKGROUND_POST_PROCESS_EXIT_SUPPORTED=false

The audited product contract requires reminders while AURA remains alive in
the tray, not after explicit Quit AURA. No Windows Task Scheduler task,
registry Run key, or automatic startup was added.

WINDOWS_AUTOSTART_EXISTING=false
WINDOWS_AUTOSTART_REQUIRED_FOR_CUTOVER=false

## Validation

- LOT 014C focused suite: 36/36 PASS, 0 FAIL, 0 ERROR.
- Real isolated Native QApplication + QQmlApplicationEngine self-check: PASS.
- Tray-unavailable fallback: PASS; the offscreen Qt environment reported no
  system tray and normal application exit policy was retained.
- Canonical LOT 013 regression: 33 total, 32 PASS, 0 FAIL, 0 ERROR, 1
  expected skip.
- LOT 014B notification regression: PASS.
- Computer Use was exposed and desktop-bound but CU_APPS_COUNT=0; no visual
  tray claim was made.

BACKGROUND_CUTOVER_STATUS=PASS
TRAY_CUTOVER_STATUS=PASS
LOT_014C=CLOSED

Remaining cutover work is LOT 014D — Lifecycle and persistence cutover safety.
