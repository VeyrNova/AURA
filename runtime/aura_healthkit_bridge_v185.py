from __future__ import annotations
# AURA_H185_R2_EXPLICIT_LAN_PAIRING_IPHONE_SHORTCUT_TRANSPORT
# AURA_H185_R3_LIVE_IPHONE_VALIDATE_RECEIPT
import argparse, hmac, json, os, tempfile, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCHEMA="aura.healthkit.bridge.v185"
VITALS_SCHEMA="aura.vitals.local.v1"
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT=18585
MAX_BODY=2*1024*1024

NUMERIC_BOUNDS={
 "heart_rate_bpm":(20,260),"resting_heart_rate_bpm":(20,200),"hrv_ms":(0,500),
 "spo2_percent":(50,100),"temperature_c":(25,45),"respiratory_rate_bpm":(4,60),
 "sleep_duration_hours":(0,24),
}
ACTIVITY_BOUNDS={
 "move_kcal":(0,20000),"move_goal_kcal":(1,20000),"exercise_min":(0,1440),
 "exercise_goal_min":(1,1440),"stand_hours":(0,24),"stand_goal_hours":(1,24),
 "steps":(0,200000),"distance_km":(0,500),"active_energy_kcal":(0,20000),
}

def text(v,n=120): return " ".join(str(v or "").split())[:n]
def num(v,lo,hi):
    try: x=float(v)
    except Exception: return None
    if not lo<=x<=hi: return None
    return int(x) if x.is_integer() else x
def utcnow(): return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
def activity(raw):
    raw=raw if isinstance(raw,dict) else {}
    return {k:num(raw.get(k),*b) for k,b in ACTIVITY_BOUNDS.items()}

def sanitize(raw):
    if not isinstance(raw,dict): raise ValueError("payload_must_be_object")
    data=raw.get("data") if isinstance(raw.get("data"),dict) else raw
    act_src=data.get("activity") if isinstance(data.get("activity"),dict) else data
    out={
      "source":text(raw.get("source") or data.get("source") or "apple_health",80),
      "device":text(raw.get("device") or data.get("device") or "iPhone / Apple Watch",100),
      "updated_at":text(raw.get("updated_at") or data.get("updated_at") or utcnow(),60),
      "activity":activity(act_src),"heart_rate_series":[],"workouts":[]
    }
    for k,b in NUMERIC_BOUNDS.items(): out[k]=num(data.get(k),*b)
    series=data.get("heart_rate_series") if isinstance(data.get("heart_rate_series"),list) else []
    for p in series[-1440:]:
        if not isinstance(p,dict): continue
        bpm=num(p.get("bpm"),20,260); stamp=text(p.get("time"),40)
        if bpm is not None and stamp: out["heart_rate_series"].append({"time":stamp,"bpm":bpm})
    workouts=data.get("workouts") if isinstance(data.get("workouts"),list) else []
    for w in workouts[:20]:
        if not isinstance(w,dict): continue
        name=text(w.get("name") or w.get("type"),80)
        if not name: continue
        out["workouts"].append({
          "name":name,"start":text(w.get("start"),40),
          "duration_min":num(w.get("duration_min"),0,1440),
          "distance_km":num(w.get("distance_km"),0,500),
          "energy_kcal":num(w.get("energy_kcal"),0,20000),
          "avg_heart_rate_bpm":num(w.get("avg_heart_rate_bpm"),20,260),
        })
    return out

def recognized(data):
    fields=[]
    for k in NUMERIC_BOUNDS:
        if data.get(k) is not None: fields.append(k)
    for k,v in (data.get("activity") or {}).items():
        if v is not None: fields.append("activity."+k)
    if data.get("heart_rate_series"): fields.append("heart_rate_series")
    if data.get("workouts"): fields.append("workouts")
    return fields

def validate_payload(raw):
    data=sanitize(raw); fields=recognized(data)
    return {"ok":bool(fields),"valid":bool(fields),"recognized":fields,"data":data}

def has_measurements(data): return bool(recognized(data))

def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as h:
            json.dump(payload,h,ensure_ascii=False,indent=2); h.write("\n"); h.flush(); os.fsync(h.fileno())
        os.replace(tmp,path)
    finally:
        try:
            if os.path.exists(tmp): os.unlink(tmp)
        except Exception: pass

def load_config(path):
    cfg=json.loads(path.read_text(encoding="utf-8"))
    if len(str(cfg.get("token") or ""))<32: raise RuntimeError("invalid_existing_token")
    return cfg

class Bridge:
    def __init__(self,config,snapshot,pid):
        self.config_path=config; self.snapshot_path=snapshot; self.pid_path=pid
        self.validation_receipt_path=config.parent/"last_validation_v185.json"
        self.config=load_config(config); self.token=str(self.config["token"])
        self.host=str(self.config.get("host") or DEFAULT_HOST); self.port=int(self.config.get("port") or DEFAULT_PORT)
        self.started=time.time(); self.ingest_count=0; self.validate_count=0
    def health(self):
        return {"ok":True,"schema":SCHEMA,"service":"aura-healthkit-bridge","host":self.host,"port":self.port,
                "lan_pairing_enabled":bool(self.config.get("lan_pairing_enabled")),
                "outbound_network":False,"snapshot_path":str(self.snapshot_path),
                "validation_receipt_path":str(self.validation_receipt_path),
                "uptime_s":round(time.time()-self.started,3),"ingest_count":self.ingest_count,
                "validate_count":self.validate_count}
    def authorized(self,header):
        if not header or not header.startswith("Bearer "): return False
        return hmac.compare_digest(header[7:].strip(),self.token)
    def record_validation(self,raw,result,client_ip):
        data=result.get("data") if isinstance(result.get("data"),dict) else {}
        receipt={
          "schema":"aura.healthkit.validation-receipt.v185",
          "received_at":utcnow(),
          "client_ip":text(client_ip,64),
          "source":text(data.get("source"),80),
          "device":text(data.get("device"),100),
          "recognized":[text(x,80) for x in (result.get("recognized") or [])[:64]],
          "valid":bool(result.get("valid")),
          "contains_health_values":False
        }
        atomic_json(self.validation_receipt_path,receipt)
        self.validate_count+=1
        return receipt
    def ingest(self,raw):
        data=sanitize(raw)
        if not has_measurements(data): return {"ok":False,"error":"no_supported_measurements"}
        wrapper={"schema":VITALS_SCHEMA,"source":data["source"],"device":data["device"],"updated_at":data["updated_at"],"data":data}
        atomic_json(self.snapshot_path,wrapper); self.ingest_count+=1
        return {"ok":True,"accepted":True,"schema":SCHEMA,"recognized":recognized(data),
                "updated_at":wrapper["updated_at"],"snapshot_path":str(self.snapshot_path)}

class Handler(BaseHTTPRequestHandler):
    server_version="AURAHealthKitBridge/1.8.5-R3"
    @property
    def bridge(self): return self.server.bridge
    def log_message(self,fmt,*args): return
    def sendj(self,status,payload):
        body=json.dumps(payload,ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path=="/health": return self.sendj(200,self.bridge.health())
        if self.path=="/v1/schema":
            return self.sendj(200,{"ok":True,"schema":SCHEMA,"vitals_schema":VITALS_SCHEMA,
              "numeric_fields":NUMERIC_BOUNDS,"activity_fields":ACTIVITY_BOUNDS,
              "authentication":"Bearer token","validate_endpoint":"POST /v1/validate",
              "ingest_endpoint":"POST /v1/ingest","series_limit":1440,"workouts_limit":20,
              "validation_receipt_contains_health_values":False})
        return self.sendj(404,{"ok":False,"error":"not_found"})
    def do_POST(self):
        if self.path not in {"/v1/validate","/v1/ingest"}:
            return self.sendj(404,{"ok":False,"error":"not_found"})
        if not self.bridge.authorized(self.headers.get("Authorization")):
            return self.sendj(401,{"ok":False,"error":"unauthorized"})
        try: length=int(self.headers.get("Content-Length") or 0)
        except Exception: length=0
        if length<=0 or length>MAX_BODY:
            return self.sendj(413,{"ok":False,"error":"invalid_body_size"})
        try: raw=json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception: return self.sendj(400,{"ok":False,"error":"invalid_json"})
        if self.path=="/v1/validate":
            try:
                result=validate_payload(raw)
                if result.get("ok"):
                    self.bridge.record_validation(raw,result,self.client_address[0] if self.client_address else "")
            except Exception as exc:
                return self.sendj(400,{"ok":False,"error":"invalid_payload","detail":type(exc).__name__})
            public={k:v for k,v in result.items() if k!="data"}
            return self.sendj(200 if result.get("ok") else 422,public)
        try: result=self.bridge.ingest(raw)
        except Exception as exc:
            return self.sendj(400,{"ok":False,"error":"invalid_payload","detail":type(exc).__name__})
        return self.sendj(200 if result.get("ok") else 422,result)

def run_server(config,snapshot,pid):
    bridge=Bridge(config,snapshot,pid)
    lan=bool(bridge.config.get("lan_pairing_enabled"))
    if lan:
        if bridge.host not in {"0.0.0.0","::"}: raise RuntimeError("r2_lan_binding_policy")
    elif bridge.host not in {"127.0.0.1","localhost","::1"}:
        raise RuntimeError("r2_loopback_binding_policy")
    server=ThreadingHTTPServer((bridge.host,bridge.port),Handler); server.bridge=bridge
    pid.parent.mkdir(parents=True,exist_ok=True); pid.write_text(str(os.getpid()),encoding="ascii")
    try:
        print(json.dumps(bridge.health(),ensure_ascii=False),flush=True)
        server.serve_forever(poll_interval=.25)
    finally:
        try: server.server_close()
        except Exception: pass
        try: pid.unlink(missing_ok=True)
        except Exception: pass
    return 0

def selftest(root):
    root=Path(root)
    cfg=root/"cfg.json"
    atomic_json(cfg,{"schema":SCHEMA,"enabled":True,"host":"127.0.0.1","port":18585,
      "token":"x"*40,"lan_pairing_enabled":False})
    bridge=Bridge(cfg,root/"latest.json",root/"pid")
    sample={"source":"apple_health_test_fixture","device":"test-device","updated_at":"2026-01-01T00:00:00Z",
      "heart_rate_bpm":72,"steps":8123}
    v=validate_payload(sample)
    receipt=bridge.record_validation(sample,v,"192.168.1.99")
    wrong=bridge.authorized("Bearer wrong")
    right=bridge.authorized("Bearer "+bridge.token)
    result=bridge.ingest(sample)
    stored=json.loads((root/"latest.json").read_text(encoding="utf-8"))
    return {"ok":bool(v.get("ok") and receipt.get("contains_health_values") is False
      and receipt.get("client_ip")=="192.168.1.99" and (not wrong) and right and result.get("ok")
      and stored.get("schema")==VITALS_SCHEMA and stored.get("data",{}).get("activity",{}).get("steps")==8123),
      "validate_ok":v.get("ok"),"receipt_no_values":receipt.get("contains_health_values") is False,
      "receipt_client_ip":receipt.get("client_ip"),"unauthorized_rejected":not wrong,
      "authorized_accepted":right,"flat_steps_supported":stored.get("data",{}).get("activity",{}).get("steps")==8123}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--selftest",action="store_true"); ap.add_argument("--selftest-root",type=Path)
    args=ap.parse_args()
    if args.selftest:
        root=args.selftest_root or Path(tempfile.mkdtemp(prefix="aura_h185_r3_"))
        print(json.dumps(selftest(root),ensure_ascii=False,indent=2)); return 0
    local=Path(os.environ.get("LOCALAPPDATA",""))/"AURA"/"vitals"
    return run_server(local/"healthkit_bridge_v185.json",local/"latest.json",local/"healthkit_bridge_v185.pid")
if __name__=="__main__": raise SystemExit(main())
