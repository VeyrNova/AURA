from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402
from voice.voice_profile import VoiceProfileStore  # noqa: E402
from voice.xtts_tts import XTTSTTS  # noqa: E402




def configure_utf8_stdio() -> None:
    """Force predictable UTF-8 diagnostics on Windows consoles and redirected output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def ver(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except Exception:
        return 'not installed'


def main() -> int:
    configure_utf8_stdio()
    print('=== AURA v0.5.2.6 XTTS SAFE DIAGNOSTICS ===', flush=True)
    profile = VoiceProfileStore().load()
    cache_dir = XTTSTTS.model_cache_dir()
    print(f'Configured engine : {profile.engine}', flush=True)
    print(f'Selected preset   : {profile.xtts_preset}', flush=True)
    print(f'XTTS device       : {settings.XTTS_DEVICE}', flush=True)
    print(f'CUDA opt-in       : {settings.XTTS_ALLOW_CUDA}', flush=True)
    print(f'Python            : {sys.version.split()[0]}', flush=True)
    print(f'coqui-tts         : {ver("coqui-tts")}', flush=True)
    print(f'transformers      : {ver("transformers")}', flush=True)
    print(f'torch             : {ver("torch")}', flush=True)
    print(f'XTTS dependency   : {XTTSTTS.dependency_available()}', flush=True)
    print(f'XTTS cache ready  : {cache_dir is not None}', flush=True)
    print(f'XTTS cache dir    : {cache_dir or "NOT FOUND"}', flush=True)

    if cache_dir is None:
        print('[FAIL] Cache XTTS incomplet. Aucun modèle lourd ne sera chargé.', flush=True)
        for candidate in XTTSTTS.model_cache_candidates():
            missing = [name for name in XTTSTTS.REQUIRED_MODEL_FILES if not (candidate / name).is_file()]
            print(f'  - {candidate} | missing={",".join(missing) if missing else "none"}', flush=True)
        return 2
    if not XTTSTTS.dependency_available():
        print('[FAIL] Dépendances XTTS manquantes. Aucun modèle lourd ne sera chargé.', flush=True)
        return 3

    print('', flush=True)
    print('Le modèle lourd va être testé dans un PROCESSUS ENFANT, forcé en CPU.', flush=True)
    print("S'il plante, cette console doit rester ouverte et afficher le code de sortie.", flush=True)
    result_path = settings.TEMP_DIR / 'xtts_safe_probe_result.json'
    try:
        result_path.unlink(missing_ok=True)
    except Exception:
        pass
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
    env['TTS_HOME'] = str(settings.XTTS_HOME)
    env['CUDA_VISIBLE_DEVICES'] = '-1'
    cmd = [sys.executable, str(ROOT / 'scripts' / 'xtts_safe_probe.py'), '--device', 'cpu', '--result', str(result_path)]
    log_path = settings.LOG_DIR / 'xtts_diagnostics.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end='', flush=True)
            log.write(line)
            log.flush()
        completed_returncode = process.wait()
    print('', flush=True)
    print(f'Child exit code   : {completed_returncode}', flush=True)
    print(f'Diagnostic log    : {log_path}', flush=True)
    if result_path.is_file():
        try:
            data = json.loads(result_path.read_text(encoding='utf-8'))
            speakers = data.get('speakers') or []
            print(f'Probe stage       : {data.get("stage")}', flush=True)
            print(f'Speakers detected : {len(speakers)}', flush=True)
            if data.get('ok'):
                selected = profile.xtts_preset
                print(f'Selected valid    : {selected in speakers if speakers else "unknown"}', flush=True)
        except Exception as exc:
            print(f'Probe result read : FAIL {exc}', flush=True)
    if completed_returncode != 0:
        print('[FAIL] XTTS a échoué dans le processus isolé. Consulte la sortie ci-dessus.', flush=True)
        print('AURA continuera d’utiliser Piper tant que ce test CPU n’est pas PASS.', flush=True)
        return 4
    print('[PASS] XTTS CPU safe-load réussi.', flush=True)
    print('Ne teste pas CUDA tant que la stabilité CPU n’est pas confirmée dans AURA.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
