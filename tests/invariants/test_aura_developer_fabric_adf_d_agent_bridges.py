
from pathlib import Path
import json,os,subprocess,sys,tempfile,threading,urllib.request
ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from runtime.aura_fabric_agent_bridge import build_launch_plan,detection_snapshot,public_agent_catalog
from runtime.aura_fabric_http_gateway import GatewayConfig,build_test_service,create_server
EXPECTED={"claude_code","codex","pi","opencode","cline","hermes","deepseek_harness","grok_build","muse_code","aider"}
cat=public_agent_catalog(); assert cat["agent_count"]==10; assert {a["agent_id"] for a in cat["agents"]}==EXPECTED; assert cat["single_model_catalog"] is True; assert detection_snapshot()["agent_count"]==10
with tempfile.TemporaryDirectory() as td:
    plans={}
    for aid in EXPECTED:
        pl=build_launch_plan(aid,model="aura-test-model",workspace=td,materialize=False); plans[aid]=pl
        assert pl["will_execute"] is False and pl["materialized"] is False and "sk-" not in json.dumps(pl)
    assert plans["claude_code"]["protocol"]=="anthropic_messages"; assert plans["codex"]["protocol"]=="openai_responses"; assert "CODEX_HOME" in plans["codex"]["environment_static"]; assert "--extension" in plans["pi"]["arguments"]; assert "OPENCODE_CONFIG" in plans["opencode"]["environment_static"]; assert "CLINE_DATA_DIR" in plans["cline"]["environment_static"]; assert plans["muse_code"]["support_level"]=="experimental_beta"
cp=subprocess.run([sys.executable,str(ROOT/"launch_aura_dev_agent.py"),"codex","--model","aura-test-model","--workspace",str(ROOT)],cwd=str(ROOT),env={**os.environ,"AURA_ROOT":str(ROOT),"PYTHONPATH":str(ROOT)},capture_output=True,text=True,timeout=15)
assert cp.returncode==0 and json.loads(cp.stdout)["will_execute"] is False
def get_json(url):
    with urllib.request.urlopen(url,timeout=5) as r: return r.status,json.loads(r.read().decode())
service=build_test_service(include_failure_route=False,retries_per_model=2); server=create_server(service=service,config=GatewayConfig(host="127.0.0.1",port=0,retries_per_model=2),host="127.0.0.1",port=0)
th=threading.Thread(target=server.serve_forever,kwargs={"poll_interval":0.05},daemon=True); th.start(); base=f"http://{server.server_address[0]}:{server.server_address[1]}"
try:
    s,a=get_json(base+"/aura/v1/agents"); assert s==200 and a["agent_count"]==10
    s,p=get_json(base+"/aura/v1/providers"); assert s==200 and p["provider_count"]==50
    s,q=get_json(base+"/aura/v1/quotas"); assert s==200 and q["reference_headline_guaranteed"] is False
    s,h=get_json(base+"/health"); assert s==200 and h["ready"] is True
    print("[PASS] ADF-D 10 coding-agent compatibility + native launchers + IDE bridges")
finally:
    server.shutdown(); server.server_close(); th.join(timeout=3)
