
from __future__ import annotations
from pathlib import Path
from typing import Any
import json, os, platform, shutil
ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
CATALOG_PATH=ROOT/"ci"/"aura_fabric_coding_agent_catalog.json"
def _catalog(): return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
def _agents(): return {a["agent_id"]:a for a in _catalog()["agents"]}
def _platform():
    p=platform.system().lower()
    return {"windows":"windows","darwin":"darwin","linux":"linux"}.get(p,p)
def detect_agent(agent_id:str):
    spec=_agents()[agent_id]; found=None
    for exe in spec["executables"]:
        found=shutil.which(exe)
        if found: break
    cur=_platform()
    return {"agent_id":agent_id,"display_name":spec["display_name"],"installed":bool(found),"executable":found,
            "platform":cur,"platform_supported":cur in spec["platforms"],"support_level":spec["support_level"],
            "protocol":spec["protocol"],"bridge_mode":spec["bridge_mode"]}
def detection_snapshot():
    items=[detect_agent(aid) for aid in sorted(_agents())]
    return {"schema":"aura.fabric.agent-detection.v1","agent_count":len(items),"installed_count":sum(x["installed"] for x in items),"agents":items}
def _managed(agent_id): return ROOT/"runtime"/"developer_fabric"/"agent_bridges"/agent_id
def build_launch_plan(agent_id:str,*,model:str,workspace:str|Path,materialize:bool=False):
    if not model.strip(): raise ValueError("model is required")
    spec=_agents()[agent_id]; det=detect_agent(agent_id); g=_catalog()["gateway"]; managed=_managed(agent_id)
    env={"AURA_FABRIC_MODEL":model,"AURA_FABRIC_GATEWAY":g["root_url"],"AURA_TRK_EXECUTABLE":str(ROOT/"aura_trk.py"),"AURA_TRK_ENABLED":"1"}; sec={}; args=[]; files={}; notes=[]
    if agent_id=="claude_code":
        env.update({"ANTHROPIC_BASE_URL":g["anthropic_base_url"],"ANTHROPIC_MODEL":model,"CLAUDE_CODE_MAX_OUTPUT_TOKENS":os.environ.get("AURA_CLAUDE_CODE_MAX_OUTPUT_TOKENS","2048"),"CLAUDE_CODE_MAX_RETRIES":os.environ.get("AURA_CLAUDE_CODE_MAX_RETRIES","1"),"CLAUDE_CODE_DISABLE_THINKING":os.environ.get("AURA_CLAUDE_CODE_DISABLE_THINKING","1"),"MAX_THINKING_TOKENS":os.environ.get("AURA_CLAUDE_CODE_MAX_THINKING_TOKENS","0")}); sec["ANTHROPIC_AUTH_TOKEN"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
    elif agent_id=="codex":
        cfg=managed/"config.toml"
        files[str(cfg)]=('model = "'+model+'"\nmodel_provider = "aura"\n\n[model_providers.aura]\nname = "AURA Fabric Gateway"\nbase_url = "'+g["openai_base_url"]+'"\nenv_key = "AURA_FABRIC_CLIENT_TOKEN"\nwire_api = "responses"\nrequest_max_retries = 0\nstream_max_retries = 0\n')
        env["CODEX_HOME"]=str(managed); sec["AURA_FABRIC_CLIENT_TOKEN"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
    elif agent_id=="pi":
        ext=managed/"aura-provider.ts"
        files[str(ext)]=('import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";\nexport default function (pi: ExtensionAPI) {\n  pi.registerProvider("aura", {\n    baseUrl: "'+g["openai_base_url"]+'",\n    apiKey: "$AURA_FABRIC_CLIENT_TOKEN", api: "openai-responses",\n    models: [{ id: "'+model+'", name: "'+model+'", reasoning: true, input: ["text","image"], cost: { input:0, output:0, cacheRead:0, cacheWrite:0 }, contextWindow:200000, maxTokens:100000 }]\n  });\n}\n')
        args=["--no-extensions","--extension",str(ext),"--provider","aura","--model","aura/"+model]; sec["AURA_FABRIC_CLIENT_TOKEN"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
    elif agent_id=="opencode":
        cfg=managed/"opencode.json"
        files[str(cfg)]=json.dumps({"$schema":"https://opencode.ai/config.json","model":"aura/"+model,"providers":{"aura":{"name":"AURA Fabric Gateway","env":["AURA_FABRIC_CLIENT_TOKEN"],"package":"@opencode-ai/ai/providers/openai-compatible","settings":{"baseURL":g["openai_base_url"]},"models":{model:{"name":model}}}}},indent=2)
        env.update({"OPENCODE_CONFIG":str(cfg),"OPENCODE_DISABLE_AUTOUPDATE":"1"}); sec["AURA_FABRIC_CLIENT_TOKEN"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
    elif agent_id=="cline":
        data=managed/"data"; tpl=data/"settings"/"aura-provider-template.json"
        files[str(tpl)]=json.dumps({"schema":"aura.fabric.cline-provider-template.v1","provider":{"id":"aura","apiProvider":"openai-compatible","baseUrl":g["openai_base_url"],"modelId":model,"protocol":"openai-responses","credentialEnv":"AURA_FABRIC_CLIENT_TOKEN"}},indent=2)
        env["CLINE_DATA_DIR"]=str(data); args=["--model",model,"--provider","aura"]; sec["AURA_FABRIC_CLIENT_TOKEN"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
        notes.append("Provider template isolated; installed Cline schema may require interactive import/config.")
    elif agent_id=="hermes":
        cfg=managed/"config.yaml"
        files[str(cfg)]=('model:\n  default: "'+model+'"\n  provider: "custom:aura"\ncustom_providers:\n  - name: "aura"\n    base_url: "'+g["openai_base_url"]+'"\n    key_env: "AURA_FABRIC_CLIENT_TOKEN"\n    api_mode: "chat_completions"\n')
        env["HERMES_HOME"]=str(managed); sec["AURA_FABRIC_CLIENT_TOKEN"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
    elif agent_id=="deepseek_harness":
        env.update({"DEEPSEEK_BASE_URL":g["openai_base_url"],"AURA_DSH_MODEL":model}); sec["DEEPSEEK_API_KEY"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
    elif agent_id=="grok_build":
        env.update({"GROK_MODELS_BASE_URL":g["openai_base_url"],"GROK_MODELS_LIST_URL":g["model_catalog_url"]}); sec["XAI_API_KEY"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
    elif agent_id=="muse_code":
        cfgroot=managed/"xdg"; settings=cfgroot/"muse"/"settings.json"
        files[str(settings)]=json.dumps({"schema":"aura.fabric.muse-experimental-template.v1","model":model,"endpoint_transport":"openai_responses","base_url":g["openai_base_url"],"model_catalog":{"url":g["model_catalog_url"]},"credential_env":"AURA_FABRIC_CLIENT_TOKEN","experimental":True},indent=2)
        env.update({"XDG_CONFIG_HOME":str(cfgroot),"MUSE_NO_AUTO_UPDATE":"1"}); sec["META_API_KEY"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
        notes.append("Experimental beta bridge; no native Windows support claim.")
    elif agent_id=="aider":
        env.update({"AIDER_OPENAI_API_BASE":g["openai_base_url"],"AIDER_MODEL":"openai/"+model}); sec["AIDER_OPENAI_API_KEY"]="AURA_FABRIC_LOCAL_TOKEN|sentinel:aura-local"
    else: raise KeyError(agent_id)
    if materialize:
        for fn,content in files.items():
            p=Path(fn); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding="utf-8")
    return {"schema":"aura.fabric.agent-launch-plan.v1","agent_id":agent_id,"display_name":spec["display_name"],"support_level":spec["support_level"],"protocol":spec["protocol"],"bridge_mode":spec["bridge_mode"],"model":model,
            "workspace":str(Path(workspace).resolve()),"gateway":g,"detection":det,"executable":spec["executables"][0],"arguments":args,
            "environment_static":env,"environment_runtime_secret_refs":sec,"managed_files":sorted(files),"managed_file_contents":files,
            "materialized":materialize,"will_execute":False,"notes":notes}
def public_agent_catalog():
    data=_catalog(); det={x["agent_id"]:x for x in detection_snapshot()["agents"]}
    return {"schema":"aura.fabric.coding-agent-catalog-public.v1","agent_count":len(data["agents"]),"single_model_catalog":True,"gateway":data["gateway"],
            "agents":[{**a,"detection":det[a["agent_id"]]} for a in data["agents"]]}
