import os, unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from aura_native.location import CurrentLocation, CurrentLocationService, FakeCurrentLocationProvider

class CurrentLocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen'); cls.app=QApplication.instance() or QApplication([])
    def test_success(self):
        p=FakeCurrentLocationProvider(CurrentLocation(43.427,6.431,12.0)); s=CurrentLocationService(p)
        s.request(); self.assertEqual(s.state,'ready'); self.assertEqual(s.location.latitude,43.427); self.assertEqual(p.calls,1)
    def test_permission_and_unavailable_states(self):
        for code, expected in [('permission_required','permission_required'),('denied','permission_denied'),('unavailable','unavailable'),('error','error')]:
            with self.subTest(code=code):
                s=CurrentLocationService(FakeCurrentLocationProvider(error=code)); s.request(); self.assertEqual(s.state,expected); self.assertIsNone(s.location)
    def test_timeout_is_bounded(self):
        s=CurrentLocationService(FakeCurrentLocationProvider(), timeout_ms=10); s.request(); QTest.qWait(50); self.assertEqual(s.state,'timeout'); self.assertIsNone(s.location)

if __name__ == '__main__': unittest.main()
