"""Provider connection test contracts. Real I/O is opt-in at the caller."""
from __future__ import annotations
import re, time
import json
import http.client
import ssl
from dataclasses import dataclass

STATUSES=("ok","not_configured","authentication_failed","permission_denied","network_error","timeout","rate_limited","invalid_configuration","provider_unavailable","model_not_found","invalid_response","unknown_error")
@dataclass(frozen=True)
class ProviderConnectionResult:
    provider_id:str; success:bool; status:str; message:str; latency_ms:int=0; models_available_count:int=0; tested_model:str=""
def sanitize_error(value):
    text=str(value or "")
    text=re.sub(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^?\s,;]+",r"\1[redacted]",text)
    text=re.sub(r"(?i)(api[-_ ]?key|token|secret)(\s*[:=]\s*)[^\s,;]+",r"\1\2[redacted]",text)
    text=re.sub(r"(?i)([?&](?:key|token|api_key)=)[^&\s]+",r"\1[redacted]",text)
    return text[:240]
class FakeProviderConnectionTester:
    def __init__(self, outcomes=None): self.outcomes=dict(outcomes or {})
    def test(self, provider_id, config=None):
        started=time.perf_counter(); outcome=self.outcomes.get(provider_id,"ok")
        if isinstance(outcome,ProviderConnectionResult): return outcome
        messages={"ok":"Connexion réussie","authentication_failed":"Clé API invalide","network_error":"Impossible de joindre le fournisseur","timeout":"Délai de connexion dépassé","not_configured":"Configurez d'abord ce fournisseur.","model_not_found":"Modèle introuvable"}
        return ProviderConnectionResult(provider_id,outcome=="ok",outcome,messages.get(outcome,"Échec de connexion"),int((time.perf_counter()-started)*1000),0,str((config or {}).get("selected_model", "")))

def map_http_status(provider_id, code, latency=0, model="", count=0):
    status={401:"authentication_failed",403:"permission_denied",429:"rate_limited"}.get(int(code), "provider_unavailable" if int(code)>=500 else "invalid_response")
    msg={"authentication_failed":"Clé API invalide","permission_denied":"Accès refusé","rate_limited":"Limite d'utilisation atteinte","provider_unavailable":"Fournisseur indisponible","invalid_response":"Réponse invalide"}[status]
    return ProviderConnectionResult(provider_id,False,status,msg,latency,count,model)
class HttpResponse:
    def __init__(self,status,payload): self.status=status; self.payload=payload
class ConnectionHttpClient:
    def __init__(self,request=None,timeout=8): self.request=request; self.timeout=timeout
    def get_json(self,url,headers=None,timeout=None):
        if self.request is not None: return self.request(url,headers or {},timeout or self.timeout)
        match=re.match(r"^(https?)://([^/]+)(/.*)?$",url)
        if not match: raise ValueError("invalid URL")
        scheme,authority,path=match.group(1),match.group(2),match.group(3) or "/"
        conn=(http.client.HTTPSConnection(authority,timeout=timeout or self.timeout,context=ssl.create_default_context()) if scheme=="https" else http.client.HTTPConnection(authority,timeout=timeout or self.timeout))
        try:
            conn.request("GET",path,headers=headers or {"User-Agent":"AURA-Native"}); response=conn.getresponse(); raw=response.read(2_000_000); payload=json.loads(raw.decode("utf-8")); return HttpResponse(response.status,payload)
        finally: conn.close()
class BaseConnectionTester:
    endpoint=""
    def __init__(self,store=None,http=None): self.store=store; self.http=http or ConnectionHttpClient()
    def _run(self,provider,url,headers,model=""):
        start=time.perf_counter()
        try:
            response=self.http.get_json(url,headers,8); code,payload=response.status,response.payload
            latency=int((time.perf_counter()-start)*1000)
            if code!=200:return map_http_status(provider,code,latency,model)
            if not isinstance(payload,dict): return ProviderConnectionResult(provider,False,"invalid_response","Réponse invalide",latency,0,model)
            rows=payload.get("data") or payload.get("models") or []
            return ProviderConnectionResult(provider,True,"ok","Connexion réussie",latency,len(rows) if isinstance(rows,list) else 0,model)
        except TimeoutError:return ProviderConnectionResult(provider,False,"timeout","Délai de connexion dépassé",int((time.perf_counter()-start)*1000),0,model)
        except Exception:return ProviderConnectionResult(provider,False,"network_error","Impossible de joindre le fournisseur",int((time.perf_counter()-start)*1000),0,model)
class OpenAIConnectionTester(BaseConnectionTester):
    def test(self,provider_id="openai",config=None):
        secret=self.store.get_secret("openai") if self.store else None
        if not secret:return ProviderConnectionResult("openai",False,"not_configured","Configurez d'abord ce fournisseur.")
        return self._run("openai","https://api.openai.com/v1/models",{"Authorization":"Bearer "+secret},(config or {}).get("selected_model",""))
class AnthropicConnectionTester(OpenAIConnectionTester):
    def test(self,provider_id="anthropic",config=None):
        secret=self.store.get_secret("anthropic") if self.store else None
        if not secret:return ProviderConnectionResult("anthropic",False,"not_configured","Configurez d'abord ce fournisseur.")
        return self._run("anthropic","https://api.anthropic.com/v1/models",{"x-api-key":secret,"anthropic-version":"2023-06-01"},(config or {}).get("selected_model",""))
class GeminiConnectionTester(OpenAIConnectionTester):
    def test(self,provider_id="gemini",config=None):
        secret=self.store.get_secret("gemini") if self.store else None
        if not secret:return ProviderConnectionResult("gemini",False,"not_configured","Configurez d'abord ce fournisseur.")
        return self._run("gemini","https://generativelanguage.googleapis.com/v1beta/models?key="+secret,{},(config or {}).get("selected_model",""))
class OllamaConnectionTester(BaseConnectionTester):
    def test(self,provider_id="ollama",config=None):
        cfg=config or {}; host=str(cfg.get("base_url") or "").rstrip("/")
        if not re.match(r"^https?://[^/]+$",host):return ProviderConnectionResult("ollama",False,"invalid_configuration","Configuration invalide")
        result=self._run("ollama",host+"/api/tags",{},cfg.get("selected_model",""))
        if result.success and result.tested_model and result.models_available_count==0:return ProviderConnectionResult("ollama",False,"model_not_found","Modèle introuvable",result.latency_ms,0,result.tested_model)
        return result
class OpenAICompatibleConnectionTester(BaseConnectionTester):
    def test(self,provider_id="custom_openai",config=None):
        cfg=config or {}; base=str(cfg.get("base_url") or "").rstrip("/")
        if not re.match(r"^https?://[^/]+$",base):return ProviderConnectionResult("custom_openai",False,"invalid_configuration","Configuration invalide")
        headers={}; secret=self.store.get_secret("custom_openai") if self.store else None
        if secret: headers["Authorization"]="Bearer "+secret
        return self._run("custom_openai",base+"/models",headers,cfg.get("selected_model",""))
def build_connection_testers(store, http=None):
    return {"openai":OpenAIConnectionTester(store,http),"anthropic":AnthropicConnectionTester(store,http),"gemini":GeminiConnectionTester(store,http),"ollama":OllamaConnectionTester(store,http),"custom_openai":OpenAICompatibleConnectionTester(store,http)}
