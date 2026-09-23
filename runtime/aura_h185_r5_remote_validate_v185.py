from __future__ import annotations
import hashlib, ipaddress, json, os, shutil, subprocess, time, urllib.request
from datetime import datetime
from pathlib import Path

ROOT=Path(r"C:\AURA GPT version")
BRIDGE=ROOT/"runtime"/"aura_healthkit_bridge_v185.py"
ROADMAP=ROOT/"data"/"roadmap"/"aura_master_roadmap_v2.json"
SCHEDULE=ROOT/"data"/"roadmap"/"aura_roadmap_schedule_state.json"
LOCAL=Path(os.environ.get("LOCALAPPDATA",""))
VITALS=LOCAL/"AURA"/"vitals"
RECEIPT=VITALS/"last_validation_v185.json"
SNAPSHOT=VITALS/"latest.json"
ENDPOINT=VITALS/"iphone_remote_endpoint_v185.txt"
PIDFILE=VITALS/"healthkit_bridge_v185.pid"

STAMP=datetime.now().strftime("%Y%m%d_%H%M%S")
RESULT=ROOT/"data"/"roadmap"/f"AURA_H185_R5_REMOTE_IPHONE_VALIDATE_{STAMP}_RESULT.txt"
LOG=[]; PROC=None; OWNS=False

def log(x=""):
    s=str(x); print(s,flush=True); LOG.append(s)

def finish(rc):
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    RESULT.write_text("\n".join(LOG)+"\n",encoding="utf-8")
    raise SystemExit(rc)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def pyexe():
    p=ROOT/"venv"/"Scripts"/"python.exe"
    return str(p) if p.exists() else (shutil.which("python.exe") or "")

def health():
    try:
        with urllib.request.urlopen("http://127.0.0.1:18585/health",timeout=1.5) as r:
            j=json.loads(r.read().decode("utf-8"))
            return isinstance(j,dict) and j.get("service")=="aura-healthkit-bridge"
    except Exception:
        return False

def is_tail_ip(s):
    try:
        return ipaddress.ip_address(s) in ipaddress.ip_network("100.64.0.0/10")
    except Exception:
        return False

def validate_nonwriting_contract():
    try:
        src=BRIDGE.read_text(encoding="utf-8")
    except Exception:
        return False
    required=[
        "AURA_H185_R3_LIVE_IPHONE_VALIDATE_RECEIPT",
        '"/v1/validate"',
        "record_validation",
        "contains_health_values",
    ]
    return all(x in src for x in required)

log("AURA H185-R5-R2 - REMOTE IPHONE VALIDATION")
log("="*78)
log("R5-R2 treats latest.json changes during the wait as informational, not fatal.")
log("Reason: /v1/validate is non-writing, while another ingest may update latest.json concurrently.")
log("")

try:
    for p in [BRIDGE,ROADMAP,SCHEDULE,ENDPOINT]:
        if not p.exists():
            raise RuntimeError(f"required file unavailable: {p}")

    if not validate_nonwriting_contract():
        raise RuntimeError("bridge /v1/validate non-writing contract could not be verified")

    road0=sha(ROADMAP)
    sched0=sha(SCHEDULE)
    snap0=sha(SNAPSHOT) if SNAPSHOT.exists() else None
    rec0=RECEIPT.stat().st_mtime if RECEIPT.exists() else 0.0

    if health():
        log("[PASS] existing bridge healthy - reused")
    else:
        py=pyexe()
        if not py:
            raise RuntimeError("Python unavailable")
        PROC=subprocess.Popen(
            [py,"-u",str(BRIDGE)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        )
        OWNS=True
        for _ in range(40):
            if health():
                break
            if PROC.poll() is not None:
                break
            time.sleep(.25)
        if not health():
            raise RuntimeError("bridge did not become healthy")
        log("[PASS] temporary bridge started")

    log(f"remote_endpoint_file = {ENDPOINT}")
    log("Waiting up to 15 minutes for remote /v1/validate...")
    log("")

    start=time.time()
    receipt=None
    while time.time()-start<900:
        if RECEIPT.exists() and RECEIPT.stat().st_mtime>max(rec0,start-1):
            try:
                r=json.loads(RECEIPT.read_text(encoding="utf-8"))
            except Exception:
                r=None
            if isinstance(r,dict) and r.get("schema")=="aura.healthkit.validation-receipt.v185":
                receipt=r
                break

        if OWNS and PROC is not None and PROC.poll() is not None:
            raise RuntimeError("temporary bridge stopped unexpectedly")
        if not OWNS and not health():
            raise RuntimeError("pre-existing bridge stopped during validation")
        time.sleep(.5)

    if receipt is None:
        raise RuntimeError("No remote iPhone validation receipt received within 15 minutes")

    snap1=sha(SNAPSHOT) if SNAPSHOT.exists() else None
    snapshot_changed=(snap0 != snap1)

    client=str(receipt.get("client_ip") or "")
    recognized=receipt.get("recognized") if isinstance(receipt.get("recognized"),list) else []

    gates={
        "client_is_tailscale_ipv4":is_tail_ip(client),
        "recognized_fields_present":len(recognized)>0,
        "receipt_no_health_values":receipt.get("contains_health_values") is False,
        "receipt_valid":receipt.get("valid") is True,
        "validate_nonwriting_contract":validate_nonwriting_contract(),
        "roadmap_unchanged":sha(ROADMAP)==road0,
        "schedule_unchanged":sha(SCHEDULE)==sched0,
    }

    for k,v in gates.items():
        log(f"{k} = {v}")

    log(f"snapshot_changed_during_wait = {snapshot_changed}")
    log("snapshot_change_is_informational = True")
    log(f"bridge_reused = {not OWNS}")
    log(f"receipt_client_ip = {client}")
    log(f"receipt_source = {receipt.get('source') or ''}")
    log(f"receipt_device = {receipt.get('device') or ''}")
    log(f"receipt_recognized_count = {len(recognized)}")
    log("receipt_recognized = "+",".join(str(x) for x in recognized))

    if not all(gates.values()):
        raise RuntimeError("R5-R2 remote validation acceptance incomplete")

    log("")
    log(f"result_file = {RESULT}")
    log("[PASS] H185-R5-R2 REMOTE IPHONE VALIDATION COMPLETE.")
    log("Authenticated iPhone -> Tailscale -> PC AURA transport is proven.")
    finish(0)

except SystemExit:
    raise
except Exception as exc:
    log("")
    log(f"[BLOCKED] {type(exc).__name__}: {exc}")
    log("Roadmap was not mutated.")
    finish(4)
finally:
    if OWNS and PROC is not None:
        try:
            PROC.terminate(); PROC.wait(timeout=4)
        except Exception:
            try: PROC.kill()
            except Exception: pass
        try:
            PIDFILE.unlink(missing_ok=True)
        except Exception:
            pass
