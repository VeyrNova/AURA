"""Optional Resemble AI cloud TTS backend for AURA v0.7.1.3.5.

Uses the documented HTTP streaming endpoint so Business-only WebSocket access
is not required. API tokens remain local and are never logged.
"""
from __future__ import annotations

import json
import logging
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from config.settings import settings
from voice.errors import SpeechSynthesisUnavailableError
from voice.text_to_speech import PiperSynthesisMetrics, normalize_french_speech

logger = logging.getLogger("aura.voice.resemble")

@dataclass(frozen=True)
class ResembleVoice:
    voice_uuid: str
    name: str
    language: str = ""
    source: str = ""
    supported_languages: tuple[str, ...] = ()
    sample_url: str = ""

    @property
    def supports_french(self) -> bool:
        langs = (self.language, *self.supported_languages)
        return any(str(lang or "").lower().replace("_", "-").startswith("fr") for lang in langs)

class ResembleTTS:
    _voices_cache: tuple[float, tuple[ResembleVoice, ...]] = (0.0, ())
    _lock = threading.Lock()

    def __init__(self, profile):
        self.profile = profile
        self._stop_event = threading.Event()

    @property
    def voice_label(self) -> str:
        name = str(getattr(self.profile, "resemble_voice_name", "") or "").strip()
        uid = str(getattr(self.profile, "resemble_voice_uuid", "") or "").strip()
        return f"Resemble · {name or uid or 'voix non choisie'}"

    @staticmethod
    def dependency_available() -> bool:
        try:
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        return bool(settings.RESEMBLE_ENABLED and settings.RESEMBLE_API_KEY and
                    str(getattr(self.profile, "resemble_voice_uuid", "") or "").strip() and self.dependency_available())
    def model_ready(self) -> bool: return self.is_available()
    def warmup(self) -> None: return None
    def stop(self) -> None: self._stop_event.set()

    @staticmethod
    def _safe_detail(raw: bytes | str) -> str:
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                text = str(payload.get("message") or payload.get("detail") or payload.get("error") or text)
        except Exception:
            pass
        secret = str(settings.RESEMBLE_API_KEY or "")
        if secret: text = text.replace(secret, "[REDACTED]")
        return " ".join(text.split())[:500]

    @classmethod
    def list_voices(cls, *, force_refresh: bool=False) -> tuple[ResembleVoice,...]:
        if not settings.RESEMBLE_API_KEY:
            raise SpeechSynthesisUnavailableError("Clé Resemble AI non configurée.")
        now=time.monotonic()
        with cls._lock:
            at,cached=cls._voices_cache
            if cached and not force_refresh and now-at<float(settings.RESEMBLE_VOICE_CACHE_SECONDS): return cached
        query=urllib.parse.urlencode({
            "page": 1,
            "page_size": 1000,
            "advanced": "true",
            "sample_url": "true",
            "filters": "true",
        })
        req=urllib.request.Request(settings.RESEMBLE_API_BASE.rstrip("/")+"/voices?"+query,
            headers={"Authorization":"Bearer "+settings.RESEMBLE_API_KEY,"Accept":"application/json"},method="GET")
        try:
            with urllib.request.urlopen(req,timeout=float(settings.RESEMBLE_TIMEOUT_SECONDS)) as r:
                payload=json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw=b""
            try: raw=exc.read(4096)
            except Exception: pass
            detail=cls._safe_detail(raw)
            raise SpeechSynthesisUnavailableError(f"Resemble HTTP {exc.code}"+(f" · {detail}" if detail else "")) from exc
        items=payload.get("items") or [] if isinstance(payload,dict) else []
        out=[]
        for item in items:
            if not isinstance(item,dict): continue
            uid=str(item.get("uuid") or "").strip(); name=str(item.get("name") or uid).strip()
            if not uid: continue
            raw_langs = item.get("supported_languages") or []
            if isinstance(raw_langs, str):
                raw_langs = [raw_langs]
            supported = tuple(str(v).strip() for v in raw_langs if str(v).strip())
            sample = str(item.get("sample_url") or item.get("sample_audio_url") or "").strip()
            out.append(ResembleVoice(
                uid,
                name,
                str(item.get("default_language") or ""),
                str(item.get("source") or ""),
                supported,
                sample,
            ))
        result=tuple(sorted(out,key=lambda x:(0 if x.supports_french else 1,x.name.casefold())))
        with cls._lock: cls._voices_cache=(time.monotonic(),result)
        french_count = sum(1 for voice in result if voice.supports_french)
        logger.info("Resemble voices loaded count=%d french_compatible=%d advanced=True",len(result),french_count)
        return result

    @staticmethod
    def _parse_wav_prefix(buffer: bytearray) -> tuple[int,int,int,int] | None:
        """Return (data_offset, sample_rate, channels, bits) once WAV data header is complete."""
        if len(buffer)<12 or bytes(buffer[:4])!=b"RIFF" or bytes(buffer[8:12])!=b"WAVE": return None
        pos=12; sample_rate=0; channels=0; bits=0
        while pos+8<=len(buffer):
            cid=bytes(buffer[pos:pos+4]); size=struct.unpack_from("<I",buffer,pos+4)[0]; data_pos=pos+8
            if cid==b"fmt " and data_pos+min(size,16)<=len(buffer) and size>=16:
                _fmt,channels,sample_rate,_br,_ba,bits=struct.unpack_from("<HHIIHH",buffer,data_pos)
            if cid==b"data":
                if sample_rate and channels and bits: return data_pos,sample_rate,channels,bits
                return None
            next_pos=data_pos+size+(size&1)
            if next_pos>len(buffer): return None
            pos=next_pos
        return None

    def speak(self,text:str):
        if not self.is_available(): raise SpeechSynthesisUnavailableError("Resemble AI n'est pas configuré ou aucune voix n'est sélectionnée.")
        clean=normalize_french_speech(str(text or "").strip())
        if not clean:return None
        if len(clean)>int(settings.CLOUD_TTS_MAX_SPEECH_CHARS): raise SpeechSynthesisUnavailableError("Réponse trop longue pour le canal cloud concis.")
        uid=str(getattr(self.profile,"resemble_voice_uuid","") or "").strip()
        body={"voice_uuid":uid,"data":clean,"precision":"PCM_16","sample_rate":24000,"use_hd":False}
        req=urllib.request.Request(settings.RESEMBLE_STREAM_URL,data=json.dumps(body,ensure_ascii=False).encode("utf-8"),
            headers={"Authorization":"Bearer "+settings.RESEMBLE_API_KEY,"Content-Type":"application/json","Accept":"audio/wav"},method="POST")
        import sounddevice as sd
        started=time.perf_counter(); first_audio=0.0; played=0; self._stop_event.clear(); prefix=bytearray(); stream=None
        try:
            with urllib.request.urlopen(req,timeout=float(settings.RESEMBLE_TIMEOUT_SECONDS)) as response:
                while not self._stop_event.is_set():
                    chunk=response.read(max(2048,int(settings.RESEMBLE_STREAM_CHUNK_BYTES)))
                    if not chunk: break
                    if stream is None:
                        prefix.extend(chunk)
                        parsed=self._parse_wav_prefix(prefix)
                        if parsed is None:
                            if len(prefix)>65536: raise SpeechSynthesisUnavailableError("Flux WAV Resemble non reconnu.")
                            continue
                        off,rate,channels,bits=parsed
                        if bits!=16: raise SpeechSynthesisUnavailableError(f"Flux Resemble PCM {bits} bits non supporté.")
                        stream=sd.RawOutputStream(samplerate=rate,channels=channels,dtype="int16"); stream.start()
                        chunk=bytes(prefix[off:]); prefix.clear()
                    if len(chunk)%2: chunk=chunk[:-1]
                    if chunk:
                        stream.write(chunk); played+=len(chunk)
                        if first_audio<=0:first_audio=time.perf_counter()-started
        except urllib.error.HTTPError as exc:
            raw=b""
            try: raw=exc.read(4096)
            except Exception: pass
            detail=self._safe_detail(raw)
            if exc.code in {401, 402} and "consumed all your credits" in detail.lower():
                raise SpeechSynthesisUnavailableError("Resemble : crédits TTS épuisés sur ce compte.") from exc
            raise SpeechSynthesisUnavailableError(f"Resemble HTTP {exc.code}"+(f" · {detail}" if detail else "")) from exc
        except SpeechSynthesisUnavailableError: raise
        except Exception as exc: raise SpeechSynthesisUnavailableError(f"Synthèse Resemble indisponible ({type(exc).__name__}).") from exc
        finally:
            if stream is not None:
                try: stream.stop(); stream.close()
                except Exception: pass
        total=time.perf_counter()-started; ttfa=first_audio or total
        if played<=0: raise SpeechSynthesisUnavailableError("Resemble n'a retourné aucun audio exploitable.")
        logger.info("Resemble TTS chars=%d ttfa=%.3fs total=%.3fs pcm_bytes=%d",len(clean),ttfa,total,played)
        return PiperSynthesisMetrics(device="cloud",model_load_seconds=0.0,synthesis_seconds=ttfa,
            playback_seconds=max(0,total-ttfa),text_chars=len(clean),time_to_audio_seconds=ttfa,chunk_count=1,streaming=True)
