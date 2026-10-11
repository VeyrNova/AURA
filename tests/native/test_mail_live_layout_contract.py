import os
import unittest
from pathlib import Path
from PySide6.QtCore import QUrl, QObject
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from aura_native.mail.service import MailService, PermissionRequiredMailBackend, FakeMailBackend
from aura_native.mail.qt_bridge import NativeMailBridge

ROOT = Path(__file__).parents[2]


class MailLiveLayoutContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QApplication.instance() or QApplication([])

    def _view(self, bridge, width=1100, height=700):
        view = QQuickView(); view.rootContext().setContextProperty('mailBridge', bridge)
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.setWidth(width); view.setHeight(height)
        view.setSource(QUrl.fromLocalFile(str(ROOT / 'app/qml/views/MailView.qml')))
        self.assertEqual(view.status(), QQuickView.Ready)
        return view

    def test_permission_layout_has_sidebar_list_preview(self):
        bridge = NativeMailBridge(MailService(PermissionRequiredMailBackend()))
        view = self._view(bridge)
        try:
            root = view.rootObject()
            for name in ('nativeMailSidebar', 'nativeMailListPanel', 'nativeMailPreviewPanel', 'nativeMailPermissionPanel'):
                self.assertIsNotNone(root.findChild(QObject, name))
            self.assertTrue(root.findChild(QObject, 'nativeMailPermissionPanel').property('visible'))
            self.assertEqual(bridge.permissionState, 'permission_required')
        finally:
            view.setSource(QUrl())

    def test_fake_inbox_and_preview(self):
        bridge = NativeMailBridge(MailService(FakeMailBackend()))
        bridge.setMode('inbox'); QTest.qWait(30); bridge.selectMessage('m1')
        view = self._view(bridge)
        try:
            self.assertEqual(len(bridge.messages), 1)
            self.assertEqual(bridge.selectedMessage['subject'], 'Bonjour')
            self.assertTrue(bridge.selectedSummary)
            self.assertEqual(bridge.threadMessages[0]['message_id'], 'm1')
            self.assertFalse(view.rootObject().findChild(QObject, 'nativeMailPermissionPanel').property('visible'))
        finally:
            view.setSource(QUrl())

    def test_premium_contract_responsive_and_styled(self):
        source = (ROOT / 'app/qml/views/MailView.qml').read_text(encoding='utf-8')
        self.assertIn('nativeMailReadOnlyStatus', source)
        self.assertIn('nativeMailSummaryCard', source)
        self.assertIn('selectedSummaryLabel', source)
        self.assertIn('background: null', source)
        self.assertNotIn('QtQuick.Controls.Button', source)
        bridge = NativeMailBridge(MailService(FakeMailBackend()))
        for width, height in ((1100,700),(1280,720),(1440,900),(1920,1080)):
            with self.subTest(width=width):
                view = self._view(bridge, width, height)
                try:
                    root=view.rootObject(); self.assertIsNotNone(root.findChild(QObject,'nativeMailSidebar'))
                    self.assertIsNotNone(root.findChild(QObject,'nativeMailListPanel'))
                    self.assertIsNotNone(root.findChild(QObject,'nativeMailPreviewPanel'))
                    self.assertGreater(root.findChild(QObject,'nativeMailSidebar').width(), 0)
                    self.assertGreater(root.findChild(QObject,'nativeMailPreviewPanel').width(), 0)
                finally: view.setSource(QUrl())

    def test_modules_mail_uses_direct_native_route_and_body_scroll_is_vertical(self):
        modules = (ROOT / 'app/qml/views/ModulesView.qml').read_text(encoding='utf-8')
        self.assertIn('root.navigateRequested("mail")', modules)
        self.assertNotIn('root.activePanel = "mail"', modules)
        mail = (ROOT / 'app/qml/views/MailView.qml').read_text(encoding='utf-8')
        self.assertIn('ScrollBar.horizontal.policy: ScrollBar.AlwaysOff', mail)
        self.assertIn('Text.WrapAnywhere', mail)
        self.assertIn('nativeMailBodyScroll', mail)

