import unittest
from types import SimpleNamespace
from aura_native.diagnostics.service import DiagnosticsService
from aura_native.ui.qt_bridge import NativeDiagnosticsBridge

class FakePsutil:
    @staticmethod
    def cpu_percent(interval=None): return 27.0
    @staticmethod
    def virtual_memory(): return SimpleNamespace(percent=50, used=4*1073741824, total=8*1073741824)
    @staticmethod
    def disk_usage(_): return SimpleNamespace(percent=25, used=25_000_000_000, total=100_000_000_000)
    def __init__(self): self.received=1000; self.sent=2000
    def net_io_counters(self): return SimpleNamespace(bytes_recv=self.received,bytes_sent=self.sent)

class DiagnosticsNativeTests(unittest.TestCase):
    def test_service_to_bridge_signal_and_network_delta(self):
        fake=FakePsutil(); now=[0.0]
        bridge=NativeDiagnosticsBridge(service=DiagnosticsService(fake,clock=lambda:now[0]))
        changes=[]; bridge.diagnosticsChanged.connect(lambda:changes.append(bridge.diagCpuText))
        bridge.refreshDiagnostics()
        self.assertTrue(bridge.diagReady)
        self.assertEqual((bridge.diagCpuText,bridge.diagRamText,bridge.diagDiskText),('27%','4.0 / 8.0 Gio','25 / 100 GB'))
        now[0]=1.0; fake.received+=125000; fake.sent+=250000
        bridge.refreshDiagnostics()
        self.assertEqual((bridge.diagDownloadText,bridge.diagUploadText),('1.0 Mbps','2.0 Mbps'))
        self.assertEqual(len(changes),2)
    def test_real_collectors_do_not_return_permanent_fallbacks(self):
        bridge=NativeDiagnosticsBridge(); bridge.refreshDiagnostics()
        self.assertTrue(bridge.diagReady)
        for text in (bridge.diagCpuText,bridge.diagRamText,bridge.diagDiskText): self.assertNotIn(text,('Unavailable','ERROR',''))

if __name__=='__main__': unittest.main()
