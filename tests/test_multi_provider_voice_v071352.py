import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from config.settings import settings
from regression_compat import assert_version_at_least
from voice.gradium_tts import GradiumTTS
from voice.resemble_tts import ResembleTTS


class _Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def read(self, *args, **kwargs): return json.dumps(self.payload).encode('utf-8')


class MultiProviderVoice071352Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, '0.7.1.3.5.2')

    def test_gradium_missing_websockets_falls_back_to_rest(self):
        profile = SimpleNamespace(gradium_voice_id='voice-1', gradium_model='default')
        backend = GradiumTTS(profile)
        old_enabled, old_key, old_prefer = settings.GRADIUM_ENABLED, settings.GRADIUM_API_KEY, settings.GRADIUM_PREFER_WEBSOCKET
        settings.GRADIUM_ENABLED = True
        settings.GRADIUM_API_KEY = 'gradium-secret-123456'
        settings.GRADIUM_PREFER_WEBSOCKET = True
        sentinel = object()
        try:
            with patch.object(backend, 'is_available', return_value=True), \
                 patch.object(backend, '_speak_websocket_async', new=AsyncMock(side_effect=ModuleNotFoundError('websockets'))), \
                 patch.object(backend, '_speak_rest', return_value=sentinel) as rest:
                result = backend.speak('Bonjour Aura')
            self.assertIs(result, sentinel)
            rest.assert_called_once()
        finally:
            settings.GRADIUM_ENABLED, settings.GRADIUM_API_KEY, settings.GRADIUM_PREFER_WEBSOCKET = old_enabled, old_key, old_prefer

    def test_resemble_uses_supported_languages_for_french(self):
        old_key = settings.RESEMBLE_API_KEY
        settings.RESEMBLE_API_KEY = 'resemble-secret-123456'
        ResembleTTS._voices_cache = (0.0, ())
        payload = {'success': True, 'items': [
            {'uuid': 'multi', 'name': 'Multilingual', 'default_language': 'en-US', 'supported_languages': ['en-US', 'fr-FR'], 'sample_url': 'https://example.test/sample.wav'},
            {'uuid': 'english', 'name': 'English', 'default_language': 'en-US', 'supported_languages': ['en-US']},
        ]}
        seen = {}
        def fake(req, timeout=None):
            seen['url'] = req.full_url
            return _Response(payload)
        try:
            with patch('voice.resemble_tts.urllib.request.urlopen', side_effect=fake):
                voices = ResembleTTS.list_voices(force_refresh=True)
            self.assertIn('advanced=true', seen['url'])
            self.assertIn('sample_url=true', seen['url'])
            self.assertIn('filters=true', seen['url'])
            self.assertEqual(voices[0].voice_uuid, 'multi')
            self.assertTrue(voices[0].supports_french)
            self.assertEqual(voices[0].sample_url, 'https://example.test/sample.wav')
            self.assertFalse(voices[1].supports_french)
        finally:
            settings.RESEMBLE_API_KEY = old_key
            ResembleTTS._voices_cache = (0.0, ())

    def test_resemble_dialog_has_french_filter(self):
        source = (settings.BASE_DIR / 'ui' / 'voice_settings_dialog.py').read_text(encoding='utf-8')
        self.assertIn('self.resemble_language_combo.addItem("Français", "fr")', source)
        self.assertIn('voice.supports_french', source)
        self.assertIn('compatibles français', source)

    def test_resemble_credit_exhaustion_message_is_explicit(self):
        source = (settings.BASE_DIR / 'voice' / 'resemble_tts.py').read_text(encoding='utf-8')
        self.assertIn('crédits TTS épuisés', source)


if __name__ == '__main__':
    unittest.main()
