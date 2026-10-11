import os, unittest
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl, QObject
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from aura_native.mail.service import FakeMailBackend, MailService
from aura_native.mail.qt_bridge import NativeMailBridge

ROOT=Path(__file__).parents[2]
class MailNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): os.environ.setdefault('QT_QPA_PLATFORM','offscreen'); cls.app=QApplication.instance() or QApplication([])
    def test_read_search_thread_attachment_and_prepared_send(self):
        backend=FakeMailBackend(); bridge=NativeMailBridge(MailService(backend))
        bridge.search('Bonjour'); QTest.qWait(30); self.assertEqual(len(bridge.model.items),1); bridge.selectMessage('m1')
        self.assertEqual(bridge.selectedMessage['body'],'Salut, voici le message.'); self.assertEqual(bridge.threadMessages[0]['message_id'],'m1')
        self.assertEqual(bridge.service.fetch_attachment('m1','a1')['name'],'agenda.txt')
        bridge.prepareSend('bob@example.test','Hello'); self.assertEqual(len(backend.sent),0); bridge.cancelPrepared(); self.assertEqual(len(backend.sent),0)
        bridge.prepareSend('bob@example.test','Hello'); bridge.confirmPrepared(); self.assertEqual(len(backend.sent),1)
    def test_real_mail_view_offscreen(self):
        bridge=NativeMailBridge(MailService(FakeMailBackend())); view=QQuickView(); view.rootContext().setContextProperty('mailBridge',bridge); view.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/views/MailView.qml')))
        try: self.assertEqual(view.status(),QQuickView.Ready); self.assertTrue(view.rootObject())
        finally: view.setSource(QUrl())
    def test_initial_component_load_starts_inbox_and_error_is_not_empty(self):
        bridge=NativeMailBridge(MailService(FakeMailBackend(failure='NETWORK_ERROR')))
        view=QQuickView(); view.rootContext().setContextProperty('mailBridge',bridge); view.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/views/MailView.qml')))
        try:
            self.assertEqual(view.status(),QQuickView.Ready)
            self.assertTrue(bridge.loading)
            QTest.qWait(80)
            self.assertEqual(bridge.state,'API_ERROR')
            self.assertEqual(len(bridge.messages),0)
            self.assertIn('ERREUR DE SYNCHRONISATION', (ROOT/'app/qml/views/MailView.qml').read_text(encoding='utf-8'))
        finally: view.setSource(QUrl())

    def test_shell_is_ready_before_delayed_backend(self):
        class Slow(FakeMailBackend):
            def search(self, query): time.sleep(2); return super().search(query)
        bridge=NativeMailBridge(MailService(Slow()))
        bridge.openInbox(); started=time.perf_counter(); view=QQuickView(); view.rootContext().setContextProperty('mailBridge',bridge); view.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/views/MailView.qml')))
        shell_ms=(time.perf_counter()-started)*1000
        try:
            self.assertEqual(view.status(),QQuickView.Ready); self.assertLess(shell_ms,500); self.assertTrue(bridge.loading); QTest.qWait(20)
            self.assertIn('nativeMailSkeletons', (ROOT/'app/qml/views/MailView.qml').read_text(encoding='utf-8'))
            QTest.qWait(2100); self.assertFalse(bridge.loading); self.assertEqual(len(bridge.messages),1)
        finally: view.setSource(QUrl())
if __name__=='__main__': unittest.main()
