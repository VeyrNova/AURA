import sys
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch

from config.settings import settings
from voice.voice_profile import VoiceProfile
from voice.xtts_tts import XTTSTTS

ROOT = Path(__file__).resolve().parents[1]


class _WarmRawStream:
    instances = []
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.closed = False
        self.payloads = []
        self.__class__.instances.append(self)
    def start(self): self.started = True
    def write(self, payload):
        # Simulate a small real-time device write; the persistent bridge keeps
        # this cost outside model generation and never reopens the endpoint.
        time.sleep(0.002)
        self.payloads.append(bytes(payload))
    def stop(self): return None
    def abort(self): return None
    def close(self): self.closed = True


class _FastModel:
    def __init__(self):
        self.speaker_manager = SimpleNamespace(speakers={
            'Ana Florence': {
                'gpt_cond_latent': torch.zeros(1,4,8),
                'speaker_embedding': torch.zeros(1,512,1),
            }
        })
    def inference_stream(self, *args, **kwargs):
        for n in (1200, 1200, 600):
            yield torch.linspace(-0.1, 0.1, n)


class XTTSPersistentAudioBridgeV071365Tests(unittest.TestCase):
    def setUp(self):
        XTTSTTS._conditioning_cache.clear()
        XTTSTTS._shared_audio_bridge = None
        _WarmRawStream.instances.clear()

    def tearDown(self):
        bridge = XTTSTTS._shared_audio_bridge
        XTTSTTS._shared_audio_bridge = None
        if bridge is not None:
            bridge.close()
        XTTSTTS._conditioning_cache.clear()

    def test_version(self):
        self.assertEqual(settings.APP_VERSION, '0.7.2')

    def test_silent_warmup_primes_persistent_audio_endpoint(self):
        backend = XTTSTTS(VoiceProfile(xtts_mode='preset', xtts_preset='Ana Florence', xtts_language='fr'))
        backend._device = 'cuda'
        model = _FastModel()
        api = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        fake_sd = types.SimpleNamespace(RawOutputStream=_WarmRawStream)
        with patch.object(backend, '_load_model', return_value=api), patch.dict(sys.modules, {'sounddevice': fake_sd}):
            result = backend.native_silent_warmup('Prêt.')
        self.assertTrue(result['audio_bridge_ready'])
        self.assertTrue(XTTSTTS._persistent_bridge_ready())
        self.assertEqual(len(_WarmRawStream.instances), 1)
        self.assertTrue(_WarmRawStream.instances[0].started)

    def test_speech_reuses_warm_stream_without_reopen(self):
        backend = XTTSTTS(VoiceProfile(xtts_mode='preset', xtts_preset='Ana Florence', xtts_language='fr'))
        backend._device = 'cuda'
        model = _FastModel()
        api = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        fake_sd = types.SimpleNamespace(RawOutputStream=_WarmRawStream)
        with patch.object(backend, '_load_model', return_value=api), patch.dict(sys.modules, {'sounddevice': fake_sd}):
            self.assertTrue(backend._prepare_persistent_audio_bridge())
            before = len(_WarmRawStream.instances)
            metrics = backend._speak_native_stream('Bonjour Aura')
            after = len(_WarmRawStream.instances)
        self.assertEqual(before, 1)
        self.assertEqual(after, 1)
        self.assertEqual(metrics.chunk_count, 3)
        self.assertTrue(metrics.progressive)
        self.assertGreater(metrics.time_to_audio_seconds, 0.0)

    def test_release_shared_model_closes_audio_bridge(self):
        backend = XTTSTTS(VoiceProfile(xtts_mode='preset', xtts_preset='Ana Florence', xtts_language='fr'))
        fake_sd = types.SimpleNamespace(RawOutputStream=_WarmRawStream)
        with patch.dict(sys.modules, {'sounddevice': fake_sd}):
            self.assertTrue(backend._prepare_persistent_audio_bridge())
        bridge = XTTSTTS._shared_audio_bridge
        XTTSTTS._shared_api = object()
        XTTSTTS._shared_device = 'cpu'
        self.assertTrue(XTTSTTS.release_shared_model())
        self.assertIsNone(XTTSTTS._shared_audio_bridge)
        self.assertFalse(bridge.alive)


    def test_idle_stopped_stream_retires_without_worker_traceback(self):
        class _StoppedStream(_WarmRawStream):
            def write(self, payload):
                raise RuntimeError("Stream is stopped")
            def start(self):
                if self.started:
                    raise RuntimeError("Stream is stopped")
                self.started = True

        fake_sd = types.SimpleNamespace(RawOutputStream=_StoppedStream)
        backend = XTTSTTS(VoiceProfile(xtts_mode='preset', xtts_preset='Ana Florence', xtts_language='fr'))
        with patch.dict(sys.modules, {'sounddevice': fake_sd}):
            self.assertTrue(backend._prepare_persistent_audio_bridge())
        bridge = XTTSTTS._shared_audio_bridge
        deadline = time.time() + 0.5
        while bridge.alive and time.time() < deadline:
            time.sleep(0.01)
        self.assertFalse(bridge.alive)

    def test_logging_exposes_bridge_delay(self):
        source = (ROOT/'voice/xtts_tts.py').read_text(encoding='utf-8')
        self.assertIn('audio_bridge_delay=%.3fs', source)
        self.assertIn('persistent_stream=True', source)
        self.assertIn('aura-xtts-audio-bridge', source)


if __name__ == '__main__':
    unittest.main()
