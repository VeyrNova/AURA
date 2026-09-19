from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def configure_utf8_stdio() -> None:
    """Prefer UTF-8 on Windows while keeping a safe fallback for redirected streams."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def out(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe = str(msg).encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe, flush=True)


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--result', default='')
    args = parser.parse_args()

    result_path = Path(args.result).resolve() if args.result else None
    result = {'ok': False, 'device': args.device, 'stage': 'start', 'speakers': []}

    try:
        out(f'[1/6] Python {sys.version.split()[0]}')
        result['stage'] = 'import_settings'
        from config.settings import settings
        os.environ['TTS_HOME'] = str(settings.XTTS_HOME)
        if args.device == 'cpu':
            # Must be set before torch CUDA initialization.
            os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
        out(f'[2/6] TTS_HOME={settings.XTTS_HOME}')

        result['stage'] = 'cache_check'
        from voice.xtts_tts import XTTSTTS
        cache = XTTSTTS.model_cache_dir()
        if cache is None:
            raise RuntimeError('Cache XTTS incomplet ou introuvable.')
        out(f'[3/6] Cache XTTS OK: {cache}')

        result['stage'] = 'import_torch'
        import torch
        out(f'[4/6] PyTorch {torch.__version__} | probe device={args.device}')
        if args.device == 'cuda':
            out(f'      torch.cuda.is_available={torch.cuda.is_available()}')
            if not torch.cuda.is_available():
                raise RuntimeError('CUDA indisponible dans PyTorch.')

        result['stage'] = 'load_tts'
        from TTS.api import TTS
        started = time.perf_counter()
        out('[5/6] Chargement XTTS-v2... (cette étape peut prendre du temps)')
        api = TTS(XTTSTTS.MODEL_NAME, progress_bar=False).to(args.device)
        elapsed = time.perf_counter() - started
        speakers = [str(x) for x in (getattr(api, 'speakers', None) or ())]
        out(f'[6/6] XTTS chargé en {elapsed:.1f}s | speakers={len(speakers)}')
        result.update(ok=True, stage='done', elapsed_seconds=elapsed, speakers=speakers)
        if speakers:
            for i, speaker in enumerate(speakers[:80]):
                out(f'  [{i:02d}] {speaker}')
        out('[PASS] XTTS peut être chargé sans faire tomber le processus.')
        return 0
    except BaseException as exc:
        result.update(ok=False, error_type=type(exc).__name__, error=str(exc))
        out(f'[FAIL] stage={result.get("stage")} {type(exc).__name__}: {exc}')
        traceback.print_exc()
        return 2
    finally:
        if result_path:
            try:
                result_path.parent.mkdir(parents=True, exist_ok=True)
                result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
