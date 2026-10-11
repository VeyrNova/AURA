"""Explicit, short hardware smoke; does nothing unless --record is passed."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from aura_native.voice.providers import SoundDeviceAudioInput, WhisperSTTProvider

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--record',action='store_true'); parser.add_argument('--seconds',type=float,default=3.0)
    args=parser.parse_args()
    if not args.record:
        print('VOICE_REAL_MIC_TEST_READY=false (pass --record explicitly)'); return 0
    seconds=max(1.0,min(5.0,float(args.seconds)))
    adapter=SoundDeviceAudioInput(max_seconds=seconds)
    print('VOICE_REAL_MIC_TEST=START')
    try:
        adapter.start()
        import time; time.sleep(seconds)
        audio=adapter.stop()
        print('VOICE_REAL_MIC_TEST=CAPTURED audio_in_memory=true')
        print('STT_REAL_TEST=UNAVAILABLE' if not getattr(adapter,'stt',None) else 'STT_REAL_TEST=DEFERRED')
    except RuntimeError as exc:
        print(f'VOICE_REAL_MIC_TEST=UNAVAILABLE reason={exc}')
    finally:
        adapter.cancel()
    return 0
if __name__=='__main__': raise SystemExit(main())
