# Reminder scheduler isolated-import gate

## Result (2026-10-04)

The original strict failure was `ReminderScheduler -> PySide6.QtCore` at
module import time. The scheduler now contains a stdlib-only
`ReminderScheduler` policy core. Qt integration is isolated in
`QtReminderSchedulerAdapter`, which creates `QTimer` only when the native UI
runtime is composed. Time-zone data is resolved lazily by the reminder time
helper as well.

The targeted strict subprocess import passes (`STRICT_REMINDER_IMPORT=PASS`)
with `-I -S -B`; no site-packages injection or validator change was used.
The normal reminder suite is 11/11 and bootstrap tests are 14/14.

The Qt-only notification, window/tray and package re-export boundaries were
isolated. Diagnostics uses an optional psutil collector. ADF construction is
now persistence-free; `initialize()` opens SQLite only for explicit runtime
use. The strict validator progressed past the ADF side-effect failure. The
remaining host result is `FileNotFoundError` from `tempfile` because the
isolated interpreter has no usable temporary directory. No validator
weakening was used.

No parity implementation or cutover was performed.
