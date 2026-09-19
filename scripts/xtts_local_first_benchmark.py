from __future__ import annotations
import sys, time
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from config.settings import settings
from voice.voice_profile import VoiceProfileStore
from voice.xtts_tts import XTTSTTS

def main():
    print('=== AURA XTTS TRUE STREAMING LOCAL-FIRST BENCHMARK ===')
    print(f'XTTS_ALLOW_CUDA={settings.XTTS_ALLOW_CUDA} XTTS_DEVICE={settings.XTTS_DEVICE} NATIVE_STREAM={settings.FAST_SPEECH_NATIVE_STREAMING}')
    if not settings.XTTS_ALLOW_CUDA or settings.XTTS_DEVICE.strip().lower()!='cuda':
        print('BLOQUÉ: active d’abord XTTS CUDA avec ENABLE_XTTS_GPU.bat. Aucun changement automatique n’est effectué.')
        return 2
    store=VoiceProfileStore()
    base=store.load()
    profile=replace(base,engine='xtts',fallback_engine='piper',xtts_mode='preset').normalized()
    tts=XTTSTTS(profile)
    if not tts.is_available():
        print('BLOQUÉ: XTTS ou son modèle local/référence n’est pas prêt.')
        return 3
    text='Bonjour. Je suis Aura, prête en local.'
    before=time.perf_counter()
    info=tts.runtime_info(load=True)
    load=time.perf_counter()-before
    print(f'LOAD {load:.3f}s device={info.device} gpu={info.gpu_name or "?"} alloc={info.allocated_mb:.0f}MiB reserved={info.reserved_mb:.0f}MiB total={info.total_mb:.0f}MiB')
    metrics=[]
    for i in range(3):
        m=tts.speak_preview(text,fast=True)
        metrics.append(m)
        print(f'RUN {i+1}: first_audio={m.time_to_audio_seconds:.3f}s first_chunk={m.first_chunk_synthesis_seconds:.3f}s synth={m.synthesis_seconds:.3f}s total={m.total_seconds:.3f}s chunks={m.chunk_count} progressive={m.progressive}')
    hot=[m.time_to_audio_seconds for m in metrics[1:] if m.time_to_audio_seconds>0]
    if hot:
        avg=sum(hot)/len(hot)
        print(f'HOT TTFA AVG={avg:.3f}s')
        print('CANDIDAT LOCAL-FIRST: OUI' if avg <= 0.80 and all(m.chunk_count > 1 for m in metrics[1:]) else 'CANDIDAT LOCAL-FIRST: À OPTIMISER')
    return 0
if __name__=='__main__': raise SystemExit(main())
