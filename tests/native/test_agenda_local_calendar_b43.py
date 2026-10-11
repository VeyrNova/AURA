from datetime import date
from pathlib import Path
import calendar
import unittest


def build_month(year, month, today=None):
    first = date(year, month, 1)
    offset = (first.weekday())
    days = calendar.monthrange(year, month)[1]
    rows = []
    for i in range(42):
        ordinal = i - offset + 1
        value = date.fromordinal(first.toordinal() + ordinal - 1)
        rows.append({"date": value, "day": value.day, "month": value.month,
                     "year": value.year, "isCurrentMonth": value.month == month,
                     "isToday": today == value})
    return rows


class AgendaLocalCalendarTests(unittest.TestCase):
    def test_september_2026_has_fixed_grid_and_boundary_days(self):
        rows = build_month(2026, 9, date(2026, 9, 15))
        self.assertEqual(len(rows), 42)
        self.assertEqual(rows[1]["date"], date(2026, 9, 1))
        self.assertIn(date(2026, 9, 30), [row["date"] for row in rows])
        self.assertTrue(any(not row["isCurrentMonth"] for row in rows))
        self.assertEqual(sum(row["isCurrentMonth"] for row in rows), 30)

    def test_fake_clock_marks_only_today(self):
        rows = build_month(2026, 9, date(2026, 9, 15))
        self.assertEqual(sum(row["isToday"] for row in rows), 1)
        self.assertEqual(next(row for row in rows if row["isToday"])["day"], 15)

    def test_qml_uses_model_data_for_js_array_delegate(self):
        source = (Path(__file__).parents[2] / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.assertIn("String(modelData.dayNumber)", source)
        self.assertIn("modelData.inMonth", source)
        self.assertIn("modelData.isToday", source)


if __name__ == "__main__":
    unittest.main()
