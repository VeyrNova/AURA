# LOT 014B — Native notification contract

Status: CLOSED  
Validation date: 2026-10-11

Native owns reminder notification delivery through NotificationCoordinator,
InternalReminderNotificationCenter, QtWindowsReminderNotifier, and
AuraTrayService. The Native branch does not import or call Legacy notification
code.

The boundary returns NotificationResult with accepted, a truthful
NotificationCapability (SUPPORTED, UNSUPPORTED, UNAVAILABLE, or ERROR), a
stable notification_id, selected channel, source, and bounded failure reason.
Windows delivery is selected only when the process, tray, and message support
are available. Otherwise the same request uses the Native in-app center. There
is no Legacy fallback.

Reminder identity is:

reminder:<reminder_id>:<trigger_at>:<missed-bit>

The in-app center suppresses duplicate logical reminders during one process
lifetime while allowing new trigger times and missed states. Tray activation
is bounded to restoring and foregrounding AURA; in-app dismissal is supported.
No arbitrary or consequential action is accepted from a notification payload.

The existing scheduler uses this single coordinator route. Rejected delivery
is not marked notified, backend exceptions remain retryable, and the center
disconnects its bus subscription and rejects new work after close. The contract
is process-alive only; post-process-exit scheduling is deferred to LOT 014C.

Validation:

- Focused notification/reminder group: 33/33 PASS, 0 FAIL, 0 ERROR.
- Real isolated Native QApplication + QQmlApplicationEngine self-check: PASS.
- Canonical LOT 013 baseline: 33 total, 32 PASS, 0 FAIL, 0 ERROR, 1 expected skip.
- Computer Use was exposed and desktop-bound but CU_APPS_COUNT=0; visual
  validation was skipped and no visual claim is made.
- The isolated LOT 014B state was removed after validation.

NOTIFICATIONS_NATIVE_IMPLEMENTATION=PASS
NOTIFICATIONS_NATIVE_REACHABLE=YES
NOTIFICATIONS_LEGACY_DEPENDENCY=false
NOTIFICATIONS_PROCESS_ALIVE_SUPPORTED=true
NOTIFICATIONS_POST_EXIT_SUPPORTED=false
NOTIFICATIONS_CLICK_ACTIONS=restore-window and dismiss
NOTIFICATIONS_PERMISSION_CAPABILITY=truthful backend availability/support; displayed state is not claimed
NOTIFICATION_SHUTDOWN_SAFE=true
NOTIFICATIONS_CUTOVER_STATUS=PASS

Remaining dependency: LOT 014C — Background ownership and tray policy.
