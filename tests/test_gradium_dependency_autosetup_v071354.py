import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config.settings import settings
from regression_compat import assert_version_at_least
from voice.gradium_dependency import (
    GradiumDependencyStatus,
    PINNED_WEBSOCKETS,
    install_websockets_for_current_aura,
)


class GradiumDependencyAutoSetup071354Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, '0.7.1.3.5.4')

    def test_installer_uses_exact_current_interpreter_and_fixed_pip_command(self):
        absent = GradiumDependencyStatus(False, r'C:\\AURA-PY\\python.exe', '', 'missing')
        ready = GradiumDependencyStatus(True, r'C:\\AURA-PY\\python.exe', PINNED_WEBSOCKETS, 'ready')
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((list(cmd), dict(kwargs)))
            return subprocess.CompletedProcess(cmd, 0, stdout='ok')

        with patch('voice.gradium_dependency.probe_websockets', side_effect=[absent, ready]), \
             patch('voice.gradium_dependency._interpreter', return_value=absent.interpreter), \
             patch('voice.gradium_dependency.subprocess.run', side_effect=fake_run), \
             patch('voice.gradium_dependency.importlib.invalidate_caches'), \
             patch('voice.gradium_dependency.sys.modules', {}):
            result = install_websockets_for_current_aura()

        self.assertTrue(result.ready)
        self.assertEqual(calls[0][0], [absent.interpreter, '-m', 'pip', '--version'])
        self.assertEqual(calls[1][0], [
            absent.interpreter, '-m', 'pip', 'install', '--disable-pip-version-check',
            f'websockets=={PINNED_WEBSOCKETS}',
        ])
        for _, kwargs in calls:
            self.assertFalse(kwargs['shell'])
            self.assertIs(kwargs['stdin'], subprocess.DEVNULL)

    def test_installer_bootstraps_pip_only_when_current_python_has_no_pip(self):
        absent = GradiumDependencyStatus(False, '/aura/python', '', 'missing')
        ready = GradiumDependencyStatus(True, '/aura/python', PINNED_WEBSOCKETS, 'ready')
        outputs = [
            subprocess.CompletedProcess([], 1, stdout='No module named pip'),
            subprocess.CompletedProcess([], 0, stdout='ensurepip ok'),
            subprocess.CompletedProcess([], 0, stdout='install ok'),
        ]
        calls = []
        def fake_run(cmd, **kwargs):
            calls.append(list(cmd)); return outputs.pop(0)
        with patch('voice.gradium_dependency.probe_websockets', side_effect=[absent, ready]), \
             patch('voice.gradium_dependency._interpreter', return_value=absent.interpreter), \
             patch('voice.gradium_dependency.subprocess.run', side_effect=fake_run), \
             patch('voice.gradium_dependency.importlib.invalidate_caches'), \
             patch('voice.gradium_dependency.sys.modules', {}):
            result = install_websockets_for_current_aura()
        self.assertTrue(result.ready)
        self.assertEqual(calls[1], [absent.interpreter, '-m', 'ensurepip', '--upgrade'])

    def test_ui_has_user_triggered_same_interpreter_installer(self):
        source = (settings.BASE_DIR / 'ui' / 'voice_settings_dialog.py').read_text(encoding='utf-8')
        self.assertIn('Installer WebSocket', source)
        self.assertIn('_install_gradium_websocket', source)
        self.assertIn('Python exact d\'AURA', source)
        self.assertIn('install_websockets_for_current_aura', source)

    def test_no_arbitrary_command_surface(self):
        source = (settings.BASE_DIR / 'voice' / 'gradium_dependency.py').read_text(encoding='utf-8')
        self.assertIn('shell=False', source)
        self.assertNotIn('shell=True', source)
        self.assertNotIn('eval(', source)
        self.assertNotIn('exec(', source)
        self.assertNotIn('os.system', source)


if __name__ == '__main__':
    unittest.main()
