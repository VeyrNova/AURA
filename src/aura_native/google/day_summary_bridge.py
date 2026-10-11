"""Qt-thread delivery of read-only day metadata."""
from threading import Thread
from PySide6.QtCore import QObject, Property, Signal, Slot


def _row(summary):
    def item(x):
        if hasattr(x, 'event_id'):
            return {'id': x.event_id, 'title': x.title, 'start': x.start, 'end': x.end, 'status': x.status}
        if hasattr(x, 'message_id'):
            return {'id': x.message_id, 'threadId': x.thread_id, 'sender': x.sender, 'subject': x.subject,
                    'snippet': x.snippet, 'date': x.date, 'unread': x.unread, 'attachments': list(x.attachments)}
        return {'id': getattr(x, 'task_id', ''), 'title': getattr(x, 'title', ''), 'due': getattr(x, 'due', ''),
                'status': getattr(x, 'status', ''), 'notes': getattr(x, 'notes', '')}
    return {'date': summary.day, 'calendarCount': summary.calendar_count, 'mailCount': summary.mail_count,
            'taskCount': summary.task_count, 'mailState': summary.mail_state,
            'calendarState': summary.calendar_state, 'taskState': summary.task_state,
            'errors': summary.errors, 'calendarEvents': [item(x) for x in summary.calendar_events],
            'mails': [item(x) for x in summary.mails], 'tasks': [item(x) for x in summary.tasks]}


class GoogleDaySummaryBridge(QObject):
    summaryChanged = Signal()
    _loaded = Signal(object, int)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service, self._items, self._generation = service, {}, 0
        self._loaded.connect(self._apply)

    @Property('QVariantMap', notify=summaryChanged)
    def summaries(self): return dict(self._items)

    @Slot('QVariantList')
    def requestDates(self, days):
        keys = tuple(str(day)[:10] for day in days)
        self._generation += 1
        generation = self._generation
        self._items = {key: {'date': key, 'mailState': 'loading', 'taskState': 'loading',
                             'calendarState': 'loading', 'calendarCount': 0, 'mailCount': 0,
                             'taskCount': 0} for key in keys}
        self.summaryChanged.emit()

        def worker():
            values = self.service.summaries_for_dates(keys)
            self._loaded.emit({key: _row(value) for key, value in values.items()}, generation)
        Thread(target=worker, daemon=True, name='AuraDailyHub').start()

    @Slot(object, int)
    def _apply(self, values, generation):
        if generation != self._generation: return
        self._items = dict(values)
        months = sorted({str(key)[:7] for key in self._items})
        month = months[0] if len(months) == 1 else ",".join(months)
        calendar_total = sum(int(row.get('calendarCount', 0) or 0) for row in self._items.values())
        mail_total = sum(int(row.get('mailCount', 0) or 0) for row in self._items.values())
        task_total = sum(int(row.get('taskCount', 0) or 0) for row in self._items.values())
        print(
            f"DAILY_HUB_MONTH={month} "
            f"calendar_days_with_items={sum(bool(row.get('calendarCount')) for row in self._items.values())} "
            f"mail_days_with_items={sum(bool(row.get('mailCount')) for row in self._items.values())} "
            f"task_days_with_items={sum(bool(row.get('taskCount')) for row in self._items.values())} "
            f"calendar_total={calendar_total} mail_total={mail_total} task_total={task_total}",
            flush=True,
        )
        self.summaryChanged.emit()

    @Slot(str, result='QVariantMap')
    def summaryForDate(self, day): return dict(self._items.get(str(day)[:10], {}))
