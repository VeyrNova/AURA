"""Real Modules catalog QML and native route contract."""
import os
import unittest
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQuick import QQuickView

ROOT=Path(__file__).parents[2]

class ModulesNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.app=QApplication.instance() or QApplication([])

    def test_real_catalog_navigation_and_prefill(self):
        view=QQuickView();errors=[]
        view.engine().warnings.connect(lambda warnings:errors.extend(w.toString() for w in warnings))
        view.rootContext().setContextProperty('auraAssetBase',QUrl.fromLocalFile(str(ROOT/'app/assets')+os.sep).toString())
        view.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/views/ModulesView.qml')))
        try:
            self.assertEqual(view.status(),QQuickView.Ready)
            root=view.rootObject();navigation=[];prefills=[]
            root.navigateRequested.connect(navigation.append)
            root.conversationPrefillRequested.connect(prefills.append)
            root.openCatalogModule('weather');self.assertEqual(navigation,['weather'])
            root.openCatalogModule('research');self.assertEqual(navigation,['weather','search'])
            root.openCatalogModule('documents');self.assertEqual(navigation,['weather','search','documents'])
            root.openCatalogModule('mail');self.assertEqual(navigation,['weather','search','documents','mail'])
            self.assertFalse(any('ReferenceError' in e or 'TypeError' in e for e in errors),errors)
        finally:view.setSource(QUrl())

    def test_native_route_and_signal_forwarding(self):
        source=(ROOT/'app/qml/views/NativeWorkspaceView.qml').read_text(encoding='utf-8')
        self.assertIn('ModulesView {',source)
        self.assertIn('visible: root.workspace === "modules"',source)
        self.assertIn('&& root.workspace !== "modules"',source)
        self.assertIn('root.conversationPrefillRequested(text)',source)
        main=(ROOT/'app/qml/Main.qml').read_text(encoding='utf-8')
        self.assertIn('visible: root.modulesDockOpen',main)
        self.assertNotIn('visible: root.modulesDockOpen && runtimeMode === "legacy"',main)
        self.assertIn('root.navigateRequested("mail")', (ROOT/'app/qml/views/ModulesView.qml').read_text(encoding='utf-8'))

    def test_shared_catalog_is_visible_and_mail_bypasses_quick_panel_in_native(self):
        source=(ROOT/'app/qml/components/ModulesSubdock.qml').read_text(encoding='utf-8')
        self.assertIn('visible: root.page === "modules"', source)
        self.assertIn('if (runtimeMode === "native")', source)
        self.assertIn('navigateRequested("mail")', source)
        self.assertIn('page = "mail"', source)
        self.assertEqual(source.count('ListElement { key:'), 11)
        self.assertIn('MAIL RAPIDE', source)
        self.assertNotIn('text: "›"', source)

if __name__=='__main__':unittest.main()
