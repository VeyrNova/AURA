from __future__ import annotations
import hashlib, json, os, shutil, subprocess, time, urllib.request
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/"runtime"/"aura_healthkit_bridge_v185.py"
ROADMAP=ROOT/"data"/"roadmap"/"aura_master_roadmap_v2.json"
SCHEDULE=ROOT/"data"/"roadmap"/"aura_roadmap_schedule_state.json"
LOCAL=Path(os.environ.get("LOCALAPPDATA",""))
VITALS=LOCAL/"AURA"/"vitals"
SNAPSHOT=VITALS/"latest.json"
PIDFILE=VITALS/"healthkit_bridge_v185.pid"
PAIRING=VITALS/"iphone_pairing_v185.txt"
BACKUP_DIR=VITALS/"backups"

STAMP=datetime.now().strftime("%Y%m%d_%H%M%S")
RESULT=ROOT/"data"/"roadmap"/f"AURA_H185_R4_LIVE_HEALTH_INGEST_{STAMP}_RESULT.txt"
LOG=[]
PROC=None

NUMERIC_FIELDS=[
    "heart_rate_bpm","resting_heart_rate_bpm","hrv_ms","spo2_percent",
    "temperature_c","respiratory_rate_bpm","sleep_duration_hours"
]
ACTIVITY_FIELDS=[
    "move_kcal","move_goal_kcal","exercise_min","exercise_goal_min",
    "stand_hours","stand_goal_hours","steps","distance_km","active_energy_kcal"
]

def log(x=""):
    s=str(x)
    print(s,flush=True)
    LOG.append(s)

def finish(rc):
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    RESULT.write_text("\n".join(LOG)+"\n",encoding="utf-8")
    raise SystemExit(rc)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def pyexe():
    p=ROOT/"venv"/"Scripts"/"python.exe"
    return str(p) if p.exists() else (shutil.which("python.exe") or "")

def process_alive(pid):
    try:
        cp=subprocess.run(
            ["tasklist","/FI",f"PID eq {int(pid)}","/FO","CSV","/NH"],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=10
        )
        return str(int(pid)) in (cp.stdout or "")
    except Exception:
        return False

def http_health():
    with urllib.request.urlopen("http://127.0.0.1:18585/health",timeout=1.5) as r:
        return json.loads(r.read().decode("utf-8"))

def recognized_fields(snapshot):
    data=snapshot.get("data") if isinstance(snapshot.get("data"),dict) else {}
    out=[]
    for key in NUMERIC_FIELDS:
        if data.get(key) is not None:
            out.append(key)
    act=data.get("activity") if isinstance(data.get("activity"),dict) else {}
    for key in ACTIVITY_FIELDS:
        if act.get(key) is not None:
            out.append("activity."+key)
    if isinstance(data.get("heart_rate_series"),list) and data.get("heart_rate_series"):
        out.append("heart_rate_series")
    if isinstance(data.get("workouts"),list) and data.get("workouts"):
        out.append("workouts")
    return out

log("AURA H185-R4 - LIVE REAL HEALTH INGEST")
log("="*74)
log("Waits for ONE real iPhone POST /v1/ingest request.")
log("Result logs field names only, never numeric health values.")
log("")

try:
    for p in [TARGET,ROADMAP,SCHEDULE,PAIRING]:
        if not p.exists():
            raise RuntimeError(f"required file unavailable: {p}")

    if PIDFILE.exists():
        raw=PIDFILE.read_text(encoding="ascii",errors="ignore").strip() or "0"
        try:
            pid=int(raw)
        except Exception:
            pid=0
        if pid>0 and process_alive(pid):
            raise RuntimeError("HealthKit bridge is already running. Stop it before R4 live ingest.")
        PIDFILE.unlink(missing_ok=True)

    py=pyexe()
    if not py:
        raise RuntimeError("Python unavailable")

    road_sha=sha(ROADMAP)
    sched_sha=sha(SCHEDULE)
    before_hash=sha(SNAPSHOT) if SNAPSHOT.exists() else None
    before_mtime=SNAPSHOT.stat().st_mtime if SNAPSHOT.exists() else 0.0

    if SNAPSHOT.exists():
        BACKUP_DIR.mkdir(parents=True,exist_ok=True)
        prior=BACKUP_DIR/f"latest_before_h185_r4_{STAMP}.json"
        shutil.copy2(SNAPSHOT,prior)
        log(f"previous_snapshot_backup = {prior}")
    else:
        log("previous_snapshot_backup = (none; latest.json did not exist)")

    log(f"pairing_file = {PAIRING}")
    log("On iPhone, use the /v1/ingest URL and CURRENT PRIVATE Bearer token.")
    log("Waiting up to 15 minutes...")
    log("")

    PROC=subprocess.Popen(
        [py,"-u",str(TARGET)],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    )

    ready=False
    for _ in range(40):
        if PROC.poll() is not None:
            break
        try:
            h=http_health()
            if h.get("service")=="aura-healthkit-bridge":
                ready=True
                break
        except Exception:
            pass
        time.sleep(.25)

    if not ready:
        raise RuntimeError("bridge did not become healthy")
    log("[PASS] bridge healthy")

    start=time.time()
    received=None
    while time.time()-start < 900:
        if SNAPSHOT.exists():
            mtime=SNAPSHOT.stat().st_mtime
            changed=(mtime>max(before_mtime,start-1))
            if changed:
                try:
                    candidate=json.loads(SNAPSHOT.read_text(encoding="utf-8"))
                except Exception:
                    candidate=None
                if isinstance(candidate,dict) and candidate.get("schema")=="aura.vitals.local.v1":
                    received=candidate
                    break
        if PROC.poll() is not None:
            raise RuntimeError("bridge stopped unexpectedly")
        time.sleep(.5)

    if received is None:
        raise RuntimeError("No new AURA vitals snapshot received within 15 minutes")

    fields=recognized_fields(received)
    after_hash=sha(SNAPSHOT)
    source=str(received.get("source") or "")
    device=str(received.get("device") or "")

    gates={
        "snapshot_schema_ok":received.get("schema")=="aura.vitals.local.v1",
        "snapshot_changed":before_hash is None or after_hash!=before_hash,
        "recognized_fields_present":len(fields)>0,
        "roadmap_unchanged":sha(ROADMAP)==road_sha,
        "schedule_unchanged":sha(SCHEDULE)==sched_sha,
    }
    for k,v in gates.items():
        log(f"{k} = {v}")

    log(f"snapshot_source = {source}")
    log(f"snapshot_device = {device}")
    log(f"recognized_count = {len(fields)}")
    log("recognized_fields = "+",".join(fields))
    log("numeric_health_values_logged = False")

    if not all(gates.values()):
        raise RuntimeError("R4 live ingest acceptance incomplete")

    log("")
    log(f"result_file = {RESULT}")
    log("[PASS] H185-R4 LIVE REAL HEALTH INGEST COMPLETE.")
    log("Real iPhone payload -> authenticated LAN bridge -> AURA latest.json is proven.")
    finish(0)

except SystemExit:
    raise
except Exception as exc:
    log("")
    log(f"[BLOCKED] {type(exc).__name__}: {exc}")
    log("Roadmap was not mutated.")
    finish(4)
finally:
    if PROC is not None:
        try:
            PROC.terminate()
            PROC.wait(timeout=4)
        except Exception:
            try:
                PROC.kill()
            except Exception:
                pass
    try:
        PIDFILE.unlink(missing_ok=True)
    except Exception:
        pass
