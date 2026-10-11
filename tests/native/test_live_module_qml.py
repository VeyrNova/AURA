"""Exercise actual native module views with local collectors and a fake forecast."""
import os
import time
import unittest
from pathlib import Path
from PySide6.QtCore import QUrl, QObject
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from aura_native.diagnostics.service import DiagnosticsService
from aura_native.ui.qt_bridge import NativeDiagnosticsBridge
from aura_native.weather.service import WeatherService
from aura_native.weather.provider import FakeWeatherProvider
from aura_native.weather.qt_bridge import NativeWeatherBridge

ROOT=Path(__file__).parents[2]

class ModuleQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.app=QApplication.instance() or QApplication([])

    def _load(self, name, context_name, bridge):
        engine=QQmlApplicationEngine()
        engine.rootContext().setContextProperty(context_name,bridge)
        engine.rootContext().setContextProperty('auraAssetBase',QUrl.fromLocalFile(str(ROOT/'app/assets')+os.sep).toString())
        engine.load(QUrl.fromLocalFile(str(ROOT/'app/qml/views'/name)))
        self.assertTrue(engine.rootObjects(), name)
        root=engine.rootObjects()[0]
        root.setProperty('width',1100); root.setProperty('height',750)
        return engine,root

    def test_diagnostics_real_value_reaches_view(self):
        bridge=NativeDiagnosticsBridge(service=DiagnosticsService())
        engine,root=self._load('DiagnosticsView.qml','diagnosticsBridge',bridge)
        bridge.refreshDiagnostics(); self.app.processEvents()
        self.assertTrue(bridge.diagReady)
        self.assertNotIn(bridge.diagCpuText,('Unavailable','ERROR'))
        visible_text=[str(obj.property('text')) for obj in root.findChildren(QObject) if obj.property('text') is not None]
        self.assertTrue(any(f'{round(bridge.diagRamPercent)}%' in text for text in visible_text), visible_text)
        self.assertTrue(any(bridge.diagDownloadText in text for text in visible_text), visible_text)
        del engine

    def test_fake_weather_value_reaches_view(self):
        fake=FakeWeatherProvider()
        bridge=NativeWeatherBridge(WeatherService(fake))
        engine,root=self._load('WeatherView.qml','weatherBridge',bridge)
        bridge.searchCity('Nice')
        for _ in range(200):
            self.app.processEvents()
            if not bridge.loading: break
            time.sleep(.005)
        self.assertEqual(bridge.temperature,20.0)
        texts=[str(obj.property('text')) for obj in root.findChildren(QObject) if obj.property('text') is not None]
        self.assertTrue(any('Nice' in text for text in texts),texts[:10])
        self.assertTrue(any('20' in text for text in texts), texts[:30])
        del engine

if __name__=='__main__': unittest.main()
