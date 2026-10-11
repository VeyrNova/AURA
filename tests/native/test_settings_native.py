"""Native locale persistence and real Settings QML control, offline."""
import os
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl, QPoint, QPointF, Qt
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest, QSignalSpy
from aura_native.bootstrap.composition import compose_runtime
from aura_native.ui.qt_bridge import NativeCoreBridge
from aura_native.config.locale_service import LocaleService

ROOT=Path(__file__).parents[2]

class SettingsNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        os.environ['AURA_PCC_FAKE']='1'
        cls.app=QApplication.instance() or QApplication([])

    def test_locale_persistence_validation(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests/native/_evidence') as directory:
            service=LocaleService(Path(directory))
            self.assertEqual(service.locale,'fr-FR')
            self.assertTrue(service.set_locale('en-US'))
            self.assertEqual(LocaleService(Path(directory)).locale,'en-US')
            self.assertFalse(service.set_locale('invalid'))
            self.assertEqual(service.locale,'en-US')
            service.path.write_text('{broken',encoding='utf-8')
            self.assertEqual(LocaleService(Path(directory)).locale,'fr-FR')

    def test_real_settings_qml_language_command_signal(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tests/native/_evidence') as directory:
            runtime=compose_runtime(project_root=ROOT,state_dir=directory)
            bridge=NativeCoreBridge(runtime)
            view=QQuickView()
            errors=[]
            view.engine().warnings.connect(lambda warnings:errors.extend(w.toString() for w in warnings))
            view.rootContext().setContextProperty('coreBridge',bridge)
            view.rootContext().setContextProperty('bridge',bridge)
            view.rootContext().setContextProperty('auraAssetBase',QUrl.fromLocalFile(str(ROOT/'app/assets')+os.sep).toString())
            try:
                view.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/views/SettingsView.qml')))
                self.assertEqual(view.status(),QQuickView.Ready)
                view.setResizeMode(QQuickView.SizeRootObjectToView);view.resize(1100,850);view.show();QTest.qWait(50)
                def find(item):
                    if item.objectName()=='nativeLocale-en-US':return item
                    for child in item.childItems():
                        found=find(child)
                        if found is not None:return found
                item=find(view.rootObject());self.assertIsNotNone(item)
                ancestor=item.parentItem()
                while ancestor is not None:
                    if ancestor.property('contentY') is not None:
                        ancestor.setProperty('contentY',max(0,ancestor.property('contentHeight')-ancestor.height()))
                        break
                    ancestor=ancestor.parentItem()
                QTest.qWait(20)
                spy=QSignalSpy(bridge.localeChanged)
                point=item.mapToScene(QPointF(item.width()/2,item.height()/2))
                QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
                self.app.processEvents()
                self.assertEqual(bridge.locale,'en-US');self.assertEqual(spy.count(),1)
                self.assertEqual(LocaleService(runtime.paths.config_dir).locale,'en-US')
                self.assertFalse(bridge.setLocale('invalid'))
                self.assertFalse(any('ReferenceError' in e or 'TypeError' in e for e in errors),errors)
            finally:
                view.close();view.setSource(QUrl());bridge.close();runtime.stop()

if __name__=='__main__':unittest.main()
