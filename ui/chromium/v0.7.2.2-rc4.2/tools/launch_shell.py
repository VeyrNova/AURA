from __future__ import annotations
import argparse, importlib.util, json, os, subprocess, sys
from pathlib import Path

P08522_MARKER="AURA P0.8.5.2.2 RUNTIME PATH CONSUMER"

def _valid_core(path: Path) -> bool:
    return (path/'core'/'version.py').is_file() and (path/'VERSION').is_file()

def _discover_core(root: Path) -> Path:
    candidates=[]

    explicit=str(os.getenv('AURA_ROOT') or '').strip()
    if explicit:
        candidates.append(Path(explicit))

    # Compatibility fallback for direct launch_shell.py execution.
    cfg=root/'aura_ui_config.json'
    if cfg.is_file():
        try:
            raw=json.loads(cfg.read_text(encoding='utf-8')).get('core_root')
            if raw:
                candidates.append(Path(raw))
        except Exception:
            pass

    current=root.parent/'current.json'
    if current.is_file():
        try:
            raw=json.loads(current.read_text(encoding='utf-8')).get('core_root')
            if raw:
                candidates.append(Path(raw))
        except Exception:
            pass

    # Portable UI may live inside Core; inspect ancestors last.
    candidates.extend([root,*root.parents])

    seen=set()
    for raw in candidates:
        try:
            p=raw.expanduser().resolve(strict=False)
        except Exception:
            p=raw.expanduser().absolute()
        key=str(p).casefold()
        if key in seen:
            continue
        seen.add(key)
        if _valid_core(p):
            return p
    raise SystemExit('AURA Core introuvable. Lancez AURA via son launcher principal.')

def _load_paths(core: Path):
    module_path=core/'core'/'runtime'/'aura_paths.py'
    if not module_path.is_file():
        raise SystemExit('AuraPaths introuvable: '+str(module_path))
    spec=importlib.util.spec_from_file_location('aura_paths_launch_shell_p08522',module_path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AuraPaths.resolve(core_root=core)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--debug',action='store_true')
    args=ap.parse_args()

    root=Path(__file__).resolve().parents[1]
    core=_discover_core(root)
    paths=_load_paths(core)

    os.environ['AURA_ROOT']=str(core)
    os.environ['AURA_UI_ROOT']=str(root)
    os.environ['AURA_DEPLOYMENT_MODE']=str(paths.deployment_mode)

    host=root/'tools'/'shell_host.py'
    candidates=[
        core/'venv'/'Scripts'/('python.exe' if args.debug else 'pythonw.exe'),
        core/'venv'/'Scripts'/'python.exe',
        Path(sys.executable),
    ]
    py=next((p for p in candidates if p.is_file()),None)
    if py is None:
        raise SystemExit('Python Core introuvable')

    cmd=[str(py),str(host),'--core',str(core),'--ui-root',str(root)]
    flags=0
    if os.name=='nt' and not args.debug:
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'DETACHED_PROCESS',0)

    # Keep shell logs in their historical location until the dedicated logs migration.
    log=root/'logs'
    log.mkdir(exist_ok=True)
    if args.debug:
        return subprocess.call(cmd,cwd=str(root),env=os.environ.copy())
    with (log/'launcher.log').open('ab') as out:
        subprocess.Popen(
            cmd,
            cwd=str(root),
            stdout=out,
            stderr=out,
            creationflags=flags,
            close_fds=True,
            env=os.environ.copy(),
        )
    return 0

if __name__=='__main__':
    raise SystemExit(main())
