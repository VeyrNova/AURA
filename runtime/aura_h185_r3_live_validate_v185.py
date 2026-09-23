from __future__ import annotations
import hashlib,json,os,shutil,subprocess,time,urllib.request
from datetime import datetime
from pathlib import Path

ROOT=Path(r"C:\AURA GPT version")
TARGET=ROOT/"runtime"/"aura_healthkit_bridge_v185.py"
ROADMAP=ROOT/"data"/"roadmap"/"aura_master_roadmap_v2.json"
SCHEDULE=ROOT/"data"/"roadmap"/"aura_roadmap_schedule_state.json"
LOCAL=Path(os.environ.get("LOCALAPPDATA",""))
VITALS=LOCAL/"AURA"/"vitals"
RECEIPT=VITALS/"last_validation_v185.json"
SNAPSHOT=VITALS/"latest.json"
PIDFILE=VITALS/"healthkit_bridge_v185.pid"
PAIRING=VITALS/"iphone_pairing_v185.txt"

STAMP=datetime.now().strftime("%Y%m%d_%H%M%S")
RESULT=ROOT/"data"/"roadmap"/f"AURA_H185_R3_LIVE_IPHONE_VALIDATE_{STAMP}_RESULT.txt"
LOG=[]
proc=None

def log(x=""):
    s=str(x); print(s,flush=True); LOG.append(s)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finish(rc):
    RESULT.parent.mkdir(parents=True,exist_ok=True); RESULT.write_text("\n".join(LOG)+"\n",encoding="utf-8"); raise SystemExit(rc)
def pyexe():
    p=ROOT/"venv"/"Scripts"/"python.exe"
    return str(p) if p.exists() else (shutil.which("python.exe") or "")
def health():
    with urllib.request.urlopen("http://127.0.0.1:18585/health",timeout=1.5) as r:
        return json.loads(r.read().decode("utf-8"))

log("AURA H185-R3 - LIVE IPHONE /v1/validate")
log("="*76)
log("This test waits for ONE real iPhone validation request.")
log("The /v1/validate endpoint does not write health values to latest.json.")
log("The receipt records only client IP, source/device labels and recognized field names.")
log("")
try:
    for p in [TARGET,ROADMAP,SCHEDULE,PAIRING]:
        if not p.exists(): raise RuntimeError(f"required file unavailable: {p}")
    if PIDFILE.exists():
        raise RuntimeError("Bridge PID file already exists. Stop the bridge first.")
    py=pyexe()
    if not py: raise RuntimeError("Python unavailable")
    road_sha,sched_sha=sha(ROADMAP),sha(SCHEDULE)
    snap_sha=sha(SNAPSHOT) if SNAPSHOT.exists() else None
    old_receipt_sha=sha(RECEIPT) if RECEIPT.exists() else None
    old_receipt_mtime=RECEIPT.stat().st_mtime if RECEIPT.exists() else 0.0

    log(f"pairing_file = {PAIRING}")
    log("Use the Validate URL and Bearer token from that PRIVATE file.")
    log("On iPhone: run your Shortcut with POST /v1/validate.")
    log("Waiting up to 15 minutes...")
    log("")

    proc=subprocess.Popen([py,"-u",str(TARGET)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                          creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    ready=False
    for _ in range(40):
        if proc.poll() is not None: break
        try:
            h=health()
            if h.get("service")=="aura-healthkit-bridge":
                ready=True; break
        except Exception: pass
        time.sleep(.25)
    if not ready: raise RuntimeError("bridge did not become healthy")
    log("[PASS] bridge healthy")

    start=time.time()
    receipt=None
    while time.time()-start < 900:
        if RECEIPT.exists():
            mtime=RECEIPT.stat().st_mtime
            if mtime > max(start-1,old_receipt_mtime):
                try:
                    candidate=json.loads(RECEIPT.read_text(encoding="utf-8"))
                except Exception:
                    candidate=None
                if isinstance(candidate,dict) and candidate.get("schema")=="aura.healthkit.validation-receipt.v185":
                    receipt=candidate; break
        if proc.poll() is not None: raise RuntimeError("bridge stopped unexpectedly")
        time.sleep(.5)

    if receipt is None: raise RuntimeError("No live iPhone validation receipt received within 15 minutes")

    client=str(receipt.get("client_ip") or "")
    recognized=receipt.get("recognized") if isinstance(receipt.get("recognized"),list) else []
    no_values=receipt.get("contains_health_values") is False
    non_loopback=client not in {"","127.0.0.1","::1"}

    log(f"receipt_client_ip = {client}")
    log(f"receipt_source = {receipt.get('source') or ''}")
    log(f"receipt_device = {receipt.get('device') or ''}")
    log(f"receipt_recognized_count = {len(recognized)}")
    log("receipt_recognized = "+",".join(str(x) for x in recognized))
    log(f"receipt_no_health_values = {no_values}")
    log(f"receipt_non_loopback_client = {non_loopback}")

    if not recognized or not no_values or not non_loopback:
        raise RuntimeError("live iPhone validation receipt did not satisfy acceptance gates")

    if sha(ROADMAP)!=road_sha or sha(SCHEDULE)!=sched_sha:
        raise RuntimeError("Roadmap/schedule changed unexpectedly")
    if snap_sha is None and SNAPSHOT.exists():
        raise RuntimeError("/v1/validate unexpectedly created latest.json")
    if snap_sha is not None and sha(SNAPSHOT)!=snap_sha:
        raise RuntimeError("/v1/validate unexpectedly changed latest.json")

    log("roadmap_unchanged = True")
    log("schedule_unchanged = True")
    log("live_health_snapshot_unchanged = True")
    log("")
    log(f"result_file = {RESULT}")
    log("[PASS] H185-R3 LIVE IPHONE VALIDATION COMPLETE.")
    log("Real iPhone -> PC private-LAN authenticated validation is proven.")
    finish(0)

except SystemExit:
    raise
except Exception as exc:
    log("")
    log(f"[BLOCKED] {type(exc).__name__}: {exc}")
    log("No Roadmap mutation was performed.")
    finish(4)
finally:
    if proc is not None:
        try:
            proc.terminate(); proc.wait(timeout=4)
        except Exception:
            try: proc.kill()
            except Exception: pass
    try: PIDFILE.unlink(missing_ok=True)
    except Exception: pass
