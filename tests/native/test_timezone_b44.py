from datetime import datetime
from zoneinfo import ZoneInfo
import unittest


class CalendarTimezoneTests(unittest.TestCase):
    def test_europe_paris_summer_and_winter(self):
        try:
            zone = ZoneInfo("Europe/Paris")
        except Exception as exc:
            self.skipTest(f"tzdata not installed in validation runtime: {exc}")
        self.assertEqual(datetime(2026, 9, 30, tzinfo=zone).utcoffset().total_seconds(), 7200)
        self.assertEqual(datetime(2026, 12, 15, tzinfo=zone).utcoffset().total_seconds(), 3600)

    def test_calendar_window_is_timezone_aware(self):
        try:
            zone = ZoneInfo("Europe/Paris")
        except Exception as exc:
            self.skipTest(f"tzdata not installed in validation runtime: {exc}")
        start = datetime(2026, 8, 31, tzinfo=zone)
        end = datetime(2026, 10, 12, tzinfo=zone)
        self.assertLess(start, end)
        self.assertEqual(start.date().isoformat(), "2026-08-31")
        self.assertEqual(end.date().isoformat(), "2026-10-12")


if __name__ == "__main__": unittest.main()
