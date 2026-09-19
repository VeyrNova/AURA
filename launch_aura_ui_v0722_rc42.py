# AURA P0.2.8 ACTIVE UIROOT PCM SINK AUTOPATCH
from pathlib import Path
import json, os, subprocess, sys

# ---------------------------------------------------------------------------
# AURA P0.2.8 ACTIVE UIROOT PCM SINK AUTOPATCH
# The RC4.2 launcher already resolves the real ui_root from its locator.
# Patch THAT shell_host.py before launch, not a guessed/canonical payload copy.
# ---------------------------------------------------------------------------
def _aura_p028_patch_active_shell(ui_root):
    _p028_core = Path(__file__).resolve().parent
    _p028_status = _p028_core / "P0_2_8_ACTIVE_UIROOT_STATUS.txt"
    try:
        _p028_root = Path(ui_root).resolve()
        _p028_shell = _p028_root / "tools" / "shell_host.py"
        if not _p028_shell.is_file():
            _p028_status.write_text(
                "ERROR active shell missing: " + str(_p028_shell),
                encoding="utf-8",
            )
            return False

        _p028_text = _p028_shell.read_text(encoding="utf-8", errors="replace")
        _p028_marker = "AURA P0.2.8 ACTIVE THREEJS PCM SINK"

        if _p028_marker in _p028_text:
            _p028_status.write_text(
                "ALREADY_PATCHED\nui_root=" + str(_p028_root) +
                "\nshell=" + str(_p028_shell),
                encoding="utf-8",
            )
            return True

        # Only touch the RC4.2 host with the expected runtime topology.
        if "ShellRuntime(root,core)" not in _p028_text:
            _p028_status.write_text(
                "ERROR incompatible shell topology\nshell=" + str(_p028_shell),
                encoding="utf-8",
            )
            return False

        _p028_needle = "rt=ShellRuntime(root,core)"
        _p028_block = r"""
    # AURA P0.2.8 ACTIVE THREEJS PCM SINK
    # Installed into the ui_root actually resolved by launch_aura_ui_v0722_rc42.py.
    import builtins as _aura_p028_builtins
    def _aura_p028_threejs_pcm_sink(level):
        try:
            value=max(0.0,min(1.0,float(level)))
        except Exception:
            value=0.0
        now=time.monotonic()
        if now-rt.last_pcm>=1/30:
            rt.last_pcm=now
            try:
                rt.hub.send('voice_amplitude',{'level':value})
            except Exception:
                pass
    _aura_p028_builtins._aura_rc42_pcm_sink=_aura_p028_threejs_pcm_sink
    logging.getLogger('aura.rc4_2.shell').info(
        'AURA P0.2.8 ACTIVE Three.js PCM sink ready ui_root=%s max_hz=30',
        root,
    )
"""
        _p028_replacement = _p028_needle + "\n" + _p028_block.rstrip()
        _p028_patched = _p028_text.replace(_p028_needle, _p028_replacement, 1)

        # Compile before touching the active file.
        compile(_p028_patched, str(_p028_shell), "exec")

        _p028_backup_dir = (
            _p028_core / "_patch_backups" / "P0_2_8_active_uiroot_pcm_sink"
        )
        _p028_backup_dir.mkdir(parents=True, exist_ok=True)
        _p028_backup = _p028_backup_dir / (
            "shell_host_" + str(abs(hash(str(_p028_shell)))) + "_before.py"
        )
        if not _p028_backup.exists():
            _p028_backup.write_bytes(_p028_shell.read_bytes())

        _p028_tmp = _p028_shell.with_name("shell_host.p0_2_8_tmp.py")
        _p028_tmp.write_text(_p028_patched, encoding="utf-8", newline="\n")
        compile(_p028_tmp.read_text(encoding="utf-8"), str(_p028_tmp), "exec")
        _p028_tmp.replace(_p028_shell)

        _p028_status.write_text(
            "PATCHED\nui_root=" + str(_p028_root) +
            "\nshell=" + str(_p028_shell) +
            "\nbackup=" + str(_p028_backup),
            encoding="utf-8",
        )
        return True
    except Exception as _p028_exc:
        try:
            _p028_status.write_text(
                "ERROR " + type(_p028_exc).__name__ + ": " + str(_p028_exc),
                encoding="utf-8",
            )
        except Exception:
            pass
        return False

# AURA P0.8.5.2.2 RUNTIME PATH CONSUMER
def _aura_p08522_load_paths(core):
    import importlib.util
    # AURA v2 compatibility: prefer the current root-level resolver.
    # Keep the historical core/runtime location as a fallback only.
    candidates=(
        core/'aura_paths.py',
        core/'core'/'runtime'/'aura_paths.py',
    )
    module_path=next((p for p in candidates if p.is_file()),None)
    if module_path is None:
        raise RuntimeError(
            'AuraPaths introuvable. Checked: '+
            ', '.join(str(p) for p in candidates)
        )
    spec=importlib.util.spec_from_file_location('aura_paths_launcher_p08522',module_path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AuraPaths.resolve(core_root=core)

def main():
    import argparse
    args_parser=argparse.ArgumentParser()
    args_parser.add_argument('--debug',action='store_true')
    args=args_parser.parse_args()

    core=Path(__file__).resolve().parent
    paths=_aura_p08522_load_paths(core)
    root=Path(paths.ui_root).resolve()

    if not (root/'tools'/'launch_shell.py').is_file():
        raise SystemExit('UI AURA active introuvable: '+str(root))

    # Environment becomes the portable hand-off contract.
    env=os.environ.copy()
    env['AURA_ROOT']=str(core)
    env['AURA_UI_ROOT']=str(root)
    env['AURA_DEPLOYMENT_MODE']=str(paths.deployment_mode)

    _aura_p028_patch_active_shell(root)
    script=root/'tools'/'launch_shell.py'
    cmd=[sys.executable,str(script)]
    if args.debug:
        cmd.append('--debug')
    return subprocess.call(cmd,cwd=str(root),env=env)

if __name__=='__main__':
    raise SystemExit(main())
