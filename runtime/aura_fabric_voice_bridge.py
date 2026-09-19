
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import uuid

@dataclass(frozen=True)
class VoicePolicy:
    local_first: bool = True
    remote_requires_explicit_approval: bool = True
    no_remote_by_default: bool = True

def _is_loopback(url: str) -> bool:
    try:
        host=urllib.parse.urlparse(url).hostname
    except Exception:
        return False
    return host in {"127.0.0.1","localhost","::1"}

def detect_backends() -> dict[str, Any]:
    whisper_cli=shutil.which("whisper")
    whisper_module=importlib.util.find_spec("whisper") is not None
    nim_url=os.environ.get("AURA_NVIDIA_NIM_ASR_URL","").strip()
    return {
        "schema":"aura.fabric.voice-backends.v1",
        "local_whisper_cli":{"available":bool(whisper_cli),"path":whisper_cli},
        "local_whisper_python":{"available":whisper_module},
        "nvidia_nim":{
            "configured":bool(nim_url),
            "base_url":nim_url or None,
            "loopback":_is_loopback(nim_url) if nim_url else None,
            "mode":"offline_transcription",
        },
        "policy":asdict(VoicePolicy()),
    }

def build_transcription_plan(audio_path: str | Path, *, language: str="auto", backend: str="auto", allow_remote: bool=False) -> dict[str, Any]:
    audio=Path(audio_path).expanduser().resolve()
    detected=detect_backends()
    selected=None
    if backend in {"auto","whisper_local"}:
        if detected["local_whisper_cli"]["available"]:
            selected="whisper_local_cli"
        elif detected["local_whisper_python"]["available"]:
            selected="whisper_local_python"
    if selected is None and backend in {"auto","nvidia_nim"} and detected["nvidia_nim"]["configured"]:
        url=detected["nvidia_nim"]["base_url"]
        if detected["nvidia_nim"]["loopback"] or allow_remote:
            selected="nvidia_nim_http"
    if backend=="nvidia_nim" and selected is None and detected["nvidia_nim"]["configured"] and not allow_remote:
        state="blocked_remote_approval_required"
    elif selected is None:
        state="unavailable"
    else:
        state="ready"
    return {
        "schema":"aura.fabric.voice-transcription-plan.v1",
        "audio_path":str(audio),
        "audio_exists":audio.is_file(),
        "language":language,
        "requested_backend":backend,
        "selected_backend":selected,
        "state":state,
        "allow_remote":bool(allow_remote),
        "provider_called":False,
        "detected":detected,
    }

def _multipart_body(audio: Path, language: str) -> tuple[bytes,str]:
    boundary="----AURA"+uuid.uuid4().hex
    chunks=[]
    def field(name,value):
        chunks.extend([f"--{boundary}\r\n".encode(),f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),str(value).encode(),b"\r\n"])
    field("language","multi" if language=="auto" else language)
    chunks.extend([f"--{boundary}\r\n".encode(),f'Content-Disposition: form-data; name="file"; filename="{audio.name}"\r\n'.encode(),b"Content-Type: application/octet-stream\r\n\r\n",audio.read_bytes(),b"\r\n",f"--{boundary}--\r\n".encode()])
    return b"".join(chunks),boundary

def transcribe(audio_path: str | Path, *, language: str="auto", backend: str="auto", allow_remote: bool=False, execute: bool=False) -> dict[str, Any]:
    plan=build_transcription_plan(audio_path,language=language,backend=backend,allow_remote=allow_remote)
    if not execute:
        return {**plan,"executed":False}
    audio=Path(plan["audio_path"])
    if not audio.is_file():
        raise FileNotFoundError(audio)
    selected=plan["selected_backend"]
    if not selected:
        raise RuntimeError("no approved transcription backend available: "+plan["state"])

    if selected=="whisper_local_cli":
        with tempfile.TemporaryDirectory(prefix="aura_whisper_") as td:
            model=os.environ.get("AURA_WHISPER_MODEL","base")
            cmd=[plan["detected"]["local_whisper_cli"]["path"],str(audio),"--model",model,"--output_format","json","--output_dir",td]
            if language!="auto": cmd += ["--language",language]
            cp=subprocess.run(cmd,capture_output=True,text=True,timeout=1800)
            if cp.returncode!=0: raise RuntimeError(cp.stderr[-2000:])
            files=list(Path(td).glob("*.json"))
            if not files: raise RuntimeError("Whisper produced no JSON transcript")
            data=json.loads(files[0].read_text(encoding="utf-8"))
            return {**plan,"executed":True,"text":str(data.get("text") or "").strip(),"backend":"whisper_local_cli"}

    if selected=="whisper_local_python":
        import whisper
        model_name=os.environ.get("AURA_WHISPER_MODEL","base")
        model=whisper.load_model(model_name)
        kwargs={} if language=="auto" else {"language":language}
        data=model.transcribe(str(audio),**kwargs)
        return {**plan,"executed":True,"text":str(data.get("text") or "").strip(),"backend":"whisper_local_python"}

    if selected=="nvidia_nim_http":
        base=plan["detected"]["nvidia_nim"]["base_url"].rstrip("/")
        if not _is_loopback(base) and not allow_remote:
            raise PermissionError("remote NVIDIA NIM transcription requires explicit approval")
        body,boundary=_multipart_body(audio,language)
        req=urllib.request.Request(base+"/v1/audio/transcriptions",data=body,method="POST",headers={"Content-Type":"multipart/form-data; boundary="+boundary})
        with urllib.request.urlopen(req,timeout=600) as r:
            data=json.loads(r.read().decode("utf-8"))
        text=data.get("text") or data.get("transcript") or ""
        return {**plan,"executed":True,"text":str(text).strip(),"backend":"nvidia_nim_http"}

    raise RuntimeError("unsupported backend "+str(selected))
