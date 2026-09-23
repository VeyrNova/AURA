
from __future__ import annotations
from pathlib import Path
import json, os, sys, tempfile, threading, urllib.request

ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
os.environ["AURA_FABRIC_TEST_NO_SLEEP"]="1"

from runtime.aura_fabric_http_gateway import GatewayConfig, GatewayService, create_server
from runtime.aura_fabric_provider_adapter import ProviderAdapter, AdapterResult
from runtime.aura_fabric_model_catalog import CatalogEntry
from runtime.aura_fabric_protocols import PROTOCOL_OPENAI_RESPONSES, normalize_request
from runtime.aura_terminal_reduction_kernel import reduce_terminal_output, SavingsLedger
from runtime.aura_fabric_local_optimizations import detect_command_prefix, session_title, normalize_filepath, suggest_next_action, quota_probe_local, capability_snapshot
from runtime.aura_fabric_voice_bridge import build_transcription_plan, detect_backends

class StatusFailure(RuntimeError):
    def __init__(self,message,status_code,retry_after=None):
        super().__init__(message); self.status_code=status_code; self.retry_after=retry_after

class Always429(ProviderAdapter):
    provider_id="prod-rate-limit"
    def catalog_entries(self):
        return (CatalogEntry(public_id="prod-rate-limit-model",provider_id=self.provider_id,provider_model_id="m1",display_name="RateLimit",capabilities=("text","streaming"),local=False,tos_status="internal"),)
    def generate(self,request,route_slug):
        raise StatusFailure("rate limited",429,0)

class Always401(ProviderAdapter):
    provider_id="prod-auth-fail"
    def catalog_entries(self):
        return (CatalogEntry(public_id="prod-auth-fail-model",provider_id=self.provider_id,provider_model_id="m1",display_name="AuthFail",capabilities=("text","streaming"),local=False,tos_status="internal"),)
    def generate(self,request,route_slug):
        raise StatusFailure("unauthorized",401)

class Success(ProviderAdapter):
    provider_id="prod-success"
    def catalog_entries(self):
        return (CatalogEntry(public_id="prod-success-model",provider_id=self.provider_id,provider_model_id="m1",display_name="Success",capabilities=("text","streaming"),local=True,tos_status="internal"),)
    def generate(self,request,route_slug):
        return AdapterResult(text="resilient:"+request.prompt_text,input_tokens=4,output_tokens=6,metadata={"production_test":True})

# 429: retry route 3 times, then same-turn failover.
service=GatewayService(retries_per_model=3)
service.register_adapter(Always429(),priority=0); service.register_adapter(Success(),priority=100)
service.set_alias("production-resilient",["prod-rate-limit-model","prod-success-model"])
req=normalize_request(PROTOCOL_OPENAI_RESPONSES,{"model":"production-resilient","input":"keep coding","stream":False})
resp=service.execute(req)
assert resp.provider_id=="prod-success"
assert resp.metadata["failover_used"] is True
failed=[x for x in resp.metadata["attempts"] if x["route"]=="prod-rate-limit/m1"]
assert len(failed)==3 and all(x["retryable"] is True and x["status_code"]==429 for x in failed)

# 401: do not waste retries, fail over immediately.
service2=GatewayService(retries_per_model=3)
service2.register_adapter(Always401(),priority=0); service2.register_adapter(Success(),priority=100)
service2.set_alias("auth-resilient",["prod-auth-fail-model","prod-success-model"])
req2=normalize_request(PROTOCOL_OPENAI_RESPONSES,{"model":"auth-resilient","input":"auth fallback","stream":False})
resp2=service2.execute(req2)
authfails=[x for x in resp2.metadata["attempts"] if x["route"]=="prod-auth-fail/m1"]
assert len(authfails)==1 and authfails[0]["retryable"] is False and authfails[0]["status_code"]==401

# Terminal Reduction Kernel: >90% reduction is possible on highly repetitive noise,
# while important failures survive.
noisy="\n".join([f"Downloading package chunk {i%10} 50%" for i in range(1000)]+["ERROR: final compiler failure at src/main.py:42"])
red=reduce_terminal_output("package install",noisy)
assert red.savings_percent>=90.0
assert "ERROR: final compiler failure" in red.output
assert red.raw_bytes>red.reduced_bytes

small=reduce_terminal_output("git status","On branch main\nnothing to commit\n")
assert small.mode=="passthrough_safe" and small.savings_percent==0.0

secret=reduce_terminal_output("tool","api_key = super-secret-value\n")
assert "super-secret-value" not in secret.output

with tempfile.TemporaryDirectory() as td:
    ledger=SavingsLedger(Path(td)/"gain.jsonl"); ledger.append(red,exit_code=1); summary=ledger.summary()
    assert summary["commands"]==1 and summary["output_byte_reduction_percent"]>=90.0

# Five provider-free local optimizations.
assert detect_command_prefix("git status")["provider_called"] is False
assert session_title("Fix AURA gateway failure")["provider_called"] is False
assert normalize_filepath(str(ROOT),ROOT)["provider_called"] is False
assert suggest_next_action("pytest",1,"FAILED test_x")["provider_called"] is False
assert quota_probe_local({"reference_headline_tokens_per_month":1300000000,"known_token_equivalent_reference_floor_per_month":0,"reference_headline_stale":False})["provider_called"] is False
assert len(capability_snapshot()["optimizations"])==5

# Voice bridge: local Whisper takes priority when detectable.
with tempfile.TemporaryDirectory() as td:
    bindir=Path(td)
    fake=bindir/("whisper.cmd" if os.name=="nt" else "whisper")
    fake.write_text("@echo off\n" if os.name=="nt" else "#!/bin/sh\nexit 0\n",encoding="utf-8")
    try: fake.chmod(0o755)
    except Exception: pass
    old_path=os.environ.get("PATH",""); old_nim=os.environ.get("AURA_NVIDIA_NIM_ASR_URL")
    os.environ["PATH"]=str(bindir)+os.pathsep+old_path
    os.environ["AURA_NVIDIA_NIM_ASR_URL"]="https://nim.example.invalid"
    try:
        plan=build_transcription_plan(bindir/"voice.wav",backend="auto",allow_remote=False)
        assert plan["selected_backend"]=="whisper_local_cli"
        remote=build_transcription_plan(bindir/"voice.wav",backend="nvidia_nim",allow_remote=False)
        assert remote["state"]=="blocked_remote_approval_required" and remote["selected_backend"] is None
    finally:
        os.environ["PATH"]=old_path
        if old_nim is None: os.environ.pop("AURA_NVIDIA_NIM_ASR_URL",None)
        else: os.environ["AURA_NVIDIA_NIM_ASR_URL"]=old_nim

# HTTP endpoints for efficiency and voice state.
server=create_server(service=service,config=GatewayConfig(host="127.0.0.1",port=0,retries_per_model=3),host="127.0.0.1",port=0)
th=threading.Thread(target=server.serve_forever,kwargs={"poll_interval":0.05},daemon=True); th.start()
base=f"http://{server.server_address[0]}:{server.server_address[1]}"
def getj(path):
    with urllib.request.urlopen(base+path,timeout=5) as r: return r.status,json.loads(r.read().decode())
try:
    s,e=getj("/aura/v1/efficiency"); assert s==200 and len(e["local_optimizations"]["optimizations"])==5
    s,v=getj("/aura/v1/voice"); assert s==200 and v["policy"]["local_first"] is True and v["policy"]["remote_requires_explicit_approval"] is True
    s,a=getj("/aura/v1/agents"); assert s==200 and a["agent_count"]==10
    s,p=getj("/aura/v1/providers"); assert s==200 and p["provider_count"]==50
    s,h=getj("/health"); assert s==200 and h["ready"] is True
    print("[PASS] ADF-E production failover + Terminal Reduction Kernel + voice bridges")
finally:
    server.shutdown(); server.server_close(); th.join(timeout=3)
