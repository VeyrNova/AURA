"""Read-only daily metadata aggregation for the native Agenda."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime


@dataclass(frozen=True)
class DailySummary:
    day: str
    calendar_events: tuple = ()
    mails: tuple = ()
    tasks: tuple = ()
    calendar_state: str = 'unknown'
    mail_state: str = 'unknown'
    task_state: str = 'unknown'
    errors: dict = field(default_factory=dict)

    @property
    def calendar_count(self): return len(self.calendar_events)
    @property
    def mail_count(self): return len(self.mails)
    @property
    def task_count(self): return len(self.tasks)


def _local_key(value):
    text = str(value or '')
    if not text: return ''
    if len(text) > 10 and text[4] != '-':
        try: return parsedate_to_datetime(text).date().isoformat()
        except (TypeError, ValueError, OverflowError): return ''
    return text[:10]


class GoogleDaySummaryService:
    def __init__(self, calendar_service=None, tasks_service=None, mail_service=None):
        self.calendar_service, self.tasks_service, self.mail_service = calendar_service, tasks_service, mail_service

    def summaries_for_dates(self, days):
        keys = tuple(dict.fromkeys(d.isoformat() if isinstance(d, date) else str(d)[:10] for d in days))
        rows = {key: {'calendar': [], 'mail': [], 'tasks': []} for key in keys}
        states = {'calendar': 'unavailable', 'mail': 'unavailable', 'tasks': 'unavailable'}
        errors = {}
        sources = (
            ('calendar', self.calendar_service, 'list_events', 'start'),
            ('tasks', self.tasks_service, 'list_tasks', 'due'),
            ('mail', self.mail_service, 'list_messages', 'date'),
        )
        for name, service, method, field_name in sources:
            if service is None: continue
            try:
                if name == 'calendar' and keys:
                    start = datetime.fromisoformat(min(keys)).astimezone().isoformat()
                    end = (datetime.fromisoformat(max(keys)) + timedelta(days=1)).astimezone().isoformat()
                    values = service.list_events(start=start, end=end)
                else:
                    values = getattr(service, method)()
                for item in values:
                    key = _local_key(getattr(item, field_name, ''))
                    if key in rows: rows[key][name].append(item)
                states[name] = 'connected'
            except Exception as exc:
                code = str(getattr(exc, 'code', exc)).upper()
                states[name] = 'permission_required' if 'PERMISSION' in code else 'error'
                errors[name] = states[name]
        return {key: DailySummary(key, tuple(row['calendar']), tuple(row['mail']), tuple(row['tasks']),
                                  states['calendar'], states['mail'], states['tasks'], dict(errors))
                for key, row in rows.items()}

    def summary_for_date(self, day):
        key = day.isoformat() if isinstance(day, date) else str(day)[:10]
        return self.summaries_for_dates((key,))[key]
