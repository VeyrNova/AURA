import tempfile
import unittest
from pathlib import Path

from config.settings import persist_local_env_value, settings
from regression_compat import assert_version_at_least


class ElevenLabsVoiceSettingsTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, '0.7.1.3.4.1')

    def test_secret_persist_replaces_single_env_entry(self):
        with tempfile.TemporaryDirectory() as td:
            env_path = Path(td) / '.env'
            env_path.write_text('FOO=bar\nELEVENLABS_API_KEY=old\n# keep\n', encoding='utf-8')
            persist_local_env_value('ELEVENLABS_API_KEY', 'new-secret', env_path=env_path)
            text = env_path.read_text(encoding='utf-8')
            self.assertIn('FOO=bar', text)
            self.assertIn('# keep', text)
            self.assertEqual(text.count('ELEVENLABS_API_KEY='), 1)
            self.assertIn('ELEVENLABS_API_KEY=new-secret', text)

    def test_secret_persist_rejects_newline_injection(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                persist_local_env_value('ELEVENLABS_API_KEY', 'abc\nOTHER=bad', env_path=Path(td) / '.env')

    def test_dialog_source_exposes_first_time_key_configuration(self):
        source = (settings.BASE_DIR / 'ui' / 'voice_settings_dialog.py').read_text(encoding='utf-8')
        self.assertIn('QLineEdit.Password', source)
        self.assertIn('Clé ElevenLabs', source)
        self.assertIn('_apply_elevenlabs_key_and_refresh', source)
        self.assertIn('self.eleven_key_edit.setEnabled(True)', source)
        self.assertIn('settings.ELEVENLABS_API_KEY = entered', source)


if __name__ == '__main__':
    unittest.main()
