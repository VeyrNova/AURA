import json
import unittest
from unittest.mock import patch

from config.settings import settings
from regression_compat import assert_version_at_least
from voice.gradium_tts import GradiumTTS
from voice.resemble_tts import ResembleTTS


class _Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self, *args, **kwargs):
        return json.dumps(self.payload).encode('utf-8')


class MultiProviderVoiceSelector071351Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, '0.7.1.3.5.1')

    def test_gradium_requests_public_catalog(self):
        old_key = settings.GRADIUM_API_KEY
        old_catalog = settings.GRADIUM_INCLUDE_CATALOG
        settings.GRADIUM_API_KEY = 'gradium-secret-123456'
        settings.GRADIUM_INCLUDE_CATALOG = True
        GradiumTTS._voices_cache = (0.0, ())
        seen = {}
        def fake_urlopen(req, timeout=None):
            seen['url'] = req.full_url
            return _Response([
                {'uid': 'fr1', 'name': 'Claire', 'language': 'fr', 'is_catalog': True},
                {'uid': 'en1', 'name': 'Emma', 'language': 'en', 'is_catalog': True},
            ])
        try:
            with patch('voice.gradium_tts.urllib.request.urlopen', side_effect=fake_urlopen):
                voices = GradiumTTS.list_voices(force_refresh=True)
            self.assertIn('include_catalog=true', seen['url'])
            self.assertIn('limit=500', seen['url'])
            self.assertEqual([v.voice_id for v in voices], ['fr1', 'en1'])
        finally:
            settings.GRADIUM_API_KEY = old_key
            settings.GRADIUM_INCLUDE_CATALOG = old_catalog
            GradiumTTS._voices_cache = (0.0, ())

    def test_resemble_list_parser_keeps_accessible_voices(self):
        old_key = settings.RESEMBLE_API_KEY
        settings.RESEMBLE_API_KEY = 'resemble-secret-123456'
        ResembleTTS._voices_cache = (0.0, ())
        payload = {'success': True, 'items': [
            {'uuid': 'r1', 'name': 'French Voice', 'default_language': 'fr-FR', 'source': 'Resemble Voice'},
            {'uuid': 'r2', 'name': 'Custom Voice', 'default_language': 'en-US', 'source': 'Custom Voice'},
        ]}
        try:
            seen = {}
            def fake_resemble(req, timeout=None):
                seen['url'] = req.full_url
                return _Response(payload)
            with patch('voice.resemble_tts.urllib.request.urlopen', side_effect=fake_resemble):
                voices = ResembleTTS.list_voices(force_refresh=True)
            self.assertIn('page_size=1000', seen['url'])
            self.assertEqual(len(voices), 2)
            self.assertEqual(voices[0].voice_uuid, 'r1')
            self.assertEqual(voices[1].voice_uuid, 'r2')
        finally:
            settings.RESEMBLE_API_KEY = old_key
            ResembleTTS._voices_cache = (0.0, ())

    def test_dialog_auto_refreshes_after_provider_apply(self):
        source = (settings.BASE_DIR / 'ui' / 'voice_settings_dialog.py').read_text(encoding='utf-8')
        self.assertIn('refresh_after: bool = True', source)
        self.assertIn('self._refresh_gradium_voices(secret_already_applied=True)', source)
        self.assertIn('self._refresh_resemble_voices(secret_already_applied=True)', source)
        self.assertIn('Gradium selector populated voices=%d', source)
        self.assertIn('Resemble selector populated voices=%d', source)

    def test_provider_setup_is_not_locked_to_active_engine(self):
        source = (settings.BASE_DIR / 'ui' / 'voice_settings_dialog.py').read_text(encoding='utf-8')
        self.assertIn('def _update_provider_setup_state', source)
        self.assertIn('edit.setEnabled(True)', source)
        self.assertIn('refresh_button.setEnabled(saved or entered_valid)', source)


if __name__ == '__main__':
    unittest.main()
