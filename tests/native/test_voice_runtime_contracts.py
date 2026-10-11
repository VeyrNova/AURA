from __future__ import annotations
import importlib, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'src'))
import unittest
from aura_native.voice.providers import ASSISTANT_CONTEXT_PROMPT, ASSISTANT_NAME, SoundDeviceAudioInput, WhisperSTTProvider, PiperTTSProvider
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np


class _FakeDefault:
    device = (1, 9)


class _FakeSoundDevice:
    default = _FakeDefault()
    devices = [
        {"name": "bad default", "max_input_channels": 1, "default_samplerate": 48000},
        {"name": "compatible", "max_input_channels": 2, "default_samplerate": 48000},
    ]
    @classmethod
    def query_devices(cls): return cls.devices
    @staticmethod
    def check_input_settings(*, device, samplerate, channels, dtype):
        if device == 0: raise ValueError("incompatible")


class _FakeStream:
    def __init__(self, owner, **kwargs):
        self.owner=owner; self.kwargs=kwargs; self.closed=False
    def start(self): self.owner.started_device=self.kwargs["device"]
    def stop(self): pass
    def close(self): self.closed=True

class VoiceRuntimeContractTests(unittest.TestCase):
    def test_faster_whisper_segment_generator_is_consumed(self):
        provider=WhisperSTTProvider(model_path="local")
        seen={}
        provider._model=SimpleNamespace(
            transcribe=lambda audio, language, task, **kwargs: (seen.update(kwargs) or (
                iter([SimpleNamespace(text=" bonjour"),SimpleNamespace(text=" AURA ")]),
                SimpleNamespace())),
        )
        result=provider.transcribe(np.ones(1600,dtype=np.float32))
        self.assertEqual(result,"bonjour AURA")
        self.assertNotIn("generator object",result)
        self.assertEqual(seen["hotwords"], ASSISTANT_NAME)
        self.assertEqual(seen["initial_prompt"], ASSISTANT_CONTEXT_PROMPT)
        self.assertEqual(provider._bias_method, "hotwords+initial_prompt")

    def test_legitimate_au_revoir_is_not_rewritten(self):
        provider=WhisperSTTProvider(model_path="local")
        provider._model=SimpleNamespace(
            transcribe=lambda audio, language, task, **kwargs: ("au revoir", SimpleNamespace())
        )
        self.assertEqual(provider.transcribe(np.ones(1600,dtype=np.float32)), "au revoir")

    def test_faster_whisper_empty_generator_returns_empty_text(self):
        provider=WhisperSTTProvider(model_path="local")
        provider._model=SimpleNamespace(transcribe=lambda audio, language, task: (iter(()), SimpleNamespace()))
        self.assertEqual(provider.transcribe(np.ones(1600,dtype=np.float32)),"")

    def test_audio_stop_returns_mono_float32_samples(self):
        adapter=SoundDeviceAudioInput(samplerate=16000,channels=1)
        adapter._frames=[np.ones((800,1),dtype=np.float32),np.ones((800,1),dtype=np.float32)]
        audio=adapter.stop()
        self.assertEqual(audio.shape,(1600,))
        self.assertEqual(audio.dtype,np.float32)
    def test_import_is_side_effect_free_and_audio_is_lazy(self):
        importlib.import_module('aura_native.voice')
        adapter=SoundDeviceAudioInput(); self.assertIsNone(adapter._stream); self.assertFalse(adapter._started)
    def test_optional_providers_fail_closed_without_download(self):
        with self.assertRaisesRegex(RuntimeError,'MODEL_MISSING'): WhisperSTTProvider().initialize()
        self.assertFalse(PiperTTSProvider().is_available())
    def test_device_listing_is_explicit_and_unavailable_safe(self):
        try: devices=SoundDeviceAudioInput.list_input_devices()
        except RuntimeError: devices=[]
        self.assertIsInstance(devices,list)

    def test_none_device_resolves_to_concrete_compatible_index(self):
        with patch.object(SoundDeviceAudioInput, "_module", return_value=_FakeSoundDevice):
            self.assertEqual(SoundDeviceAudioInput().resolve_input_device(), 1)

    def test_incompatible_default_uses_compatible_fallback(self):
        with patch.object(SoundDeviceAudioInput, "_module", return_value=_FakeSoundDevice):
            adapter = SoundDeviceAudioInput(device=0)
            self.assertEqual(adapter.resolve_input_device(), 1)

    def test_stream_receives_resolved_integer_index(self):
        fake=_FakeSoundDevice
        fake.started_device=None
        fake.InputStream=classmethod(lambda cls, **kwargs: _FakeStream(cls, **kwargs))
        with patch.object(SoundDeviceAudioInput, "_module", return_value=fake):
            adapter=SoundDeviceAudioInput()
            adapter.start()
            self.assertEqual(fake.started_device,1)
            self.assertIsInstance(fake.started_device,int)
            adapter.cancel()

if __name__=='__main__': unittest.main(verbosity=2)
