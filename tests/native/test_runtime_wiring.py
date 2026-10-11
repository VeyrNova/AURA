import unittest
from pathlib import Path
from aura_native.bootstrap.composition import compose_runtime
from aura_native.ui.qt_bridge import NativeDiagnosticsBridge
from aura_native.weather.qt_bridge import NativeWeatherBridge
from aura_native.ui.music_bridge import NativeMusicBridge
from aura_native.ui.module_composition import NativeModuleComposition
from aura_native.ui.qt_bridge import NativeCoreBridge
from aura_native.mail.qt_bridge import NativeMailBridge
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlEngine
from PySide6.QtTest import QTest
import os
import re

ROOT = Path(__file__).parents[2]

class RuntimeWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        os.environ['AURA_PCC_FAKE']='1'
        cls.app=QApplication.instance() or QApplication([])

    def test_native_composition_and_diagnostics_bridge(self):
        runtime = compose_runtime(project_root=ROOT, state_dir=ROOT / 'tests/native/_evidence/runtime-wiring-state')
        try:
            self.assertIsNotNone(runtime)
            composition=NativeModuleComposition.build(runtime)
            bridge = composition.diagnostics_bridge
            bridge.refreshDiagnostics()
            self.assertTrue(bridge.diagReady)
            self.assertTrue((ROOT/'app/qml/views/DiagnosticsView.qml').is_file())
            self.assertIs(composition.weather_bridge._service,runtime.weather_service)
            self.assertIsInstance(composition.music_bridge,NativeMusicBridge)
            engine=QQmlEngine();composition.install_context(engine.rootContext())
            self.assertIs(engine.rootContext().contextProperty('musicBridge'),composition.music_bridge)
            self.assertIs(engine.rootContext().contextProperty('musicPlaylistModel'),composition.music_bridge.model)
            core=NativeCoreBridge(runtime)
            self.assertIn(core.locale,('fr-FR','en-US'))
            self.assertTrue(callable(core.setLocale))
            self.assertTrue(callable(core.sendMessage))
            self.assertIsInstance(NativeMailBridge(runtime.mail_service), NativeMailBridge)
            self.assertIn('MailView {',(ROOT/'app/qml/views/NativeWorkspaceView.qml').read_text(encoding='utf-8'))
            for name in ('SettingsView.qml','ProviderIntegrationsView.qml','ModulesView.qml'):
                source=(ROOT/'app/qml/views'/name).read_text(encoding='utf-8')
                for member in set(re.findall(r'coreBridge\.([A-Za-z_]\w*)',source)):
                    self.assertTrue(hasattr(core,member),f'{name}: coreBridge.{member}')
            core.close();composition.music_bridge.shutdown()
            composition.music_bridge._player.deleteLater();composition.music_bridge._audio.deleteLater();QTest.qWait(50)
            self.assertTrue((ROOT/'app/qml/views/WeatherView.qml').is_file())
            qml = (ROOT/'app/qml/views/NativeWorkspaceView.qml').read_text(encoding='utf-8')
            self.assertIn('root.workspace === "diagnostics"', qml)
            self.assertTrue(getattr(runtime, 'developer_fabric_service', None))
        finally:
            runtime.stop()

if __name__ == '__main__': unittest.main()
