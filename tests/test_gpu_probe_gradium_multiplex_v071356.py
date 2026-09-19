import base64
import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot, ResourcePressureError
from voice.gradium_tts import GradiumTTS


class _VoiceEngineFake:
    def release_stt_model(self): return True
    def release_xtts_model(self): return True
    def xtts_model_loaded(self): return False


class _LLMProbeFake:
    def __init__(self, *, gpu_ratio=0.8, other=None, model_size=2 * 1024**3):
        self.running = dict(other or {})
        self.unloaded = []
        self.warmups = []
        self.gpu_ratio = gpu_ratio
        self.model_size = model_size
    def running_model_info(self, model=None): return self.running.get(model)
    def running_model_query_ok(self): return True
    def unload(self, model=None): self.unloaded.append(model); self.running.pop(model, None); return True
    def model_available(self, model): return True
    def local_model_info(self, model): return {'name': model, 'size': self.model_size}
    def warmup(self, **kwargs):
        self.warmups.append(dict(kwargs))
        model = kwargs['model']
        size = self.model_size
        self.running[model] = {'name': model, 'size': size, 'size_vram': int(size * self.gpu_ratio)}
    def model_processor_info(self, model=None):
        info = self.running.get(model) or {}
        size = int(info.get('size', 0) or 0)
        vram = int(info.get('size_vram', 0) or 0)
        ratio = (vram / size) if size else 0.0
        return {'model': model, 'size': size, 'size_vram': vram, 'gpu_ratio': ratio,
                'processor': '100% CPU' if size and not vram else f'{int(round(ratio*100))}% GPU' if size else 'not-loaded'}


class GPUProbe071356Tests(unittest.TestCase):
    def _guardian(self, llm):
        g = ResourceGuardian(llm, _VoiceEngineFake())
        snap = ResourceSnapshot(ram_used_pct=76.3, ram_total_gb=15.6, ram_available_gb=3.70,
                                vram_used_mb=0, vram_total_mb=6141,
                                gpu_name='NVIDIA GeForce RTX 4050 Laptop GPU')
        g.sample = lambda **kwargs: snap
        g._collect = lambda: None
        g._wait_model_unloaded = lambda model=None: True
        # Physical NVIDIA attribution is part of the production safety
        # contract. Unit tests must therefore mock it together with Ollama's
        # simulated GPU residency instead of consulting real nvidia-smi.
        g._gpu_probe_source = "nvidia-smi"
        g._gpu_snapshot = lambda force=False: (1800.0, 6141.0, "NVIDIA GeForce RTX 4050 Laptop GPU")
        return g

    def _profile(self):
        return {'name':'voice-fast','provider':'local','model':settings.LLM_VOICE_MODEL,
                'co_resident':False,'keep_alive':'5m','num_ctx':2048}

    def test_gpu_fit_probe_preloads_and_accepts_verified_vram_residency(self):
        llm = _LLMProbeFake(gpu_ratio=0.85)
        g = self._guardian(llm)
        g.prepare_for_llm(self._profile())
        self.assertEqual(len(llm.warmups), 1)
        self.assertIn(settings.LLM_VOICE_MODEL, llm.running)
        self.assertGreater(llm.running[settings.LLM_VOICE_MODEL]['size_vram'], 0)

    def test_gpu_probe_rejects_and_unloads_cpu_only_placement(self):
        llm = _LLMProbeFake(gpu_ratio=0.0)
        g = self._guardian(llm)
        with self.assertRaises(ResourcePressureError):
            g.prepare_for_llm(self._profile())
        self.assertIn(settings.LLM_VOICE_MODEL, llm.unloaded)

    def test_other_cpu_resident_brain_is_unloaded_before_voice_preflight(self):
        other = {settings.LLM_TEXT_MODEL: {'name': settings.LLM_TEXT_MODEL, 'size': 4 * 1024**3, 'size_vram': 0}}
        llm = _LLMProbeFake(gpu_ratio=0.85, other=other)
        g = self._guardian(llm)
        g.prepare_for_llm(self._profile())
        self.assertIn(settings.LLM_TEXT_MODEL, llm.unloaded)

    def test_model_that_cannot_fit_vram_remains_blocked_without_probe(self):
        llm = _LLMProbeFake(gpu_ratio=0.85, model_size=6 * 1024**3)
        g = self._guardian(llm)
        with self.assertRaises(ResourcePressureError):
            g.prepare_for_llm(self._profile())
        self.assertEqual(llm.warmups, [])


class _RawOutputStream:
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def write(self, data): pass


class _MultiplexWS:
    def __init__(self):
        self.sent=[]; self.queue=[]; self.closed=False
    def send(self, raw):
        msg=json.loads(raw); self.sent.append(msg)
        rid=msg.get('client_req_id')
        if msg.get('type') == 'setup':
            self.queue.append(json.dumps({'type':'ready','client_req_id':rid}))
        elif msg.get('type') == 'end_of_stream' and rid:
            audio=base64.b64encode(b'\x00\x00'*80).decode('ascii')
            self.queue.append(json.dumps({'type':'audio','audio':audio,'client_req_id':rid}))
            self.queue.append(json.dumps({'type':'end_of_stream','client_req_id':rid}))
    def recv(self, timeout=None): return self.queue.pop(0)
    def close(self): self.closed=True


class GradiumMultiplex071356Tests(unittest.TestCase):
    def test_reused_socket_scopes_each_logical_request_with_unique_client_req_id(self):
        ws=_MultiplexWS(); calls=[]
        def connect(*args, **kwargs): calls.append(1); return ws
        modules={
            'websockets': types.ModuleType('websockets'),
            'websockets.sync': types.ModuleType('websockets.sync'),
            'websockets.sync.client': types.ModuleType('websockets.sync.client'),
            'sounddevice': types.ModuleType('sounddevice'),
        }
        modules['websockets.sync.client'].connect=connect
        modules['sounddevice'].RawOutputStream=_RawOutputStream
        backend=GradiumTTS(SimpleNamespace(gradium_voice_id='voice-fr', gradium_model='default'))
        with patch.dict(sys.modules, modules, clear=False):
            first=backend._speak_websocket('Bonjour')
            second=backend._speak_websocket('Encore')
        self.assertFalse(first.connection_reused)
        self.assertTrue(second.connection_reused)
        self.assertEqual(len(calls), 1)
        setups=[m for m in ws.sent if m.get('type')=='setup']
        self.assertEqual(len(setups),2)
        self.assertNotEqual(setups[0]['client_req_id'], setups[1]['client_req_id'])
        for setup in setups:
            rid=setup['client_req_id']
            scoped=[m for m in ws.sent if m.get('client_req_id')==rid]
            self.assertEqual([m['type'] for m in scoped], ['setup','text','end_of_stream'])


if __name__ == '__main__':
    unittest.main()
