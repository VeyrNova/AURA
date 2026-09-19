"""Explicit opt-in local Chatterbox Multilingual V3 adapter for AURA v0.7.1.3.5.

No package or model is downloaded silently. The backend is unavailable unless
CHATTERBOX_ENABLED=1 and CHATTERBOX_ALLOW_MODEL_LOAD=1 are explicitly set and
the chatterbox package is already installed. This keeps AURA's zero-cost local
fallback deterministic while allowing an honest RTX benchmark later.
"""
from __future__ import annotations

# AURA I18N R2 â€” dynamic Chatterbox language
import os as _aura_i18n_r2_chatter_os

def _aura_i18n_chatter_language() -> str:
    raw = str(
        _aura_i18n_r2_chatter_os.environ.get("AURA_TTS_LANGUAGE")
        or _aura_i18n_r2_chatter_os.environ.get("STT_LANGUAGE")
        or "fr"
    ).strip().lower()
    return "en" if raw.startswith("en") else "fr"

import logging, time
from pathlib import Path
from config.settings import settings
from voice.errors import SpeechSynthesisUnavailableError
from voice.text_to_speech import PiperSynthesisMetrics, normalize_french_speech
logger=logging.getLogger("aura.voice.chatterbox")

class ChatterboxTTS:
    _model=None
    _device=""
    def __init__(self,profile): self.profile=profile
    @property
    def voice_label(self): return "Chatterbox Multilingual V3 · local"
    @staticmethod
    def dependency_available():
        try:
            import chatterbox.mtl_tts, torch, sounddevice  # noqa
            return True
        except Exception:return False
    def is_available(self): return bool(settings.CHATTERBOX_ENABLED and settings.CHATTERBOX_ALLOW_MODEL_LOAD and self.dependency_available())
    def model_ready(self): return self.is_available()
    def stop(self): return None
    def warmup(self):
        if not self.is_available(): return
        self._load()
    @classmethod
    def _load(cls):
        if cls._model is not None:return cls._model
        if not settings.CHATTERBOX_ALLOW_MODEL_LOAD: raise SpeechSynthesisUnavailableError("Chatterbox bloqué: chargement local non autorisé explicitement.")
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        device="cuda" if settings.CHATTERBOX_DEVICE=="cuda" and torch.cuda.is_available() else "cpu"
        started=time.perf_counter(); cls._model=ChatterboxMultilingualTTS.from_pretrained(device=device,t3_model="v3"); cls._device=device
        logger.info("Chatterbox Multilingual V3 loaded device=%s elapsed=%.3fs",device,time.perf_counter()-started)
        return cls._model
    def speak(self,text:str):
        if not self.is_available(): raise SpeechSynthesisUnavailableError("Chatterbox Multilingual V3 n'est pas installé/autorisé.")
        clean=normalize_french_speech(str(text or "").strip())
        if not clean:return None
        model=self._load(); ref=str(getattr(self.profile,"chatterbox_reference_wav","") or self.profile.xtts_reference_wav or "").strip()
        kwargs={"language_id":_aura_i18n_chatter_language()}
        if ref and Path(ref).is_file(): kwargs["audio_prompt_path"]=ref
        import sounddevice as sd
        started=time.perf_counter(); wav=model.generate(clean,**kwargs); synth=time.perf_counter()-started
        arr=wav.detach().float().cpu().numpy()
        while getattr(arr,"ndim",1)>1: arr=arr[0]
        sd.play(arr,samplerate=int(model.sr),blocking=True); total=time.perf_counter()-started
        logger.info("Chatterbox TTS device=%s chars=%d first_audio=%.3fs total=%.3fs",self._device,len(clean),synth,total)
        return PiperSynthesisMetrics(device=self._device or "local",model_load_seconds=0.0,synthesis_seconds=synth,
            playback_seconds=max(0,total-synth),text_chars=len(clean),time_to_audio_seconds=synth,chunk_count=1,streaming=False)

# AURA I18N R5 — persisted TTS language authority
def _aura_i18n_chatter_language() -> str:
    try:
        import json as _json
        from pathlib import Path as _Path
        _base = os.environ.get("APPDATA") or str(_Path.home() / "AppData" / "Roaming")
        _p = _Path(_base) / "AURA" / "config" / "locale.json"
        if _p.is_file():
            _loc = str(_json.loads(_p.read_text(encoding="utf-8")).get("locale") or "").strip()
            if _loc == "en-US": return "en"
            if _loc == "fr-FR": return "fr"
    except Exception:
        pass
    _raw = str(os.environ.get("AURA_TTS_LANGUAGE") or os.environ.get("STT_LANGUAGE") or "fr").strip().lower()
    return "en" if _raw.startswith("en") else "fr"
