@echo off
setlocal EnableExtensions DisableDelayedExpansion
title REFRESH AURA MEDIA INDEX
set "ROOT=C:\AURA GPT version"
if exist "%ROOT%\venv\Scripts\python.exe" (
  set "PY=%ROOT%\venv\Scripts\python.exe"
) else (
  set "PY=python.exe"
)
"%PY%" -c "import json,sys;from pathlib import Path;sys.path.insert(0,r'C:\AURA GPT version');from runtime.aura_local_media_index_v180 import refresh_default_index;cfg=Path(r'C:\AURA GPT version\data\media\media_roots_v180.json');d=json.loads(cfg.read_text(encoding='utf-8-sig')) if cfg.exists() else {};r=refresh_default_index(r'C:\AURA GPT version\data\media\local_media_index_v180.json',roots=d.get('roots') or None,max_files=int(d.get('max_files') or 25000));print('AURA media index refreshed:',r.get('item_count'),'items from',r.get('root_count'),'roots')"
echo(
pause
