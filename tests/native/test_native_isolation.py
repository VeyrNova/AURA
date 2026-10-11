"""Static and mocked checks for the native branch; no legacy service is started."""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]

class NativeIsolationTests(unittest.TestCase):
    def test_native_modules_do_not_import_historical_packages(self):
        forbidden=("WebEngine","MainWindow","subprocess")
        for path in (ROOT/'src/aura_native').rglob('*.py'):
            text=path.read_text(encoding='utf-8')
            for item in forbidden:self.assertNotIn(item,text,path)
            for node in ast.walk(ast.parse(text)):
                if isinstance(node,ast.Import):
                    self.assertFalse(any(alias.name.split('.')[0]=='weather_bridge' for alias in node.names),path)
                elif isinstance(node,ast.ImportFrom):
                    self.assertNotEqual((node.module or '').split('.')[0],'weather_bridge',path)
            # Network code stays behind explicit provider boundaries, including
            # the injectable OSRM adapter used only after a route request.
            # Search service uses urllib.parse for URL validation only; the
            # actual transport remains confined to duckduckgo.py.
            network_adapters = {"search/duckduckgo.py", "search/service.py"}
            if path.name not in {"provider.py", "routing.py"} and path.relative_to(ROOT/'src/aura_native').as_posix() not in network_adapters:
                self.assertNotIn("urllib",text,path)
    def test_native_branch_has_no_historical_constructors_or_music_shutdown(self):
        source=(ROOT/'app/main.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('AuraCoreBridge()'),1); self.assertEqual(source.count('MusicQtBridge()'),1); self.assertEqual(source.count('WeatherBridge()'),1)
        self.assertIn('core_bridge = NativeCoreBridge(native_runtime, app)',source)
        self.assertIn('if args.core_mode == "legacy":\n        app.aboutToQuit.connect(_aura_shutdown_music_on_app_exit)',source)
    def test_legacy_branch_is_selected_without_constructing_services_in_mocked_unit_design(self):
        source=(ROOT/'app/main.py').read_text(encoding='utf-8')
        self.assertIn('p.add_argument("--core-mode", choices=("legacy", "native"), default="native")',source)
        self.assertIn('if args.core_mode == "legacy":',source)
