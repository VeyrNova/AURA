"""Deterministic offline native test runner with durable progress evidence."""
from __future__ import annotations
import json, os, re, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).parents[1]
EVIDENCE_DIR=ROOT/'tests/native/_evidence'; EVIDENCE_PATH=EVIDENCE_DIR/'headless_latest.json'; PROGRESS_PATH=EVIDENCE_DIR/'headless_progress.jsonl'
EXCLUDED=("_real","e2e","pcc","provider_credentials_center","google_ui","ui_b43")
OFFSCREEN_ALLOW={'test_weather_city_qml','test_settings_native','test_modules_native','test_music_native','test_music_qml_controls','test_local_notes','test_rc_readiness','test_qml_runtime_errors','test_local_reminders_r1','test_runtime_wiring','test_diagnostics_native','test_weather_qml_wiring','test_live_module_qml','test_maps_visual_contract','test_weather_base_map_contract','test_mail_live_layout_contract','test_agenda_daily_hub_delegate','test_routing_native'}
def _write_atomic(data):
    EVIDENCE_DIR.mkdir(parents=True,exist_ok=True); tmp=EVIDENCE_PATH.with_suffix('.json.tmp'); tmp.write_text(json.dumps(data,indent=2),encoding='utf-8'); os.replace(tmp,EVIDENCE_PATH)
def _progress(line):
    EVIDENCE_DIR.mkdir(parents=True,exist_ok=True)
    with PROGRESS_PATH.open('a',encoding='utf-8') as f: f.write(line+'\n'); f.flush()
    print(line,flush=True)
def main():
    files=sorted((ROOT/'tests/native').glob('test*.py')); modules=[p.stem for p in files]; excluded=[]
    for m in modules:
        text=(ROOT/'tests/native'/f'{m}.py').read_text(encoding='utf-8')
        if any(x in m.lower() for x in EXCLUDED) or ('PySide6' in text and m not in OFFSCREEN_ALLOW) or ('compose_runtime' in text and m not in OFFSCREEN_ALLOW): excluded.append(m)
    selected=[m for m in modules if m not in excluded]; counts={m:(ROOT/'tests/native'/f'{m}.py').read_text(encoding='utf-8').count('def test_') for m in modules}
    env=os.environ.copy(); env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join((str(ROOT/'src'),str(ROOT/'tests/native'))),QT_QPA_PLATFORM='offscreen')
    started=time.monotonic(); results=[]; failed_imports=[]; timeouts=[]; total=passed=failed=executed_tests=0; evidence={'status':'running','started_at':time.time(),'modules':results,'timeouts':timeouts,'failed_imports':failed_imports}; _write_atomic(evidence)
    try:
        for module in selected:
            _progress(f'MODULE_START {module}'); t0=time.monotonic(); timed_out=False
            # Qt/Multimedia initialization can exceed 15s on a busy Windows
            # desktop. Keep a bounded, explicit budget for those modules.
            budget=30 if module in OFFSCREEN_ALLOW else 15
            try: p=subprocess.run([sys.executable,'-B','-m','unittest',module],cwd=ROOT,env=env,text=True,capture_output=True,timeout=budget); output=p.stdout+p.stderr
            except subprocess.TimeoutExpired as exc: timed_out=True; timeouts.append(module); output=(exc.stdout or '')+(exc.stderr or ''); p=None
            duration=round(time.monotonic()-t0,3); match=re.search(r'Ran (\d+) tests? in [0-9.]+s',output or ''); n=int(match.group(1)) if match else 0; import_error=bool(re.search(r'ImportError|ModuleNotFoundError',output or '')) or not match
            if import_error: failed_imports.append(module)
            ok=(not timed_out and p is not None and p.returncode==0 and not import_error)
            if timed_out: n=counts[module]
            total+=n; executed_tests+=(0 if timed_out else n); passed+=n if ok else 0; failed+=0 if ok else n
            results.append({'module':module,'tests':n,'passed':n if ok else 0,'failed':0 if ok else n,'returncode':None if p is None else p.returncode,'timeout':timed_out,'import_error':import_error,'duration_s':duration}); _progress(f'MODULE_END {module} duration={duration:.3f}s result={"PASS" if ok else ("TIMEOUT" if timed_out else "FAIL")}'); evidence.update({'modules':results,'timeouts':timeouts,'failed_imports':failed_imports}); _write_atomic(evidence)
    finally:
        discovered_tests=sum(counts.values()); adf=[m for m in modules if m.startswith('test_adf_') or m=='test_developer_fabric']; adf_discovered=sum(counts[m] for m in adf); adf_excluded=sum(counts[m] for m in adf if m in excluded)
        evidence.update({'status':'complete','completed_at':time.time(),'discovered_modules':len(modules),'executed_modules':len(selected),'excluded_modules':len(excluded),'discovered_tests':discovered_tests,'executed_tests':executed_tests,'excluded_tests':discovered_tests-executed_tests,'adf_discovered_tests':adf_discovered,'adf_executed_tests':adf_discovered-adf_excluded,'adf_excluded_tests':adf_excluded,'passed':passed,'failed':failed,'skip':0,'duration_s':round(time.monotonic()-started,3),'excluded_list':excluded}); _write_atomic(evidence)
        print(f'DISCOVERED_MODULES={len(modules)} EXECUTED_MODULES={len(selected)} EXCLUDED_MODULES={len(excluded)}',flush=True); print('EXCLUDED_REASON=real_google_or_interactive_gui_or_unbounded_qt_runtime',flush=True); print('EXCLUDED_LIST='+','.join(excluded),flush=True); print('EXECUTED_COUNTS='+','.join(f'{m}:{counts[m]}' for m in selected),flush=True); print(f'DISCOVERED_TESTS={discovered_tests} EXECUTED_TESTS={executed_tests} EXCLUDED_TESTS={discovered_tests-executed_tests}',flush=True); print(f'ADF_DISCOVERED_TESTS={adf_discovered} ADF_EXECUTED_TESTS={adf_discovered-adf_excluded} ADF_EXCLUDED_TESTS={adf_excluded}',flush=True); print('TIMEOUT_MODULES='+','.join(timeouts),flush=True); print('FAILED_IMPORTS='+str(len(failed_imports)),flush=True); print(f'HEADLESS_TOTAL={total} PASS={passed} FAIL={failed} SKIP=0 DURATION={time.monotonic()-started:.2f}s',flush=True)
    return 0 if failed==0 and not failed_imports and not timeouts else 1
if __name__=='__main__': raise SystemExit(main())
