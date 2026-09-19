@echo off
setlocal EnableExtensions DisableDelayedExpansion
title ADD AURA MEDIA FOLDER
echo ================================================================
echo ADD AURA MEDIA FOLDER
echo ================================================================
echo(
set /p "MEDIA_ROOT=Paste the full media folder path: "
if not defined MEDIA_ROOT (
  echo [FAIL] No path entered.
  pause
  exit /b 1
)
set "AURA_MEDIA_ROOT=%MEDIA_ROOT%"
if exist "C:\AURA GPT version\venv\Scripts\python.exe" (
  set "PY=C:\AURA GPT version\venv\Scripts\python.exe"
) else (
  set "PY=python.exe"
)
"%PY%" -c "import json,os,sys;from pathlib import Path;sys.path.insert(0,r'C:\AURA GPT version');from runtime.aura_local_media_index_v180 import refresh_default_index;root=Path(os.environ['AURA_MEDIA_ROOT']).expanduser();cfg=Path(r'C:\AURA GPT version\data\media\media_roots_v180.json');d=json.loads(cfg.read_text(encoding='utf-8-sig')) if cfg.exists() else {'schema':'aura.media-roots.v180','roots':[],'max_files':25000};assert root.exists() and root.is_dir(), 'folder does not exist';roots=[str(x) for x in d.get('roots') or []];key=str(root.resolve()).casefold();seen={str(Path(x).expanduser().resolve()).casefold() for x in roots if Path(x).expanduser().exists()};roots.append(str(root.resolve())) if key not in seen else None;d['roots']=roots;cfg.parent.mkdir(parents=True,exist_ok=True);cfg.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');r=refresh_default_index(r'C:\AURA GPT version\data\media\local_media_index_v180.json',roots=roots,max_files=int(d.get('max_files') or 25000));print('[PASS] Media root added/refreshed:',root);print('Items:',r.get('item_count'),'Audio:',r.get('audio_count'),'Video:',r.get('video_count'))"
if errorlevel 1 (
  echo [FAIL] Folder was not added.
  pause
  exit /b 2
)
echo(
pause
exit /b 0
