"""Native provider boundary. No SDK or historical transport is used."""
from dataclasses import dataclass
import json
import os
from urllib.parse import urlencode
from urllib import error, request
import random
import time
from aura_native.core.contracts import CommandError
from aura_native.agent.pcc4_debug import pcc4_trace

@dataclass(frozen=True)
class ProviderResponse:
    text:str; provider:str; model:str; finish_reason:str=""; provider_request_id:str=""

@dataclass(frozen=True)
class ProviderChunk:
    text:str; provider:str; model:str; done:bool=False; finish_reason:str=""; provider_request_id:str=""


class NoProvider:
    name="unavailable"
    available=False
    def error(self): return CommandError("provider_unavailable","No native inference provider is configured")

class FakeProvider:
    """Deterministic offline provider for native tests; it has no transport."""
    name="fake"
    def __init__(self,text="Réponse locale de test",*,failure=None): self.text,self.failure=text,failure; self.calls=[]; self.available=True
    def error(self): return CommandError("provider_unavailable","Fake provider disabled")
    def generate(self,messages):
        self.calls.append(tuple(messages))
        if self.failure: raise ProviderFailure(self.failure,"Fake provider failure")
        return ProviderResponse(str(self.text),"fake","offline-test","stop","fake-0")
    def generate_stream(self,messages,*,cancel_event=None):
        response=self.generate(messages)
        yield ProviderChunk(response.text,response.provider,response.model,True,response.finish_reason,response.provider_request_id)

class StreamingFakeProvider(FakeProvider):
    """Offline chunk source; optional delay exercises cancellation safely."""
    name="streaming-fake"
    def __init__(self,chunks=("Réponse ","offline"),*,delay=0.0,failure=None):
        super().__init__("".join(chunks),failure=failure); self.chunks=tuple(chunks); self.delay=float(delay)
    def generate_stream(self,messages,*,cancel_event=None):
        import time
        self.calls.append(tuple(messages))
        if self.failure: raise ProviderFailure(self.failure,"Streaming fake failure")
        for index,text in enumerate(self.chunks):
            if self.delay: time.sleep(self.delay)
            if cancel_event is not None and cancel_event.is_set(): return
            yield ProviderChunk(str(text),"streaming-fake","offline-test",index == len(self.chunks)-1,"stop" if index == len(self.chunks)-1 else "",f"fake-{index}")

class OllamaProvider:
    name="ollama"
    def __init__(self,settings,*,opener=request.urlopen): self.settings,self._open=settings,opener
    @property
    def available(self): return self.settings.provider_name=="ollama" and bool(self.settings.model)
    def error(self):
        return CommandError("provider_unavailable","Ollama native provider is not configured")
    def generate(self,messages):
        if not self.available: raise ProviderFailure("provider_unavailable","Ollama model is not configured")
        payload=json.dumps({"model":self.settings.model,"messages":messages,"stream":False,"think":False}).encode("utf-8")
        req=request.Request(self.settings.ollama_host+"/api/chat",data=payload,headers={"Content-Type":"application/json"},method="POST")
        try:
            with self._open(req,timeout=self.settings.timeout_seconds) as response: raw=response.read()
        except TimeoutError as exc: raise ProviderFailure("provider_timeout","Provider timeout") from exc
        except error.HTTPError as exc:
            code="authentication_failed" if exc.code==401 else "permission_denied" if exc.code==403 else "rate_limited" if exc.code==429 else "provider_unavailable" if exc.code>=500 else "invalid_response"; raise ProviderFailure(code,"Provider HTTP error") from exc
        except error.URLError as exc: raise ProviderFailure("provider_network_error","Provider connection failed") from exc
        try: data=json.loads(raw.decode("utf-8")); text=str(data["message"]["content"]).strip()
        except (ValueError,KeyError,TypeError,UnicodeDecodeError) as exc: raise ProviderFailure("provider_invalid_response","Provider response is invalid") from exc
        if not text: raise ProviderFailure("provider_invalid_response","Provider response is empty")
        return ProviderResponse(text,"ollama",str(data.get("model") or self.settings.model),str(data.get("done_reason") or ""))
    def generate_stream(self,messages,*,cancel_event=None):
        if not self.available: raise ProviderFailure("provider_unavailable","Ollama model is not configured")
        # Ask Ollama for answer text only.  Reasoning tokens are not part of the
        # native conversation contract and must not become user-visible deltas.
        payload=json.dumps({"model":self.settings.model,"messages":messages,"stream":True,"think":False}).encode("utf-8")
        req=request.Request(self.settings.ollama_host+"/api/chat",data=payload,headers={"Content-Type":"application/json"},method="POST")
        try:
            with self._open(req,timeout=self.settings.timeout_seconds) as response:
                for raw in response:
                    if cancel_event is not None and cancel_event.is_set():
                        return
                    if not raw.strip():
                        continue
                    try: data=json.loads(raw.decode("utf-8")); text=str(data.get("message",{}).get("content") or "")
                    except (ValueError,TypeError,UnicodeDecodeError) as exc: raise ProviderFailure("provider_invalid_response","Provider stream is invalid") from exc
                    # Ollama terminates a normal stream with a `done` record
                    # whose message may be absent, empty, or whitespace-only.
                    # It is a completion marker, not an invalid response.
                    yield ProviderChunk(text,"ollama",str(data.get("model") or self.settings.model),bool(data.get("done",False)),str(data.get("done_reason") or ""))
        except TimeoutError as exc: raise ProviderFailure("provider_timeout","Provider timeout") from exc
        except error.HTTPError as exc:
            code="authentication_failed" if exc.code==401 else "permission_denied" if exc.code==403 else "rate_limited" if exc.code==429 else "provider_unavailable" if exc.code>=500 else "invalid_response"
            raise ProviderFailure(code,"Provider HTTP error") from exc
        except error.URLError as exc: raise ProviderFailure("provider_network_error","Provider connection failed") from exc


class GeminiRuntimeProvider:
    """Gemini REST streaming adapter; its API key stays inside this instance."""
    name = "gemini"
    supports_tools = False

    def __init__(self, *, model, api_key, timeout_seconds=45.0, opener=request.urlopen,
                 max_attempts=3, base_delay=1.0, max_delay=30.0, jitter=0.1, random_fn=None):
        self.model = str(model or "").strip()
        self._api_key = str(api_key or "")
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 180.0))
        self._open = opener
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay = max(0.0, float(base_delay))
        self.max_delay = max(0.0, float(max_delay))
        self.jitter = max(0.0, min(float(jitter), 1.0))
        self._random = random_fn or random.random

    @property
    def available(self):
        return bool(self.model and self._api_key)

    def error(self):
        return CommandError("provider_not_configured", "Configurez ce fournisseur dans IA & Intégrations.")

    @staticmethod
    def _payload(messages):
        system = []
        contents = []
        for message in messages:
            role = str(message.get("role", "user"))
            text = str(message.get("content", ""))
            if not text:
                continue
            if role == "system":
                system.append(text)
                continue
            if role not in ("user", "assistant"):
                continue
            mapped = "model" if role == "assistant" else "user"
            if contents and contents[-1]["role"] == mapped:
                contents[-1]["parts"][0]["text"] += "\n\n" + text
            else:
                contents.append({"role": mapped, "parts": [{"text": text}]})
        payload={"contents": contents}
        if system:
            payload["systemInstruction"]={"parts":[{"text":"\n\n".join(system)}]}
        return payload

    @staticmethod
    def _response_text(data):
        candidates = data.get("candidates") if isinstance(data, dict) else None
        if not isinstance(candidates, list) or not candidates:
            return ""
        content = candidates[0].get("content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else []
        return "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))

    @staticmethod
    def _http_failure(code, retry_after=None):
        if code == 400:
            return ProviderFailure("invalid_response", "Gemini a retourné une requête invalide.", http_status=code, stage="http_response", retry_after=retry_after)
        if code == 401:
            return ProviderFailure("authentication_failed", "La clé Gemini est invalide.", http_status=code, stage="http_response", retry_after=retry_after)
        if code == 403:
            return ProviderFailure("permission_denied", "Gemini a refusé cette requête.", http_status=code, stage="http_response", retry_after=retry_after)
        if code == 404:
            return ProviderFailure("model_not_found", "Le modèle Gemini est introuvable.", http_status=code, stage="http_response", retry_after=retry_after)
        if code in (408,):
            return ProviderFailure("timeout", "Gemini a dépassé le délai autorisé.", http_status=code, stage="http_response", retry_after=retry_after)
        if code == 429:
            return ProviderFailure("rate_limited", "Gemini limite temporairement les requêtes.", http_status=code, stage="http_response", retry_after=retry_after)
        if code >= 500:
            return ProviderFailure("provider_unavailable", "Gemini est temporairement indisponible.", http_status=code, stage="http_response", retry_after=retry_after)
        return ProviderFailure("invalid_response", "Gemini a retourné une réponse invalide.", http_status=code, stage="http_response", retry_after=retry_after)

    @staticmethod
    def _retry_after(headers):
        if headers is None:
            return None
        try:
            value = headers.get("Retry-After")
            seconds = float(str(value).strip())
            return seconds if seconds >= 0 else None
        except (AttributeError, TypeError, ValueError):
            return None

    def _retry_delay(self, retry_index, retry_after=None):
        if retry_after is not None:
            delay = retry_after
        else:
            delay = self.base_delay * (2 ** max(0, retry_index - 1))
            if self.jitter:
                delay += delay * self.jitter * self._random()
        return min(self.max_delay, max(0.0, delay))

    def _wait_backoff(self, delay, cancel_event):
        if delay <= 0:
            return bool(cancel_event is not None and cancel_event.is_set())
        if cancel_event is not None:
            return cancel_event.wait(delay)
        time.sleep(delay)
        return False

    @staticmethod
    def _sse_data(response):
        """Yield JSON SSE data while tolerating split and blank keepalive lines."""
        chunk_buffer = ""
        event_buffer = ""

        def decode(value):
            try:
                return json.loads(value)
            except (ValueError, TypeError, UnicodeDecodeError) as exc:
                raise ProviderFailure("invalid_response", "Gemini a retourné un flux invalide.", stage="sse") from exc

        def accept_line(line):
            nonlocal event_buffer
            stripped = line.strip()
            if not stripped or stripped.startswith(":"):
                return []
            if not stripped.startswith("data:"):
                return []
            value = stripped[5:].strip()
            if event_buffer:
                event_buffer += value
            else:
                event_buffer = value
            try:
                result = decode(event_buffer)
            except ProviderFailure:
                return []
            event_buffer = ""
            return [result]

        for raw in response:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            chunk_buffer += text
            while "\n" in chunk_buffer:
                line, chunk_buffer = chunk_buffer.split("\n", 1)
                for item in accept_line(line.rstrip("\r")):
                    yield item
        if chunk_buffer:
            for item in accept_line(chunk_buffer):
                yield item
        if event_buffer:
            raise ProviderFailure("invalid_response", "Gemini a retourné un flux incomplet.", stage="sse")

    def generate(self, messages):
        parts = []
        last = None
        for chunk in self.generate_stream(messages):
            if chunk.text:
                parts.append(chunk.text)
            last = chunk
        if last is None or not "".join(parts).strip():
            raise ProviderFailure("invalid_response", "Gemini n’a pas retourné de réponse utilisable.")
        return ProviderResponse("".join(parts), "gemini", self.model, last.finish_reason, last.provider_request_id)

    def _generate_once(self, messages, *, cancel_event=None):
        if not self.available:
            raise ProviderFailure("provider_not_configured", "Configurez ce fournisseur dans IA & Intégrations.")
        body = json.dumps(self._payload(messages), ensure_ascii=False).encode("utf-8")
        query = urlencode({"alt": "sse"})
        model_path=self.model.removeprefix("models/")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_path}:streamGenerateContent?{query}"
        req = request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key}, method="POST")
        emitted = False
        finish_reason = ""
        try:
            try:
                response = self._open(req, timeout=self.timeout_seconds)
            except TimeoutError as exc:
                raise ProviderFailure("timeout", "La requête Gemini a expiré.", stage="connect") from exc
            except error.HTTPError:
                raise
            except error.URLError as exc:
                raise ProviderFailure("network_error", "Gemini est injoignable.", stage="connect") from exc
            with response:
                for data in self._sse_data(response):
                    if cancel_event is not None and cancel_event.is_set():
                        return
                    text = self._response_text(data)
                    candidates = data.get("candidates", []) if isinstance(data, dict) else []
                    if candidates and isinstance(candidates[0], dict):
                        finish_reason = str(candidates[0].get("finishReason") or finish_reason)
                    if text:
                        emitted = True
                        if self._api_key:
                            text = text.replace(self._api_key, "[redacted]")
                        yield ProviderChunk(text, "gemini", self.model, False, finish_reason)
            if cancel_event is not None and cancel_event.is_set():
                return
        except error.HTTPError as exc:
            raise self._http_failure(int(exc.code), self._retry_after(getattr(exc, "headers", None))) from exc
        except TimeoutError as exc:
            raise ProviderFailure("timeout", "La requête Gemini a expiré.", stage="read") from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError):
                raise ProviderFailure("timeout", "La requête Gemini a expiré.", stage="read") from exc
            raise ProviderFailure("network_error", "Gemini est injoignable.", stage="read") from exc
        except ProviderFailure:
            raise
        except Exception as exc:
            raise ProviderFailure("network_error", "Gemini est injoignable.", stage="transport") from exc
        if not emitted:
            raise ProviderFailure("invalid_response", "Gemini n’a pas retourné de réponse utilisable.")
        yield ProviderChunk("", "gemini", self.model, True, finish_reason)

    def generate_stream(self, messages, *, cancel_event=None):
        """Stream Gemini with bounded pre-first-delta transient retries."""
        emitted = False
        for attempt in range(1, self.max_attempts + 1):
            if cancel_event is not None and cancel_event.is_set():
                return
            try:
                for chunk in self._generate_once(messages, cancel_event=cancel_event):
                    if chunk.text:
                        emitted = True
                    yield chunk
                return
            except ProviderFailure as exc:
                retryable = (
                    not emitted
                    and attempt < self.max_attempts
                    and exc.code in {"provider_unavailable", "network_error", "timeout", "rate_limited"}
                )
                if not retryable:
                    raise
                delay = self._retry_delay(attempt, exc.retry_after)
                pcc4_trace(
                    "PCC4_RETRY_SCHEDULED",
                    provider=self.name,
                    model=self.model,
                    request_id=getattr(self, "_pcc4_request_id", ""),
                    error_code=exc.code,
                    http_status=exc.http_status or "",
                    stage=exc.stage,
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    delay_ms=int(delay * 1000),
                )
                if self._wait_backoff(delay, cancel_event):
                    return
                pcc4_trace(
                    "PCC4_RETRY_STARTED",
                    provider=self.name,
                    model=self.model,
                    request_id=getattr(self, "_pcc4_request_id", ""),
                    attempt=attempt + 1,
                )
                continue

class ProviderFailure(Exception):
    def __init__(self,code,message,*,http_status=None,stage="",retry_after=None):
        self.code,self.message,self.http_status,self.stage,self.retry_after=code,message,http_status,stage,retry_after
        super().__init__(message)
