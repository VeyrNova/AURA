import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from config.settings import settings
from regression_compat import assert_version_at_least
from voice.elevenlabs_tts import ElevenLabsTTS


class _Response:
    def __init__(self, payload):
        self.data = json.dumps(payload).encode('utf-8')
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, *args):
        return self.data


def _http_error(url, code, payload):
    return urllib.error.HTTPError(
        url=url,
        code=code,
        msg='error',
        hdrs=None,
        fp=io.BytesIO(json.dumps(payload).encode('utf-8')),
    )


class ElevenLabsAPIDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.old_key = settings.ELEVENLABS_API_KEY
        settings.ELEVENLABS_API_KEY = 'test-secret-key-123456'
        ElevenLabsTTS._voices_cache = (0.0, ())
        ElevenLabsTTS._quota_cache = (0.0, {})

    def tearDown(self):
        settings.ELEVENLABS_API_KEY = self.old_key

    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, '0.7.1.3.4.4')

    def test_http_detail_extracts_status_and_message_and_redacts_secret(self):
        exc = _http_error(
            'https://api.elevenlabs.io/v2/voices',
            400,
            {'detail': {'status': 'bad_request', 'message': 'secret test-secret-key-123456 rejected'}},
        )
        detail = ElevenLabsTTS._safe_http_error_detail(exc)
        self.assertIn('bad_request', detail)
        self.assertIn('[REDACTED]', detail)
        self.assertNotIn('test-secret-key-123456', detail)

    def test_voice_list_retries_simplified_v2_after_400(self):
        first = _http_error(
            'https://api.elevenlabs.io/v2/voices?page_size=100&sort=name&sort_direction=asc',
            400,
            {'detail': {'status': 'invalid_query', 'message': 'sort rejected'}},
        )
        second = _Response({'voices': [{'voice_id': 'abc', 'name': 'Aura Test', 'category': 'premade'}]})
        with patch('voice.elevenlabs_tts.urllib.request.urlopen', side_effect=[first, second]) as mocked:
            voices = ElevenLabsTTS.list_voices(force_refresh=True)
        self.assertEqual(len(voices), 1)
        self.assertEqual(voices[0].voice_id, 'abc')
        self.assertEqual(mocked.call_count, 2)
        second_url = mocked.call_args_list[1].args[0].full_url
        self.assertIn('/v2/voices?page_size=100', second_url)
        self.assertNotIn('sort=', second_url)

    def test_voice_list_falls_back_to_legacy_v1_after_v2_client_errors(self):
        errors = [
            _http_error('https://api.elevenlabs.io/v2/voices?a=1', 400, {'detail': 'bad query'}),
            _http_error('https://api.elevenlabs.io/v2/voices?page_size=100', 422, {'detail': 'unsupported'}),
        ]
        response = _Response({'voices': [{'voice_id': 'legacy', 'name': 'Legacy Voice'}]})
        with patch('voice.elevenlabs_tts.urllib.request.urlopen', side_effect=errors + [response]) as mocked:
            voices = ElevenLabsTTS.list_voices(force_refresh=True)
        self.assertEqual(voices[0].voice_id, 'legacy')
        self.assertTrue(mocked.call_args_list[2].args[0].full_url.endswith('/v1/voices'))

    def test_api_diagnostics_is_read_only_and_reports_each_endpoint(self):
        responses = [
            _Response({'user_id': 'u'}),
            _Response({'character_count': 1, 'character_limit': 10000}),
            _http_error('https://api.elevenlabs.io/v2/voices?page_size=1', 400, {'detail': {'status': 'bad', 'message': 'voices unavailable'}}),
        ]
        with patch('voice.elevenlabs_tts.urllib.request.urlopen', side_effect=responses) as mocked:
            result = ElevenLabsTTS.api_diagnostics()
        self.assertTrue(result['user']['ok'])
        self.assertTrue(result['quota']['ok'])
        self.assertFalse(result['voices']['ok'])
        self.assertEqual(result['voices']['http'], 400)
        self.assertEqual(mocked.call_count, 3)
        self.assertTrue(all(call.args[0].method == 'GET' for call in mocked.call_args_list))

    def test_dialog_contains_diagnostic_summary(self):
        source = (settings.BASE_DIR / 'ui' / 'voice_settings_dialog.py').read_text(encoding='utf-8')
        self.assertIn('ElevenLabsTTS.api_diagnostics()', source)
        self.assertIn('Diagnostic lecture seule', source)
        self.assertIn('Authentification', source)


if __name__ == '__main__':
    unittest.main()
