import unittest
import time
from datetime import date
from aura_native.google.day_summary import GoogleDaySummaryService
from aura_native.google.models import CalendarEvent, TaskItem
from aura_native.google.providers import FakeCalendarProvider, FakeTasksProvider
from aura_native.mail.models import MailMessage
from aura_native.mail.service import MailService, FakeMailBackend
from aura_native.mail.summary import MailSummaryService
from aura_native.mail.links import gmail_url, tasks_url

class TestGoogleDailyHub(unittest.TestCase):
    def test_month_aggregation_counts_are_per_day(self):
        cal = FakeCalendarProvider(); cal.events = [
            CalendarEvent('c1','A','2026-10-01T09:00:00+02:00','2026-10-01T10:00:00+02:00','Europe/Paris'),
            CalendarEvent('c2','B','2026-10-02T09:00:00+02:00','2026-10-02T10:00:00+02:00','Europe/Paris'),
            CalendarEvent('c3','C','2026-10-04T09:00:00+02:00','2026-10-04T10:00:00+02:00','Europe/Paris'),
        ]
        tasks = FakeTasksProvider(); tasks.tasks = [TaskItem('t1','T1','2026-10-04'), TaskItem('t2','T2','2026-10-04'), TaskItem('t3','T3','2026-10-07')]
        mail = MailService(FakeMailBackend([
            MailMessage('m1','th1','a',(), 'S1','x','x','Fri, 02 Oct 2026 09:00:00 +0200'),
            MailMessage('m2','th2','a',(), 'S2','x','x','Fri, 02 Oct 2026 10:00:00 +0200'),
            MailMessage('m3','th3','a',(), 'S3','x','x','Fri, 02 Oct 2026 11:00:00 +0200'),
            MailMessage('m4','th4','a',(), 'S4','x','x','Sun, 04 Oct 2026 11:00:00 +0200'),
        ]))
        rows = GoogleDaySummaryService(cal, tasks, mail).summaries_for_dates([f'2026-10-{d:02d}' for d in range(1, 32)])
        self.assertEqual(rows['2026-10-02'].mail_count, 3)
        self.assertEqual((rows['2026-10-04'].mail_count, rows['2026-10-04'].task_count), (1, 2))
        self.assertEqual(rows['2026-10-05'].mail_count, 0)
        self.assertEqual(rows['2026-10-07'].task_count, 1)
    def test_date_local_counts_and_isolation(self):
        cal = FakeCalendarProvider(); cal.events = [CalendarEvent('c','Réunion','2026-10-03T09:00:00+02:00','2026-10-03T10:00:00+02:00','Europe/Paris')]
        tasks = FakeTasksProvider(); tasks.tasks = [TaskItem('t','À faire','2026-10-03')]
        mail = MailService(FakeMailBackend([MailMessage('m','th','a',(), 'Sujet','Extrait','corps','Sat, 03 Oct 2026 08:00:00 +0200')]))
        s = GoogleDaySummaryService(cal, tasks, mail).summary_for_date(date(2026,10,3))
        self.assertEqual((s.calendar_count,s.task_count,s.mail_count),(1,1,1))
    def test_mail_summary_fallback_is_bounded_and_cached(self):
        m=MailMessage('m','t','a',(), 'Sujet','Extrait','x'*5000,'')
        service=MailSummaryService(lambda text: text, max_input=100, max_output=30)
        self.assertLessEqual(len(service.summarize(m)),30); self.assertEqual(service.summarize(m),service.summarize(m))
    def test_safe_links(self):
        self.assertIn('#all/thread-1', gmail_url('thread-1')); self.assertEqual(tasks_url(),'https://tasks.google.com/')
    def test_async_generation_ignores_stale_results(self):
        from aura_native.mail.day_bridge import DailyHubActions
        seen=[]; service=MailSummaryService(lambda text: (time.sleep(.03), text)[1])
        a=DailyHubActions(service); m=MailMessage('m','t','a',(), 'Sujet','fallback','body','')
        a.summaryReady.connect(lambda *x: seen.append(x)); a.summarize([m]); a.summarize([]); time.sleep(.08)
        self.assertEqual(seen, [])
