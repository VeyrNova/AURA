import base64
import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config.settings import settings
from regression_compat import assert_version_at_least
from voice.gradium_tts import GradiumTTS, GradiumSynthesisMetrics
from scripts.voice_cloud_benchmark_report import parse_samples, report


class _RawOutputStream:
    def __init__(self, *args, **kwargs):
        self.writes = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def write(self, data): self.writes.append(bytes(data))


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.closed = False
        self._replies = []
    def send(self, data):
        self.sent.append(json.loads(data))
        if self.sent[-1].get('type') == 'setup':
            self._replies.append(json.dumps({'type': 'ready'}))
        elif self.sent[-1].get('type') == 'end_of_stream':
            audio = base64.b64encode(b'\x00\x00' * 80).decode('ascii')
            self._replies.extend([json.dumps({'type': 'audio', 'audio': audio}), json.dumps({'type': 'end_of_stream'})])
    def recv(self, timeout=None):
        if not self._replies:
            raise AssertionError('no queued websocket reply')
        return self._replies.pop(0)
    def close(self): self.closed = True


class GradiumRealtime071353Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, '0.7.1.3.5.3')

    def _modules(self, connect):
        ws = types.ModuleType('websockets')
        sync = types.ModuleType('websockets.sync')
        client = types.ModuleType('websockets.sync.client')
        client.connect = connect
        ws.sync = sync
        sync.client = client
        sd = types.ModuleType('sounddevice')
        sd.RawOutputStream = _RawOutputStream
        return {'websockets': ws, 'websockets.sync': sync, 'websockets.sync.client': client, 'sounddevice': sd}

    def test_persistent_websocket_is_reused_and_metrics_are_exposed(self):
        profile = SimpleNamespace(gradium_voice_id='voice-fr', gradium_model='default')
        backend = GradiumTTS(profile)
        fake = _FakeWS()
        calls = []
        def connect(*args, **kwargs):
            calls.append((args, kwargs))
            return fake
        with patch.dict(sys.modules, self._modules(connect), clear=False):
            first = backend._speak_websocket('Bonjour Aura')
            second = backend._speak_websocket('Encore bonjour')
        self.assertIsInstance(first, GradiumSynthesisMetrics)
        self.assertEqual(first.transport, 'websocket')
        self.assertFalse(first.connection_reused)
        self.assertTrue(first.streaming)
        self.assertGreaterEqual(first.chunk_count, 1)
        self.assertTrue(second.connection_reused)
        self.assertEqual(len(calls), 1)
        setups = [m for m in fake.sent if m.get('type') == 'setup']
        self.assertEqual(len(setups), 2)
        self.assertFalse(setups[0]['close_ws_on_eos'])
        backend.stop()
        self.assertTrue(fake.closed)

    def test_dependency_probe_uses_sync_client(self):
        with patch.dict(sys.modules, self._modules(lambda *a, **k: _FakeWS()), clear=False):
            self.assertTrue(GradiumTTS.websocket_dependency_available())

    def test_voice_requirements_pin_websockets(self):
        root = settings.BASE_DIR
        self.assertIn('websockets>=16.1,<17', (root / 'requirements-voice.txt').read_text(encoding='utf-8'))
        self.assertIn('websockets==16.1.1', (root / 'requirements-voice-pinned.txt').read_text(encoding='utf-8'))
        self.assertTrue((root / 'INSTALL_GRADIUM_REALTIME.bat').exists())

    def test_ui_exposes_transport_state(self):
        source = (settings.BASE_DIR / 'ui' / 'voice_settings_dialog.py').read_text(encoding='utf-8')
        self.assertIn('Transport Gradium', source)
        self.assertIn('INSTALL_GRADIUM_REALTIME.bat', source)
        self.assertIn('connexion persistante', source)

    def test_read_only_benchmark_parses_gradium_and_elevenlabs(self):
        text = '\n'.join([
            'INFO Gradium TTS transport=websocket chars=52 connect=0.123s reused=False first_packet=0.250s first_audio=0.260s total=3.000s chunks=4 pcm_bytes=100',
            'INFO Gradium TTS transport=rest chars=52 first_audio=1.900s total=6.000s pcm_bytes=100',
            'INFO ElevenLabs TTS voice=x model=y chars=52 ttfa=0.550s total=3.400s pcm_bytes=100',
        ])
        samples = parse_samples(text)
        self.assertEqual(len(samples), 3)
        out = report(samples)
        self.assertIn('Gradium', out)
        self.assertIn('ElevenLabs', out)
        self.assertIn('websocket', out)


if __name__ == '__main__':
    unittest.main()
