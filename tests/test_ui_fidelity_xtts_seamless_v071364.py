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


class _BlockingRawStream:
    instances = []
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.payloads = []
        self.started = False
        self.closed = False
        self.__class__.instances.append(self)
    def start(self): self.started = True
    def write(self, payload):
        time.sleep(0.05)
        self.payloads.append(bytes(payload))
    def stop(self): return None
    def abort(self): return None
    def close(self): self.closed = True


class _FastProducerModel:
    def __init__(self):
        self.speaker_manager = SimpleNamespace(speakers={
            'Ana Florence': {
                'gpt_cond_latent': torch.zeros(1,4,8),
                'speaker_embedding': torch.zeros(1,512,1),
            }
        })
    def inference_stream(self, *args, **kwargs):
        for n in (2400, 2400, 1200):
            yield torch.linspace(-0.1, 0.1, n)


class UIFidelityXTTSSeamlessV071364Tests(unittest.TestCase):
    def setUp(self):
        XTTSTTS._conditioning_cache.clear()
        _BlockingRawStream.instances.clear()

    def tearDown(self):
        XTTSTTS._conditioning_cache.clear()

    def test_version(self):
        self.assertEqual(settings.APP_VERSION, '0.7.2')

    def test_opengl_low_motion_keeps_cinematic_orb(self):
        source = (ROOT / 'ui' / 'opengl_orb_surface.py').read_text(encoding='utf-8')
        self.assertIn('self._dynamic_low_motion_confirmations += 1', source)
        self.assertIn('OpenGL cinematic lock retained', source)
        self.assertIn('QTimer.singleShot(1800, self._validate_dynamic_output)', source)
        self.assertIn('cinematic-eco', source)
        block = source[source.index('def _validate_dynamic_output'):source.index('def _set_adaptive_visual_quality')]
        self.assertNotIn('initialization_failed.emit', block)

    def test_native_audio_playback_does_not_block_cuda_producer(self):
        backend = XTTSTTS(VoiceProfile(xtts_mode='preset', xtts_preset='Ana Florence', xtts_language='fr'))
        backend._device = 'cuda'
        model = _FastProducerModel()
        api = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        fake_sd = types.SimpleNamespace(RawOutputStream=_BlockingRawStream)
        with patch.object(backend, '_load_model', return_value=api), \
             patch.dict(sys.modules, {'sounddevice': fake_sd}), \
             patch.object(settings, 'XTTS_ALLOW_CUDA', True), \
             patch.object(settings, 'FAST_SPEECH_NATIVE_STREAMING', True):
            metrics = backend._speak_native_stream('Bonjour Aura')
        self.assertEqual(metrics.chunk_count, 3)
        self.assertEqual(len(_BlockingRawStream.instances[0].payloads), 3)
        # Playback intentionally blocks for ~150 ms. CUDA production must finish
        # independently instead of inheriting those write delays.
        self.assertLess(metrics.synthesis_seconds, 0.10)
        self.assertGreater(metrics.total_seconds, 0.13)
        self.assertTrue(metrics.progressive)

    def test_streaming_log_marks_seamless_queue(self):
        source = (ROOT / 'voice' / 'xtts_tts.py').read_text(encoding='utf-8')
        self.assertIn('mode=producer-consumer', source)
        self.assertIn('seamless_queue=True', source)
        self.assertIn('aura-xtts-playback', source)


if __name__ == '__main__':
    unittest.main()
