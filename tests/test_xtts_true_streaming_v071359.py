import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import torch

from config.settings import settings
from voice.voice_profile import VoiceProfile
from voice.xtts_tts import XTTSTTS


class _FakeRawStream:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.closed = False
        self.payloads = []
        self.__class__.instances.append(self)

    def start(self):
        self.started = True

    def write(self, payload):
        self.payloads.append(bytes(payload))

    def stop(self):
        return None

    def abort(self):
        return None

    def close(self):
        self.closed = True


class _FakeModel:
    def __init__(self):
        self.speaker_manager = SimpleNamespace(
            speakers={
                "Ana Florence": {
                    "gpt_cond_latent": torch.zeros(1, 4, 8),
                    "speaker_embedding": torch.zeros(1, 512, 1),
                }
            }
        )
        self.calls = []

    def inference_stream(self, text, language, gpt_cond, speaker_emb, **kwargs):
        self.calls.append((text, language, kwargs))
        yield torch.linspace(-0.1, 0.1, 2400)
        yield torch.linspace(-0.1, 0.1, 2400)
        yield torch.linspace(-0.1, 0.1, 1200)


class XTTSNativeStreamingV071359Tests(unittest.TestCase):
    def setUp(self):
        XTTSTTS._conditioning_cache.clear()
        _FakeRawStream.instances.clear()

    def tearDown(self):
        XTTSTTS._conditioning_cache.clear()

    def _backend(self):
        backend = XTTSTTS(VoiceProfile(xtts_mode="preset", xtts_preset="Ana Florence", xtts_language="fr"))
        backend._device = "cuda"
        return backend

    def test_native_stream_plays_multiple_chunks_without_temp_wav(self):
        backend = self._backend()
        model = _FakeModel()
        api = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        fake_sd = types.SimpleNamespace(RawOutputStream=_FakeRawStream)
        with patch.object(backend, "_load_model", return_value=api), \
             patch.dict(sys.modules, {"sounddevice": fake_sd}), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "FAST_SPEECH_NATIVE_STREAMING", True):
            metrics = backend._speak_native_stream("Bonjour Aura")
        self.assertTrue(metrics.progressive)
        self.assertEqual(metrics.chunk_count, 3)
        self.assertGreater(metrics.first_chunk_synthesis_seconds, 0.0)
        self.assertGreater(metrics.time_to_audio_seconds, 0.0)
        self.assertEqual(len(_FakeRawStream.instances), 1)
        self.assertEqual(len(_FakeRawStream.instances[0].payloads), 3)
        self.assertEqual(model.calls[0][1], "fr")
        self.assertEqual(model.calls[0][2]["stream_chunk_size"], settings.XTTS_NATIVE_STREAM_CHUNK_SIZE)

    def test_preset_conditioning_is_cached(self):
        backend = self._backend()
        model = _FakeModel()
        api = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        first, first_hit = backend._native_conditioning(api)
        model.speaker_manager.speakers.clear()
        second, second_hit = backend._native_conditioning(api)
        self.assertFalse(first_hit)
        self.assertTrue(second_hit)
        self.assertIs(first[0], second[0])
        self.assertIs(first[1], second[1])

    def test_custom_conditioning_computed_only_once(self):
        backend = XTTSTTS(VoiceProfile(
            xtts_mode="custom", xtts_speaker_id="AURA_CUSTOM",
            xtts_reference_wav="C:/voice/ref.wav", xtts_language="fr",
        ))
        backend._device = "cuda"
        model = _FakeModel()
        calls = []
        def conditioning(audio_path):
            calls.append(tuple(audio_path))
            return torch.ones(1, 4, 8), torch.ones(1, 512, 1)
        model.get_conditioning_latents = conditioning
        api = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        backend._native_conditioning(api)
        backend._native_conditioning(api)
        self.assertEqual(calls, [("C:/voice/ref.wav",)])

    def test_release_shared_model_clears_conditioning_cache(self):
        XTTSTTS._conditioning_cache[("preset", "Ana Florence", "", "fr")] = (object(), object())
        XTTSTTS._shared_api = object()
        XTTSTTS._shared_device = "cpu"
        self.assertTrue(XTTSTTS.release_shared_model())
        self.assertEqual(XTTSTTS._conditioning_cache, {})


if __name__ == "__main__":
    unittest.main()
