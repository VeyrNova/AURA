from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "media"
PLAYLIST = DATA / "premium_playlist_v180.json"
LIBRARY_STATE = DATA / "premium_library_state_v180.json"
COLLECTIONS = DATA / "premium_collections_v180.json"
RESUME_STATE = DATA / "premium_resume_state_v180.json"
PIDFILE = DATA / "music_premium_bridge_v180.pid"
PORT = 18180

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv"}
MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS

LOCK = threading.RLock()
STATE = {
    "process": None,
    "rc_port": None,
    "current_id": "",
    "current_path": "",
    "current_title": "",
    "playing": False,
    "paused": False,
    "volume_percent": 80,
    "last_position_seconds": 0.0,
    "last_duration_seconds": 0.0,
    "last_position_percent": 0.0,
    "last_status_ok": False,
    "manual_stop": False,
}
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

# AURA_M180_UI4_R4_R3_LIFECYCLE_WATCHDOG
AURA_UI_LIFECYCLE = {"last_heartbeat": time.time()}
AURA_UI_HEARTBEAT_TIMEOUT_SECONDS = 4.0


def now_iso():
    import datetime
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def json_write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# AURA_M180_UI5_R3_LIBRARY_STATE
def load_library_state():
    default = {
        "schema": "aura.music-premium-library-state.v180",
        "updated_at": now_iso(),
        "favorites": [],
        "history": [],
        "last_selected_id": "",
        "last_played_id": "",
    }
    with LOCK:
        if not LIBRARY_STATE.exists():
            return default
        try:
            data = json.loads(LIBRARY_STATE.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                return default
            favorites = data.get("favorites") if isinstance(data.get("favorites"), list) else []
            history = data.get("history") if isinstance(data.get("history"), list) else []
            data["schema"] = "aura.music-premium-library-state.v180"
            data["favorites"] = [str(x) for x in favorites if str(x)]
            data["history"] = history[:60]
            data["last_selected_id"] = str(data.get("last_selected_id") or "")
            data["last_played_id"] = str(data.get("last_played_id") or "")
            return {**default, **data}
        except Exception:
            return default


def save_library_state(data):
    payload = {
        "schema": "aura.music-premium-library-state.v180",
        "updated_at": now_iso(),
        "favorites": [str(x) for x in (data.get("favorites") or []) if str(x)],
        "history": list(data.get("history") or [])[:60],
        "last_selected_id": str(data.get("last_selected_id") or ""),
        "last_played_id": str(data.get("last_played_id") or ""),
    }
    json_write(LIBRARY_STATE, payload)
    return payload


def set_library_selected(item_id):
    data = load_library_state()
    data["last_selected_id"] = str(item_id or "")
    return save_library_state(data)


def toggle_library_favorite(item_id, enabled=None):
    item_id = str(item_id or "")
    data = load_library_state()
    current = [str(x) for x in data.get("favorites") or []]
    have = item_id in current
    target = (not have) if enabled is None else bool(enabled)
    if target and item_id and not have:
        current.append(item_id)
    elif not target and have:
        current = [x for x in current if x != item_id]
    data["favorites"] = current
    return save_library_state(data)


def record_library_play(item):
    data = load_library_state()
    item_id = str(item.get("id") or "")
    data["last_selected_id"] = item_id
    data["last_played_id"] = item_id
    entry = {
        "id": item_id,
        "title": str(item.get("title") or "Media"),
        "artist": str(item.get("artist") or ""),
        "album": str(item.get("album") or ""),
        "played_at": now_iso(),
    }
    history = list(data.get("history") or [])
    history.insert(0, entry)
    data["history"] = history[:60]
    return save_library_state(data)

# AURA_M180_UI5_R4_COLLECTIONS_ENGINE
def load_collections():
    default = {
        "schema": "aura.music-premium-collections.v180",
        "updated_at": now_iso(),
        "items": [],
    }
    with LOCK:
        if not COLLECTIONS.exists():
            return default
        try:
            data = json.loads(COLLECTIONS.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                return default
            items = data.get("items") if isinstance(data.get("items"), list) else []
            clean = []
            for row in items[:100]:
                if not isinstance(row, dict):
                    continue
                cid = str(row.get("id") or "")
                name = str(row.get("name") or "").strip()
                paths = [str(x) for x in (row.get("paths") or []) if str(x)]
                if cid and name:
                    clean.append({
                        "id": cid,
                        "name": name[:80],
                        "paths": paths[:5000],
                        "created_at": str(row.get("created_at") or ""),
                        "updated_at": str(row.get("updated_at") or ""),
                    })
            return {**default, "items": clean}
        except Exception:
            return default


def save_collections(items):
    payload = {
        "schema": "aura.music-premium-collections.v180",
        "updated_at": now_iso(),
        "items": list(items or [])[:100],
    }
    json_write(COLLECTIONS, payload)
    return payload


def collection_find(collection_id):
    cid = str(collection_id or "")
    data = load_collections()
    for row in data.get("items") or []:
        if str(row.get("id") or "") == cid:
            return row
    raise ValueError("collection_introuvable")


def collection_save_current(name):
    name = str(name or "").strip()[:80]
    if not name:
        raise ValueError("nom_collection_vide")
    pl = load_playlist()
    paths = [str(x.get("path") or "") for x in (pl.get("items") or []) if str(x.get("path") or "")]
    if not paths:
        raise ValueError("playlist_vide")
    data = load_collections()
    rows = list(data.get("items") or [])
    now = now_iso()
    existing = None
    for row in rows:
        if str(row.get("name") or "").strip().casefold() == name.casefold():
            existing = row
            break
    if existing is not None:
        existing["name"] = name
        existing["paths"] = paths
        existing["updated_at"] = now
    else:
        cid = f"col_{int(time.time()*1000)}_{len(rows)+1}"
        rows.insert(0, {
            "id": cid,
            "name": name,
            "paths": paths,
            "created_at": now,
            "updated_at": now,
        })
    return save_collections(rows)


def collection_load(collection_id):
    row = collection_find(collection_id)
    items = []
    missing = 0
    for raw in row.get("paths") or []:
        try:
            p = Path(str(raw)).expanduser().resolve()
            if not p.is_file() or not is_media(p):
                missing += 1
                continue
            items.append(media_item(p))
        except Exception:
            missing += 1
    playlist = save_playlist(dedupe_items(items))
    return {
        "collection": row,
        "playlist": playlist,
        "missing": missing,
    }


def collection_rename(collection_id, name):
    cid = str(collection_id or "")
    name = str(name or "").strip()[:80]
    if not name:
        raise ValueError("nom_collection_vide")
    data = load_collections()
    found = False
    for row in data.get("items") or []:
        if str(row.get("id") or "") == cid:
            row["name"] = name
            row["updated_at"] = now_iso()
            found = True
            break
    if not found:
        raise ValueError("collection_introuvable")
    return save_collections(data.get("items") or [])


def collection_delete(collection_id):
    cid = str(collection_id or "")
    data = load_collections()
    rows = [r for r in (data.get("items") or []) if str(r.get("id") or "") != cid]
    return save_collections(rows)

# AURA_M180_UI5_R7_M3U8_ENGINE
import subprocess as _aura_m3u_subprocess
from urllib.parse import urlparse as _aura_urlparse, unquote as _aura_unquote

def _aura_ps_dialog(kind):
    if kind=="save":
        cmd=(
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d=New-Object System.Windows.Forms.SaveFileDialog;"
            "$d.Title='AURA - Exporter la playlist';"
            "$d.Filter='Playlist M3U8 (*.m3u8)|*.m3u8|Playlist M3U (*.m3u)|*.m3u|Tous les fichiers (*.*)|*.*';"
            "$d.DefaultExt='m3u8';$d.AddExtension=$true;"
            "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){"
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Console]::Write($d.FileName)}"
        )
    else:
        cmd=(
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d=New-Object System.Windows.Forms.OpenFileDialog;"
            "$d.Title='AURA - Importer une playlist';"
            "$d.Filter='Playlists M3U/M3U8 (*.m3u;*.m3u8)|*.m3u;*.m3u8|Tous les fichiers (*.*)|*.*';"
            "$d.Multiselect=$false;"
            "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){"
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Console]::Write($d.FileName)}"
        )
    try:
        cp=_aura_m3u_subprocess.run(["powershell.exe","-NoProfile","-STA","-Command",cmd],
            stdout=_aura_m3u_subprocess.PIPE,stderr=_aura_m3u_subprocess.DEVNULL,timeout=120)
        return (cp.stdout or b"").decode("utf-8",errors="replace").strip()
    except Exception:return ""

def _aura_dialog_save_m3u8():
    try:
        import tkinter as _tk
        from tkinter import filedialog as _fd
        root=_tk.Tk(); root.withdraw()
        try:root.attributes("-topmost",True)
        except Exception:pass
        value=_fd.asksaveasfilename(title="AURA - Exporter la playlist",defaultextension=".m3u8",
            filetypes=[("Playlist M3U8","*.m3u8"),("Playlist M3U","*.m3u"),("Tous les fichiers","*.*")])
        root.destroy(); return str(value or "")
    except Exception:return _aura_ps_dialog("save")

def _aura_dialog_open_m3u():
    try:
        import tkinter as _tk
        from tkinter import filedialog as _fd
        root=_tk.Tk(); root.withdraw()
        try:root.attributes("-topmost",True)
        except Exception:pass
        value=_fd.askopenfilename(title="AURA - Importer une playlist",
            filetypes=[("Playlists M3U/M3U8","*.m3u *.m3u8"),("Tous les fichiers","*.*")])
        root.destroy(); return str(value or "")
    except Exception:return _aura_ps_dialog("open")

def aura_export_m3u8():
    items=list(load_playlist().get("items") or [])
    if not items:raise ValueError("playlist_vide")
    dest=_aura_dialog_save_m3u8()
    if not dest:return {"cancelled":True,"count":0,"path":""}
    p=Path(dest).expanduser()
    if p.suffix.lower() not in {".m3u",".m3u8"}:p=p.with_suffix(".m3u8")
    p.parent.mkdir(parents=True,exist_ok=True)
    lines=["#EXTM3U"];count=0
    for item in items:
        raw=str(item.get("path") or "")
        if not raw:continue
        title=str(item.get("title") or Path(raw).stem).replace("\r"," ").replace("\n"," ").strip()
        artist=str(item.get("artist") or "").replace("\r"," ").replace("\n"," ").strip()
        label=f"{artist} - {title}" if artist else title
        lines.extend([f"#EXTINF:-1,{label}",raw]);count+=1
    p.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"cancelled":False,"count":count,"path":str(p)}

def _aura_m3u_line_to_path(raw,base):
    value=str(raw or "").strip().strip('"')
    if not value:return None
    if value.lower().startswith("file://"):
        try:
            u=_aura_urlparse(value); decoded=_aura_unquote(u.path or "")
            if u.netloc:decoded="//"+u.netloc+decoded
            if len(decoded)>=3 and decoded[0]=="/" and decoded[2]==":":decoded=decoded[1:]
            value=decoded
        except Exception:return None
    p=Path(value).expanduser()
    if not p.is_absolute():p=base/p
    try:return p.resolve()
    except Exception:return p

def aura_import_m3u8():
    source=_aura_dialog_open_m3u()
    if not source:return {"cancelled":True,"playlist":load_playlist(),"missing":0,"imported":0,"path":""}
    src=Path(source).expanduser().resolve()
    if not src.is_file():raise ValueError("playlist_source_introuvable")
    raw=src.read_bytes();text=None
    for enc in ("utf-8-sig","utf-8","cp1252","latin1"):
        try:text=raw.decode(enc);break
        except Exception:pass
    if text is None:raise ValueError("playlist_encoding_invalide")
    items=[];missing=0;seen=set()
    for line in text.splitlines():
        s=line.strip()
        if not s or s.startswith("#"):continue
        p=_aura_m3u_line_to_path(s,src.parent)
        if p is None or not p.is_file() or not is_media(p):
            missing+=1;continue
        key=str(p).casefold()
        if key in seen:continue
        seen.add(key)
        try:items.append(media_item(p))
        except Exception:missing+=1
    if not items:raise ValueError("aucun_media_valide_dans_playlist")
    playlist=save_playlist(items)
    return {"cancelled":False,"playlist":playlist,"missing":missing,"imported":len(items),"path":str(src)}

# AURA_M180_UI5_R8_RESUME_ENGINE
def load_resume_state():
    default={
        "schema":"aura.music-premium-resume.v180",
        "updated_at":now_iso(),
        "item_id":"",
        "position_seconds":0.0,
        "duration_seconds":0.0,
        "title":"",
        "artist":"",
    }
    with LOCK:
        if not RESUME_STATE.exists():return default
        try:
            data=json.loads(RESUME_STATE.read_text(encoding="utf-8-sig"))
            if not isinstance(data,dict):return default
            return {
                **default,
                "item_id":str(data.get("item_id") or ""),
                "position_seconds":float(data.get("position_seconds") or 0.0),
                "duration_seconds":float(data.get("duration_seconds") or 0.0),
                "title":str(data.get("title") or ""),
                "artist":str(data.get("artist") or ""),
                "updated_at":str(data.get("updated_at") or now_iso()),
            }
        except Exception:return default

def save_resume_state(item_id,position,duration):
    item_id=str(item_id or "")
    try:position=max(0.0,float(position or 0.0))
    except Exception:position=0.0
    try:duration=max(0.0,float(duration or 0.0))
    except Exception:duration=0.0
    item=None
    try:item=playlist_find(item_id)
    except Exception:item=None
    payload={
        "schema":"aura.music-premium-resume.v180",
        "updated_at":now_iso(),
        "item_id":item_id,
        "position_seconds":position,
        "duration_seconds":duration,
        "title":str((item or {}).get("title") or ""),
        "artist":str((item or {}).get("artist") or ""),
    }
    json_write(RESUME_STATE,payload)
    return payload

def clear_resume_state(item_id=""):
    current=load_resume_state()
    wanted=str(item_id or "")
    if wanted and str(current.get("item_id") or "") not in {"",wanted}:
        return current
    payload={
        "schema":"aura.music-premium-resume.v180",
        "updated_at":now_iso(),
        "item_id":"",
        "position_seconds":0.0,
        "duration_seconds":0.0,
        "title":"",
        "artist":"",
    }
    json_write(RESUME_STATE,payload)
    return payload

# AURA_M180_UI6_R1_REAL_AUDIO_ANALYSIS_ENGINE
import array as _aura_analysis_array
import hashlib as _aura_analysis_hashlib
import math as _aura_analysis_math
import tempfile as _aura_analysis_tempfile

AURA_ANALYSIS_VERSION = 3
AURA_ANALYSIS_RATE = 12000
AURA_ANALYSIS_STEP = 1.0 / 60.0
AURA_ANALYSIS_CACHE = DATA / "premium_audio_analysis_v180"
AURA_ANALYSIS_CACHE.mkdir(parents=True, exist_ok=True)

def _aura_analysis_vlc():
    try:
        return find_vlc()
    except Exception:
        return ""

def _aura_analysis_ffmpeg():
    value=shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
    return str(value or "")

def _aura_analysis_cache_path(path):
    p=Path(path)
    stamp=f"{str(p.resolve()).casefold()}|{int(p.stat().st_mtime)}|{int(p.stat().st_size)}|v{AURA_ANALYSIS_VERSION}"
    key=_aura_analysis_hashlib.sha1(stamp.encode("utf-8",errors="replace")).hexdigest()
    return AURA_ANALYSIS_CACHE / f"{key}.json"

def _aura_analysis_pcm_from_wav(path):
    try:
        import wave as _aura_wave
        with _aura_wave.open(str(path),"rb") as w:
            channels=int(w.getnchannels() or 1)
            width=int(w.getsampwidth() or 0)
            rate=int(w.getframerate() or 0)
            raw=w.readframes(w.getnframes())
        if width!=2 or not raw:
            return b""
        if channels==1:
            return raw
        src=_aura_analysis_array.array("h")
        src.frombytes(raw[:len(raw)-(len(raw)%2)])
        if os.sys.byteorder!="little":
            src.byteswap()
        mono=_aura_analysis_array.array("h")
        for n in range(0,len(src)-channels+1,channels):
            total=0
            for c in range(channels):
                total+=int(src[n+c])
            mono.append(int(total/channels))
        if os.sys.byteorder!="little":
            mono.byteswap()
        return mono.tobytes()
    except Exception:
        return b""

def _aura_analysis_decode_with_python(path):
    # Optional local decoders only; never installs anything.
    try:
        import soundfile as _aura_sf
        data,rate=_aura_sf.read(str(path),dtype="float32",always_2d=True)
        if data is not None and len(data):
            import audioop as _aura_audioop
            mono=data.mean(axis=1)
            pcm=_aura_analysis_array.array("h",(max(-32768,min(32767,int(float(x)*32767.0))) for x in mono))
            if os.sys.byteorder!="little":
                pcm.byteswap()
            raw=pcm.tobytes()
            if int(rate)!=AURA_ANALYSIS_RATE and raw:
                raw,_=_aura_audioop.ratecv(raw,2,1,int(rate),AURA_ANALYSIS_RATE,None)
            if len(raw)>4096:
                return raw,"soundfile"
    except Exception:
        pass
    try:
        import av as _aura_av
        import audioop as _aura_audioop
        container=_aura_av.open(str(path))
        chunks=[]
        source_rate=None
        for frame in container.decode(audio=0):
            arr=frame.to_ndarray()
            source_rate=int(getattr(frame,"sample_rate",0) or 0) or source_rate
            if getattr(arr,"ndim",1)>1:
                try:arr=arr.mean(axis=0)
                except Exception:arr=arr.reshape(-1)
            vals=_aura_analysis_array.array("h")
            for x in arr.reshape(-1):
                try:
                    xf=float(x)
                    if abs(xf)<=1.5:xf*=32767.0
                    vals.append(max(-32768,min(32767,int(xf))))
                except Exception:
                    vals.append(0)
            if os.sys.byteorder!="little":vals.byteswap()
            chunks.append(vals.tobytes())
        raw=b"".join(chunks)
        if source_rate and source_rate!=AURA_ANALYSIS_RATE and raw:
            raw,_=_aura_audioop.ratecv(raw,2,1,source_rate,AURA_ANALYSIS_RATE,None)
        if len(raw)>4096:
            return raw,"pyav"
    except Exception:
        pass
    return b"",""

def _aura_analysis_vlc_wav(path,vlc):
    src=Path(path).resolve()
    tmp=Path(_aura_analysis_tempfile.gettempdir())/f"aura_music_analysis_{os.getpid()}_{int(time.time()*1000)}.wav"
    diagnostics=[]
    variants=[
        "#transcode{vcodec=none,acodec=s16l,channels=1,samplerate="+str(AURA_ANALYSIS_RATE)+"}:std{access=file,mux=wav,dst="+tmp.as_posix()+"}",
        "#transcode{vcodec=none,acodec=s16l,channels=1,samplerate="+str(AURA_ANALYSIS_RATE)+"}:standard{access=file,mux=wav,dst="+tmp.as_posix()+"}",
    ]
    try:
        for idx,sout in enumerate(variants,1):
            try:
                tmp.unlink()
            except Exception:
                pass
            cmd=[
                vlc,
                "--intf=dummy",
                "--dummy-quiet",
                "--no-video",
                "--no-video-title-show",
                "--sout="+sout,
                "--sout-keep",
                str(src),
                "vlc://quit",
            ]
            try:
                cp=subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0x08000000),
                )
                err=((cp.stderr or b"")+(cp.stdout or b"")).decode("utf-8",errors="replace").strip()
                diagnostics.append(f"v{idx}:rc={cp.returncode}:{err[-300:]}")
                if tmp.exists() and tmp.stat().st_size>4096:
                    raw=_aura_analysis_pcm_from_wav(tmp)
                    if len(raw)>4096:
                        return raw,"vlc_wav"," | ".join(diagnostics)
            except subprocess.TimeoutExpired:
                diagnostics.append(f"v{idx}:timeout")
            except Exception as exc:
                diagnostics.append(f"v{idx}:{type(exc).__name__}:{exc}")
        return b"","vlc_wav_failed"," | ".join(diagnostics)
    finally:
        try:tmp.unlink()
        except Exception:pass

def _aura_analysis_decode(path):
    src=Path(path).resolve()

    raw,decoder=_aura_analysis_decode_with_python(src)
    if raw:
        return raw,decoder,""

    ffmpeg=_aura_analysis_ffmpeg()
    if ffmpeg:
        tmp=Path(_aura_analysis_tempfile.gettempdir())/f"aura_music_analysis_{os.getpid()}_{int(time.time()*1000)}.raw"
        try:
            cmd=[ffmpeg,"-hide_banner","-loglevel","error","-y","-i",str(src),
                 "-vn","-ac","1","-ar",str(AURA_ANALYSIS_RATE),"-f","s16le",str(tmp)]
            cp=subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0x08000000),
            )
            if cp.returncode==0 and tmp.exists() and tmp.stat().st_size>4096:
                return tmp.read_bytes(),"ffmpeg",""
        except Exception:
            pass
        finally:
            try:tmp.unlink()
            except Exception:pass

    vlc=_aura_analysis_vlc()
    if not vlc:
        return b"","decoder_unavailable","VLC not found by existing find_vlc()"

    return _aura_analysis_vlc_wav(src,vlc)

def _aura_analysis_percentile(values,p=0.95):
    vals=sorted(float(x) for x in values if float(x)>=0)
    if not vals:return 1.0
    idx=max(0,min(len(vals)-1,int(round((len(vals)-1)*p))))
    return max(1e-9,vals[idx])

def _aura_analysis_frames(raw):
    # UI6-R1-R5: 60 Hz cadence + 38 real logarithmic FFT bands.
    # Frame layout: [rms, low, high, transient, band0 ... band37]
    try:
        import numpy as _np
    except Exception:
        return []

    if len(raw)<4:
        return []

    pcm=_np.frombuffer(raw[:len(raw)-(len(raw)%2)],dtype="<i2").astype(_np.float32)
    if pcm.size<512:
        return []
    pcm/=32768.0

    rate=int(AURA_ANALYSIS_RATE)
    hop=max(1,int(round(rate*float(AURA_ANALYSIS_STEP))))
    win_size=512

    try:
        view=_np.lib.stride_tricks.sliding_window_view(pcm,win_size)[::hop]
    except Exception:
        count=max(1,1+(pcm.size-win_size)//hop)
        view=_np.stack([pcm[i*hop:i*hop+win_size] for i in range(count)],axis=0)

    if view.size==0:
        return []

    window=_np.hanning(win_size).astype(_np.float32)
    framed=view*window[None,:]
    norm=max(1.0,float(window.sum())*.5)

    spectrum=_np.abs(_np.fft.rfft(framed,axis=1)).astype(_np.float32)/norm
    freqs=_np.fft.rfftfreq(win_size,d=1.0/rate)

    low_hz=45.0
    high_hz=min(5500.0,rate*0.48)
    edges=_np.geomspace(low_hz,high_hz,39)
    centers=_np.sqrt(edges[:-1]*edges[1:])

    bands=_np.zeros((spectrum.shape[0],38),dtype=_np.float32)
    for idx in range(38):
        mask=(freqs>=edges[idx])&(freqs<edges[idx+1])
        if not bool(mask.any()):
            nearest=int(_np.argmin(_np.abs(freqs-centers[idx])))
            bands[:,idx]=spectrum[:,nearest]
        else:
            chunk=spectrum[:,mask]
            bands[:,idx]=_np.sqrt(_np.mean(chunk*chunk,axis=1))

    compressed=_np.log1p(bands*90.0)
    global_p=float(_np.percentile(compressed,98.0)) if compressed.size else 1.0
    band_p=_np.percentile(compressed,97.0,axis=0)
    denom=.55*global_p+.45*band_p
    denom=_np.maximum(denom,1e-6)
    spec_norm=_np.clip(compressed/denom[None,:],0.0,1.0)
    spec_norm=_np.power(spec_norm,.72)

    if spec_norm.shape[1]>=3:
        sm=spec_norm.copy()
        sm[:,1:-1]=.18*spec_norm[:,:-2]+.64*spec_norm[:,1:-1]+.18*spec_norm[:,2:]
        sm[:,0]=.78*spec_norm[:,0]+.22*spec_norm[:,1]
        sm[:,-1]=.78*spec_norm[:,-1]+.22*spec_norm[:,-2]
        spec_norm=sm

    rms=_np.sqrt(_np.mean(framed*framed,axis=1))
    low_mask=centers<250.0
    high_mask=centers>2400.0
    low=_np.mean(bands[:,low_mask],axis=1) if bool(low_mask.any()) else rms
    high=_np.mean(bands[:,high_mask],axis=1) if bool(high_mask.any()) else rms

    flux=_np.zeros((bands.shape[0],),dtype=_np.float32)
    if bands.shape[0]>1:
        delta=_np.maximum(bands[1:]-bands[:-1],0.0)
        flux[1:]=_np.mean(delta,axis=1)

    def _scale_metric(v):
        p=float(_np.percentile(v,95.0)) if v.size else 1.0
        if p<=1e-9:p=1.0
        return _np.power(_np.clip(v/p,0.0,1.0),.72)

    summary=_np.stack([
        _scale_metric(rms),
        _scale_metric(low),
        _scale_metric(high),
        _scale_metric(flux),
    ],axis=1)

    merged=_np.concatenate([summary,spec_norm],axis=1)
    packed=_np.rint(_np.clip(merged,0.0,1.0)*255.0).astype(_np.uint8)
    return packed.tolist()


def aura_analyze_item(item_id):
    item=playlist_find(item_id)
    src=Path(str(item.get("path") or "")).resolve()
    if not src.is_file():
        return {"available":False,"reason":"source_missing","id":str(item_id or "")}
    cache=_aura_analysis_cache_path(src)
    if cache.exists():
        try:
            data=json.loads(cache.read_text(encoding="utf-8-sig"))
            if data.get("version")==AURA_ANALYSIS_VERSION and isinstance(data.get("frames"),list) and data.get("frames"):
                return {**data,"cached":True}
        except Exception:pass

    raw,decoder,diagnostic=_aura_analysis_decode(src)
    if not raw:
        return {"available":False,"reason":decoder,"id":str(item_id or ""),"decoder":decoder,"diagnostic":diagnostic}
    frames=_aura_analysis_frames(raw)
    if not frames:
        return {"available":False,"reason":"no_frames","id":str(item_id or ""),"decoder":decoder}

    payload={
        "available":True,
        "version":AURA_ANALYSIS_VERSION,
        "id":str(item.get("id") or item_id or ""),
        "step_seconds":AURA_ANALYSIS_STEP,
        "sample_rate":AURA_ANALYSIS_RATE,
        "channels":["rms","low","high","transient","spectrum_38"],
        "spectrum_bands":38,
        "frames":frames,
        "decoder":decoder,
        "decoder_diagnostic":diagnostic,
        "cached":False,
        "generated_at":now_iso(),
    }
    try:cache.write_text(json.dumps(payload,separators=(",",":")),encoding="utf-8")
    except Exception:pass
    return payload

# AURA_M180_UI6_R1_R5_R8_WINDOWED_FFT_TRANSPORT
_AURA_R8_ANALYSIS_MEM={}

def aura_analysis_window(item_id,position=0.0,before=1.5,after=8.5):
    item_id=str(item_id or "")
    if not item_id:
        return {"available":False,"reason":"missing_id","id":""}

    cached=_AURA_R8_ANALYSIS_MEM.get(item_id)
    if not isinstance(cached,dict) or not cached.get("available") or int(cached.get("version") or 0)!=int(AURA_ANALYSIS_VERSION):
        cached=aura_analyze_item(item_id)
        if cached.get("available"):
            _AURA_R8_ANALYSIS_MEM[item_id]=cached

    if not cached.get("available"):
        return cached

    frames=list(cached.get("frames") or [])
    step=float(cached.get("step_seconds") or 0.0)
    if not frames or step<=0:
        return {"available":False,"reason":"invalid_analysis","id":item_id}

    try:position=max(0.0,float(position or 0.0))
    except Exception:position=0.0
    try:before=max(0.5,min(3.0,float(before or 1.5)))
    except Exception:before=1.5
    try:after=max(4.0,min(12.0,float(after or 8.5)))
    except Exception:after=8.5

    start_seconds=max(0.0,position-before)
    end_seconds=position+after
    start_index=max(0,min(len(frames)-1,int(start_seconds/step)))
    end_index=max(start_index+1,min(len(frames),int(end_seconds/step)+2))
    sliced=frames[start_index:end_index]

    return {
        "available":True,
        "version":cached.get("version"),
        "id":str(cached.get("id") or item_id),
        "step_seconds":step,
        "sample_rate":cached.get("sample_rate"),
        "channels":cached.get("channels"),
        "spectrum_bands":cached.get("spectrum_bands"),
        "frames":sliced,
        "window_start_seconds":start_index*step,
        "window_end_seconds":end_index*step,
        "window_start_index":start_index,
        "window_end_index":end_index,
        "total_frames":len(frames),
        "decoder":cached.get("decoder"),
        "transport":"windowed_fft_v1",
    }

# AURA_M180_UI6_R2_WINDOWS_MEDIA_KEYS
AURA_MEDIA_HOTKEYS={
    "started":False,
    "thread_alive":False,
    "registered":{},
    "last_action":"",
    "last_error":"",
}

def _aura_media_items():
    try:return list((load_playlist() or {}).get("items") or [])
    except Exception:return []

def _aura_media_current_id():
    try:
        s=status_payload() or {}
        cid=str(s.get("current_id") or "")
        if cid:return cid
    except Exception:pass
    try:
        lib=load_library_state() or {}
        cid=str(lib.get("last_played_id") or "")
        if cid:return cid
    except Exception:pass
    return ""

def _aura_media_launch(item):
    if not isinstance(item,dict):raise RuntimeError("media item missing")
    result=launch_item(item)
    try:record_library_play(item)
    except Exception:pass
    return result

AURA_MEDIA_COMMAND_DEBOUNCE={"action":"","at":0.0}


# AURA_M180_UI6_R6_PLAY_ID_ENDPOINT
def aura_media_play_id(item_id):
    wanted=str(item_id or "").strip()
    if not wanted:
        return {"ok":False,"reason":"missing_id"}

    items=_aura_media_items()
    item=next((x for x in items if str(x.get("id") or "")==wanted),None)
    if item is None:
        return {"ok":False,"reason":"item_not_found","id":wanted}

    try:
        STATE["manual_stop"]=False
    except Exception:
        pass

    _aura_media_launch(item)
    return {
        "ok":True,
        "action":"play_id",
        "current_id":wanted,
        "title":str(item.get("title") or ""),
    }

def aura_media_command(action):
    action=str(action or "").strip().lower()
    now=time.monotonic()
    if action and action==AURA_MEDIA_COMMAND_DEBOUNCE.get("action") and now-float(AURA_MEDIA_COMMAND_DEBOUNCE.get("at") or 0)<0.22:
        return {"ok":True,"action":action,"debounced":True}
    AURA_MEDIA_COMMAND_DEBOUNCE["action"]=action
    AURA_MEDIA_COMMAND_DEBOUNCE["at"]=now
    if action in {"play_pause","toggle","pause"}:
        s=status_payload() or {}
        cid=str(s.get("current_id") or "")
        if cid or float(s.get("duration_seconds") or 0)>0:
            try:
                STATE["manual_stop"]=False
            except Exception:pass
            reply=rc("pause")
            return {"ok":True,"action":"play_pause","rc":str(reply or "")}

        items=_aura_media_items()
        wanted=_aura_media_current_id()
        item=next((x for x in items if str(x.get("id") or "")==wanted),None)
        if item is None and items:item=items[0]
        if item is None:return {"ok":False,"action":"play_pause","reason":"playlist_empty"}
        _aura_media_launch(item)
        return {"ok":True,"action":"play_pause","current_id":str(item.get("id") or "")}

    if action=="stop":
        try:STATE["manual_stop"]=True
        except Exception:pass
        reply=rc("stop")
        return {"ok":True,"action":"stop","rc":str(reply or "")}

    if action in {"next","previous","prev"}:
        items=_aura_media_items()
        if not items:return {"ok":False,"action":action,"reason":"playlist_empty"}

        current=_aura_media_current_id()
        idx=next((i for i,x in enumerate(items) if str(x.get("id") or "")==current),-1)

        if action=="next":
            target_idx=0 if idx<0 else (idx+1)%len(items)
            normalized="next"
        else:
            target_idx=len(items)-1 if idx<0 else (idx-1)%len(items)
            normalized="previous"

        item=items[target_idx]
        try:STATE["manual_stop"]=False
        except Exception:pass
        _aura_media_launch(item)
        return {
            "ok":True,
            "action":normalized,
            "current_id":str(item.get("id") or ""),
            "title":str(item.get("title") or ""),
        }

    return {"ok":False,"action":action,"reason":"unsupported_action"}

def _aura_media_hotkey_worker():
    import ctypes
    from ctypes import wintypes
    time.sleep(1.0)
    user32=ctypes.windll.user32

    WM_HOTKEY=0x0312
    MOD_NOREPEAT=0x4000
    mapping={
        0xA180:(0xB0,"next"),
        0xA181:(0xB1,"previous"),
        0xA182:(0xB2,"stop"),
        0xA183:(0xB3,"play_pause"),
    }

    registered={}
    try:
        for hotkey_id,(vk,action) in mapping.items():
            ok=bool(user32.RegisterHotKey(None,hotkey_id,MOD_NOREPEAT,vk))
            registered[action]=ok
        AURA_MEDIA_HOTKEYS["registered"]=registered
        AURA_MEDIA_HOTKEYS["thread_alive"]=True

        msg=wintypes.MSG()
        while True:
            value=user32.GetMessageW(ctypes.byref(msg),None,0,0)
            if value<=0:break
            if msg.message==WM_HOTKEY:
                item=mapping.get(int(msg.wParam))
                if item:
                    action=item[1]
                    AURA_MEDIA_HOTKEYS["last_action"]=action
                    try:
                        threading.Thread(target=aura_media_command,args=(action,),daemon=True).start()
                    except Exception as exc:
                        AURA_MEDIA_HOTKEYS["last_error"]=str(exc)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except Exception as exc:
        AURA_MEDIA_HOTKEYS["last_error"]=f"{type(exc).__name__}: {exc}"
    finally:
        for hotkey_id in mapping:
            try:user32.UnregisterHotKey(None,hotkey_id)
            except Exception:pass
        AURA_MEDIA_HOTKEYS["thread_alive"]=False

def aura_start_media_hotkeys():
    if AURA_MEDIA_HOTKEYS.get("started"):return
    AURA_MEDIA_HOTKEYS["started"]=True
    try:
        threading.Thread(target=_aura_media_hotkey_worker,name="aura-media-hotkeys",daemon=True).start()
    except Exception as exc:
        AURA_MEDIA_HOTKEYS["last_error"]=f"{type(exc).__name__}: {exc}"

aura_start_media_hotkeys()

# AURA_M180_UI6_R3_NATIVE_SMTC_HELPER
# AURA_M180_UI6_R4_WINDOWS_TIMELINE_SEEK_SYNC
AURA_SMTC_HELPER_EXE = ROOT / "runtime" / "aura_smtc_native_helper_v180.exe"
AURA_SMTC_STATUS = ROOT / "data" / "media" / "aura_smtc_status_v180.json"
AURA_SMTC_PROC = None

def aura_read_smtc_status():
    try:
        if AURA_SMTC_STATUS.exists():
            return json.loads(AURA_SMTC_STATUS.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return {"ready":False,"last_error":"status_unavailable"}

def aura_smtc_helper_alive():
    global AURA_SMTC_PROC
    try:
        if AURA_SMTC_PROC is not None and AURA_SMTC_PROC.poll() is None:return True
    except Exception:pass
    st=aura_read_smtc_status()
    try:pid=int(st.get("pid") or 0)
    except Exception:pid=0
    if pid<=0:return False
    try:
        cp=subprocess.run(["tasklist","/FI",f"PID eq {pid}","/FO","CSV","/NH"],
                          stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=4)
        return str(pid) in (cp.stdout or b"").decode("utf-8",errors="replace")
    except Exception:return False

def aura_start_smtc_helper():
    global AURA_SMTC_PROC
    if not AURA_SMTC_HELPER_EXE.exists() or aura_smtc_helper_alive():return
    try:
        AURA_SMTC_PROC=subprocess.Popen(
            [str(AURA_SMTC_HELPER_EXE)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0x08000000))
    except Exception:
        AURA_SMTC_PROC=None

def aura_media_seek(position):
    try:
        seconds=float(position)
    except Exception:
        return {"ok":False,"reason":"invalid_position"}
    if seconds != seconds or seconds in (float("inf"),float("-inf")):
        return {"ok":False,"reason":"invalid_position"}
    seconds=max(0.0,seconds)
    try: STATE["manual_stop"]=False
    except Exception: pass
    reply=rc(f"seek {seconds:.3f}")
    return {"ok":True,"action":"seek","position_seconds":seconds,"rc":str(reply or "")}

def aura_smtc_watchdog():
    while True:
        try:aura_start_smtc_helper()
        except Exception:pass
        time.sleep(4.0)

threading.Thread(target=aura_smtc_watchdog,name="aura-smtc-watchdog",daemon=True).start()

def load_playlist():
    with LOCK:
        if not PLAYLIST.exists():
            return {"schema": "aura.music-premium-playlist.v180", "updated_at": now_iso(), "items": []}
        try:
            data = json.loads(PLAYLIST.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("bad playlist")
            if not isinstance(data.get("items"), list):
                data["items"] = []
            return data
        except Exception:
            return {"schema": "aura.music-premium-playlist.v180", "updated_at": now_iso(), "items": []}


def save_playlist(items):
    payload = {
        "schema": "aura.music-premium-playlist.v180",
        "updated_at": now_iso(),
        "count": len(items),
        "items": items,
    }
    json_write(PLAYLIST, payload)
    return payload


def clean_title(path: Path):
    stem = path.stem.strip()
    artist = ""
    title = stem
    if " - " in stem:
        left, right = stem.split(" - ", 1)
        if left and right:
            artist, title = left.strip(), right.strip()
    return title or stem, artist


def media_item(path: Path):
    path = path.expanduser().resolve()
    title, artist = clean_title(path)
    ext = path.suffix.lower()
    stat = path.stat()
    ident = "pl_" + uuid.uuid5(uuid.NAMESPACE_URL, str(path).casefold()).hex[:20]
    return {
        "id": ident,
        "path": str(path),
        "title": title,
        "artist": artist,
        "album": path.parent.name,
        "extension": ext,
        "media_type": "audio" if ext in AUDIO_EXTS else "video",
        "size_bytes": int(stat.st_size),
        "modified_at": int(stat.st_mtime),
    }


# AURA_M180_UI5_R2_METADATA_ENGINE
import base64 as _aura_meta_b64
import struct as _aura_meta_struct

AURA_METADATA_VERSION = 2
AURA_MAX_COVER_BYTES = 700000


def _aura_meta_text(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return _aura_meta_text(value[0]) if value else ""
    return str(value).strip()


def _aura_cover_uri(mime, raw):
    if not raw or len(raw) > AURA_MAX_COVER_BYTES:
        return ""
    mime = str(mime or "image/jpeg").strip().lower()
    if mime not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        mime = "image/jpeg"
    return "data:" + mime.replace("image/jpg","image/jpeg") + ";base64," + _aura_meta_b64.b64encode(raw).decode("ascii")


def _aura_id3_decode(payload):
    if not payload:
        return ""
    enc = payload[0]
    raw = payload[1:]
    try:
        if enc == 0:
            return raw.decode("latin1", errors="replace").strip("\x00 ").strip()
        if enc == 1:
            return raw.decode("utf-16", errors="replace").strip("\x00 ").strip()
        if enc == 2:
            return raw.decode("utf-16-be", errors="replace").strip("\x00 ").strip()
        return raw.decode("utf-8", errors="replace").strip("\x00 ").strip()
    except Exception:
        return ""


def _aura_synchsafe(raw):
    if len(raw) != 4:
        return 0
    return ((raw[0] & 0x7f) << 21) | ((raw[1] & 0x7f) << 14) | ((raw[2] & 0x7f) << 7) | (raw[3] & 0x7f)


def _aura_apic(payload):
    if not payload:
        return "", b""
    enc = payload[0]
    rest = payload[1:]
    z = rest.find(b"\x00")
    if z < 0:
        return "", b""
    mime = rest[:z].decode("latin1", errors="replace")
    rest = rest[z+1:]
    if not rest:
        return "", b""
    rest = rest[1:]
    if enc in (1,2):
        z = rest.find(b"\x00\x00")
        if z < 0:return "", b""
        image = rest[z+2:]
    else:
        z = rest.find(b"\x00")
        if z < 0:return "", b""
        image = rest[z+1:]
    return mime, image


def _aura_parse_id3(path):
    out={}
    try:
        with Path(path).open("rb") as f:
            head=f.read(10)
            if len(head)<10 or head[:3] != b"ID3":
                return out
            version=int(head[3])
            size=_aura_synchsafe(head[6:10])
            body=f.read(min(size, 16*1024*1024))
        pos=0
        if head[5] & 0x40 and len(body)>=4:
            if version == 4:
                pos=_aura_synchsafe(body[:4])
            else:
                pos=4+int.from_bytes(body[:4],"big",signed=False)
        keys={"TIT2":"title","TPE1":"artist","TALB":"album","TRCK":"track","TDRC":"year","TYER":"year"}
        while pos+10 <= len(body):
            fid=body[pos:pos+4].decode("latin1",errors="ignore")
            if not fid.strip("\x00") or not fid.replace("\x00","").isalnum():
                break
            raw_size=body[pos+4:pos+8]
            frame_size=_aura_synchsafe(raw_size) if version==4 else int.from_bytes(raw_size,"big",signed=False)
            if frame_size <= 0 or pos+10+frame_size > len(body):
                break
            payload=body[pos+10:pos+10+frame_size]
            if fid in keys:
                out[keys[fid]]=_aura_id3_decode(payload)
            elif fid=="APIC" and not out.get("cover_data_uri"):
                mime,image=_aura_apic(payload)
                uri=_aura_cover_uri(mime,image)
                if uri:out["cover_data_uri"]=uri
            pos += 10 + frame_size
    except Exception:
        pass
    return out


def _aura_parse_flac(path):
    out={}
    try:
        with Path(path).open("rb") as f:
            if f.read(4) != b"fLaC":
                return out
            last=False
            while not last:
                h=f.read(4)
                if len(h)<4:break
                last=bool(h[0]&0x80)
                typ=h[0]&0x7f
                n=int.from_bytes(h[1:4],"big")
                if n<0 or n>20*1024*1024:
                    f.seek(n,1);continue
                data=f.read(n)
                if typ==4 and len(data)>=8:
                    p=0
                    vendor_n=int.from_bytes(data[p:p+4],"little");p+=4+vendor_n
                    if p+4>len(data):continue
                    count=int.from_bytes(data[p:p+4],"little");p+=4
                    for _ in range(min(count,2048)):
                        if p+4>len(data):break
                        ln=int.from_bytes(data[p:p+4],"little");p+=4
                        raw=data[p:p+ln];p+=ln
                        try:s=raw.decode("utf-8",errors="replace")
                        except Exception:continue
                        if "=" not in s:continue
                        k,v=s.split("=",1);k=k.upper().strip();v=v.strip()
                        mp={"TITLE":"title","ARTIST":"artist","ALBUM":"album","TRACKNUMBER":"track","DATE":"year","YEAR":"year"}
                        if k in mp and not out.get(mp[k]):out[mp[k]]=v
                elif typ==6 and not out.get("cover_data_uri"):
                    p=0
                    if len(data)<32:continue
                    p+=4
                    ml=int.from_bytes(data[p:p+4],"big");p+=4
                    mime=data[p:p+ml].decode("utf-8",errors="replace");p+=ml
                    dl=int.from_bytes(data[p:p+4],"big");p+=4+dl
                    p+=16
                    if p+4>len(data):continue
                    il=int.from_bytes(data[p:p+4],"big");p+=4
                    image=data[p:p+il]
                    uri=_aura_cover_uri(mime,image)
                    if uri:out["cover_data_uri"]=uri
    except Exception:
        pass
    return out


def _aura_parse_mutagen(path):
    out={}
    try:
        from mutagen import File as _MutagenFile
    except Exception:
        return out
    try:
        easy=_MutagenFile(str(path),easy=True)
        if easy is not None:
            for src,dst in [("title","title"),("artist","artist"),("album","album"),("tracknumber","track"),("date","year")]:
                try:
                    v=easy.get(src)
                    if v:out[dst]=_aura_meta_text(v)
                except Exception:pass
        rich=_MutagenFile(str(path),easy=False)
        if rich is not None:
            tags=getattr(rich,"tags",None)
            if tags:
                try:
                    for frame in tags.values():
                        name=frame.__class__.__name__.upper()
                        if name=="APIC":
                            uri=_aura_cover_uri(getattr(frame,"mime","image/jpeg"),bytes(getattr(frame,"data",b"")))
                            if uri:out["cover_data_uri"]=uri;break
                except Exception:pass
                if not out.get("cover_data_uri"):
                    try:
                        cov=tags.get("covr")
                        if cov:
                            raw=bytes(cov[0])
                            mime="image/png" if raw[:8]==b"\x89PNG\r\n\x1a\n" else "image/jpeg"
                            uri=_aura_cover_uri(mime,raw)
                            if uri:out["cover_data_uri"]=uri
                    except Exception:pass
            if not out.get("cover_data_uri"):
                try:
                    pics=getattr(rich,"pictures",None) or []
                    if pics:
                        pic=pics[0]
                        uri=_aura_cover_uri(getattr(pic,"mime","image/jpeg"),bytes(getattr(pic,"data",b"")))
                        if uri:out["cover_data_uri"]=uri
                except Exception:pass
    except Exception:
        return {}
    if out:
        out["metadata_source"]="mutagen"
    return out


def aura_read_media_metadata(path):
    p=Path(path)
    meta=_aura_parse_mutagen(p)
    if not meta:
        if p.suffix.lower()==".mp3":
            meta=_aura_parse_id3(p)
            if meta:meta["metadata_source"]="id3v2"
        elif p.suffix.lower()==".flac":
            meta=_aura_parse_flac(p)
            if meta:meta["metadata_source"]="flac"
    return meta


_aura_ui5_r2_base_media_item = media_item
def media_item(path):
    item=_aura_ui5_r2_base_media_item(path)
    meta=aura_read_media_metadata(item["path"])
    for key in ("title","artist","album","track","year","cover_data_uri","metadata_source"):
        value=meta.get(key)
        if value not in (None,""):
            item[key]=value
    item["metadata_version"]=AURA_METADATA_VERSION
    item["metadata_mtime"]=item.get("modified_at")
    item["has_cover"]=bool(item.get("cover_data_uri"))
    return item


def aura_refresh_playlist_metadata(force=False):
    pl=load_playlist()
    changed=False
    refreshed=[]
    for old in pl.get("items",[]):
        try:
            p=Path(str(old.get("path") or "")).expanduser().resolve()
            if not p.is_file():
                refreshed.append(old);continue
            st=p.stat()
            stale=(
                force
                or int(old.get("metadata_version") or 0) != AURA_METADATA_VERSION
                or int(old.get("metadata_mtime") or 0) != int(st.st_mtime)
            )
            if stale:
                new=media_item(p)
                # Preserve stable playlist ID.
                if old.get("id"):new["id"]=old["id"]
                refreshed.append(new);changed=True
            else:
                refreshed.append(old)
        except Exception:
            refreshed.append(old)
    if changed:
        return save_playlist(refreshed)
    return pl

def dedupe_paths(paths):
    out, seen = [], set()
    for p in paths:
        try:
            rp = Path(p).expanduser().resolve()
        except Exception:
            continue
        key = str(rp).casefold()
        if key in seen:
            continue
        if not rp.exists() or not rp.is_file() or rp.suffix.lower() not in MEDIA_EXTS:
            continue
        seen.add(key)
        out.append(rp)
    return out


def run_picker(kind):
    if kind == "track":
        script = r'''
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = "AURA - Ajouter une ou plusieurs musiques"
$d.Filter = "Audio et video|*.mp3;*.wav;*.flac;*.m4a;*.aac;*.ogg;*.opus;*.wma;*.mp4;*.mkv;*.mov;*.avi;*.webm;*.m4v;*.wmv|Tous les fichiers|*.*"
$d.Multiselect = $true
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  ConvertTo-Json -InputObject @($d.FileNames) -Compress
}
'''
    elif kind == "playlist":
        script = r'''
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = "AURA - Importer une playlist"
$d.Filter = "Playlists|*.m3u;*.m3u8;*.pls|M3U|*.m3u;*.m3u8|PLS|*.pls"
$d.Multiselect = $false
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  [Console]::Write($d.FileName)
}
'''
    elif kind == "folder":
        script = r'''
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = "AURA - Choisir un dossier musique"
$d.ShowNewFolderButton = $false
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  [Console]::Write($d.SelectedPath)
}
'''
    else:
        raise ValueError("unknown picker kind")

    cp = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout or "picker failed").strip())
    return (cp.stdout or "").strip()


def parse_playlist_file(path: Path):
    ext = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    found = []
    if ext in {".m3u", ".m3u8"}:
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            p = Path(line.strip('"'))
            if not p.is_absolute():
                p = path.parent / p
            found.append(p)
    elif ext == ".pls":
        rows = []
        for line in text.splitlines():
            m = re.match(r"(?i)^\s*File(\d+)\s*=\s*(.+?)\s*$", line)
            if m:
                p = Path(m.group(2).strip().strip('"'))
                if not p.is_absolute():
                    p = path.parent / p
                rows.append((int(m.group(1)), p))
        rows.sort(key=lambda x: x[0])
        found = [p for _, p in rows]
    return dedupe_paths(found)


def folder_media(folder: Path, limit=10000):
    found = []
    for current, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d.casefold() not in {"$recycle.bin", "system volume information"} and not d.startswith(".")]
        for name in files:
            p = Path(current) / name
            if p.suffix.lower() in MEDIA_EXTS:
                found.append(p)
                if len(found) >= limit:
                    return dedupe_paths(found)
    found.sort(key=lambda p: str(p).casefold())
    return dedupe_paths(found)


def pick_and_update(kind):
    raw = run_picker(kind)
    if not raw:
        return {"cancelled": True, "playlist": load_playlist()}

    if kind == "track":
        try:
            values = json.loads(raw)
            if isinstance(values, str):
                values = [values]
        except Exception:
            values = [raw]
        paths = dedupe_paths(values)
        current = load_playlist()["items"]
        existing_paths = {str(x.get("path") or "").casefold() for x in current}
        for p in paths:
            if str(p).casefold() not in existing_paths:
                current.append(media_item(p))
        return {"cancelled": False, "mode": "append", "playlist": save_playlist(current)}

    if kind == "playlist":
        pl = Path(raw).expanduser().resolve()
        paths = parse_playlist_file(pl)
        return {"cancelled": False, "mode": "replace", "playlist_file": str(pl), "playlist": save_playlist([media_item(p) for p in paths])}

    folder = Path(raw).expanduser().resolve()
    paths = folder_media(folder)
    return {"cancelled": False, "mode": "replace", "folder": str(folder), "playlist": save_playlist([media_item(p) for p in paths])}


def shutil_which(name):
    import shutil
    return shutil.which(name)


def find_vlc():
    candidates = [
        shutil_which("vlc.exe"),
        shutil_which("vlc"),
        str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "VideoLAN" / "VLC" / "vlc.exe"),
        str(Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "VideoLAN" / "VLC" / "vlc.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(Path(c))
    raise RuntimeError("VLC introuvable")


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


# AURA_M180_UI4_R4_R6_FAST_VLC_RC
def _rc_read_until_prompt(sock, max_wait):
    deadline = time.monotonic() + max(0.05, float(max_wait))
    chunks = []
    while time.monotonic() < deadline:
        remaining = max(0.01, deadline - time.monotonic())
        sock.settimeout(min(0.08, remaining))
        try:
            data = sock.recv(4096)
        except socket.timeout:
            if chunks:
                break
            continue
        if not data:
            break
        chunks.append(data)
        blob = b"".join(chunks)
        stripped = blob.rstrip()
        if stripped.endswith(b">") or blob.endswith(b"> "):
            break
        if len(blob) > 32768:
            break
    return b"".join(chunks)


def rc(command, timeout=0.35, retries=3):
    with LOCK:
        port = STATE.get("rc_port")
    if not port:
        raise RuntimeError("session VLC absente")
    last = None
    for _ in range(retries):
        sock = None
        try:
            sock = socket.create_connection(("127.0.0.1", int(port)), timeout=min(0.35, timeout))
            _rc_read_until_prompt(sock, 0.20)
            sock.sendall((str(command).strip() + "\n").encode("utf-8"))
            raw = _rc_read_until_prompt(sock, timeout)
            if not raw:
                raise RuntimeError("VLC RC response vide")
            return raw.decode("utf-8", errors="replace")
        except Exception as exc:
            last = exc
            time.sleep(0.04)
        finally:
            try:
                if sock:
                    sock.close()
            except Exception:
                pass
    raise RuntimeError(f"VLC RC indisponible: {last}")

def last_number(text):
    values = []
    for line in str(text or "").replace("\r", "\n").split("\n"):
        clean = line.strip().lstrip(">").strip()
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*$", clean)
        if m:
            try:
                values.append(float(m.group(1)))
            except Exception:
                pass
    return values[-1] if values else None


def terminate_current():
    with LOCK:
        proc = STATE.get("process")
        port = STATE.get("rc_port")
    if port:
        try:
            rc("quit", timeout=0.3, retries=1)
        except Exception:
            pass
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    with LOCK:
        STATE.update({"process": None, "rc_port": None, "current_id": "", "current_path": "", "current_title": "", "playing": False, "paused": False})


def launch_item(item):
    with LOCK:
        AURA_UI_LIFECYCLE["last_heartbeat"] = time.time()
    path = Path(item["path"]).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    terminate_current()
    vlc = find_vlc()
    port = free_port()
    args = [
        vlc, "--intf=dummy", "--extraintf=rc", f"--rc-host=127.0.0.1:{port}",
        "--rc-quiet", "--dummy-quiet", "--no-video-title-show", "--play-and-exit", str(path),
    ]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with LOCK:
        STATE.update({
            "process": proc, "rc_port": port, "current_id": item["id"],
            "current_path": str(path), "current_title": item.get("title") or path.stem,
            "playing": True, "paused": False,
            "last_position_seconds": 0.0,
            "last_duration_seconds": 0.0,
            "last_position_percent": 0.0,
            "last_status_ok": True,
            "manual_stop": False,
        })

    deadline = time.time() + 5.0
    last = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"VLC s'est fermé immédiatement (code {proc.returncode})")
        try:
            rc("get_length", timeout=0.3, retries=1)
            pct = int(STATE.get("volume_percent") or 80)
            rc(f"volume {int(round(256 * pct / 100.0))}", timeout=0.3, retries=1)
            return status_payload()
        except Exception as exc:
            last = exc
            time.sleep(0.15)
    terminate_current()
    raise RuntimeError(f"VLC RC ne répond pas après lancement: {last}")


def status_payload():
    with LOCK:
        proc = STATE.get("process")
        result = {
            "ok": True,
            "current_id": STATE.get("current_id") or "",
            "current_path": STATE.get("current_path") or "",
            "current_title": STATE.get("current_title") or "",
            "playing": bool(STATE.get("playing")),
            "paused": bool(STATE.get("paused")),
            "volume_percent": int(STATE.get("volume_percent") or 80),
            "rc_port": STATE.get("rc_port"),
            "position_seconds": float(STATE.get("last_position_seconds") or 0.0),
            "duration_seconds": float(STATE.get("last_duration_seconds") or 0.0),
            "position_percent": float(STATE.get("last_position_percent") or 0.0),
            "status_valid": bool(STATE.get("last_status_ok")),
            "ended": False,
            "end_reason": "",
            "clock_source": "vlc_rc_get_time",
            "clock_precision": "integer_floor_seconds",
        }

    if not proc or proc.poll() is not None or not result["rc_port"]:
        with LOCK:
            duration = float(STATE.get("last_duration_seconds") or 0.0)
            position = float(STATE.get("last_position_seconds") or 0.0)
            manual_stop = bool(STATE.get("manual_stop"))
            has_track = bool(STATE.get("current_id"))
            ended = bool(
                has_track
                and not manual_stop
                and duration > 0.0
                and position >= max(0.0, duration - 2.0)
            )
            STATE["playing"] = False
            STATE["paused"] = False
            STATE["last_status_ok"] = True
        result["playing"] = False
        result["paused"] = False
        result["status_valid"] = True
        result["ended"] = ended
        result["end_reason"] = "natural" if ended else ("manual_stop" if manual_stop else "")
        return result

    try:
        raw_time = last_number(rc("get_time"))
        raw_length = last_number(rc("get_length"))
        raw_playing = last_number(rc("is_playing"))

        with LOCK:
            if raw_time is not None and float(raw_time) >= 0:
                STATE["last_position_seconds"] = float(raw_time)
            if raw_length is not None and float(raw_length) > 0:
                STATE["last_duration_seconds"] = float(raw_length)

            duration = float(STATE.get("last_duration_seconds") or 0.0)
            position = float(STATE.get("last_position_seconds") or 0.0)

            if duration > 0:
                STATE["last_position_percent"] = max(
                    0.0,
                    min(100.0, position * 100.0 / duration),
                )

            if raw_playing is not None:
                is_playing = bool(int(raw_playing))
                STATE["playing"] = is_playing
                if is_playing:
                    STATE["paused"] = False
                elif position > 0 and (duration <= 0 or position < duration - 0.5):
                    STATE["paused"] = True
                else:
                    STATE["paused"] = False

            STATE["last_status_ok"] = True

            result.update({
                "playing": bool(STATE.get("playing")),
                "paused": bool(STATE.get("paused")),
                "position_seconds": round(float(STATE.get("last_position_seconds") or 0.0),3),
                "duration_seconds": round(float(STATE.get("last_duration_seconds") or 0.0),3),
                "position_percent": round(float(STATE.get("last_position_percent") or 0.0),3),
                "status_valid": True,
            })
    except Exception as exc:
        # IMPORTANT: a transient VLC RC read must never reset the timeline.
        with LOCK:
            STATE["last_status_ok"] = False
            result.update({
                "playing": bool(STATE.get("playing")),
                "paused": bool(STATE.get("paused")),
                "position_seconds": round(float(STATE.get("last_position_seconds") or 0.0),3),
                "duration_seconds": round(float(STATE.get("last_duration_seconds") or 0.0),3),
                "position_percent": round(float(STATE.get("last_position_percent") or 0.0),3),
                "status_valid": False,
                "status_warning": str(exc),
            })
    return result

def control(action, value=None):
    action = str(action or "").strip().lower()
    if action == "pause":
        rc("pause")
        with LOCK:
            STATE["playing"] = False
            STATE["paused"] = True
    elif action in {"resume", "play"}:
        rc("play")
        with LOCK:
            STATE["playing"] = True
            STATE["paused"] = False
    elif action == "stop":
        with LOCK:
            STATE["manual_stop"] = True
        rc("stop")
        with LOCK:
            STATE["playing"] = False
            STATE["paused"] = False
    elif action == "seek_percent":
        pct = max(0.0, min(100.0, float(value or 0)))
        length = float(last_number(rc("get_length")) or 0)
        if length <= 0:
            raise RuntimeError("durée média indisponible")
        rc(f"seek {int(round(length * pct / 100.0))}")
    elif action == "volume_percent":
        pct = max(0, min(100, int(float(value or 0))))
        rc(f"volume {int(round(256 * pct / 100.0))}")
        with LOCK:
            STATE["volume_percent"] = pct
    elif action == "quit":
        terminate_current()
    else:
        raise ValueError("action lecteur inconnue")
    time.sleep(0.08)
    return status_payload()


def playlist_find(item_id):
    for item in load_playlist()["items"]:
        if str(item.get("id")) == str(item_id):
            return item
    raise KeyError("morceau introuvable")


class Handler(BaseHTTPRequestHandler):
    server_version = "AURA-Music-Premium-Bridge/1.0"

    def log_message(self, fmt, *args):
        return

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def send_json(self, code, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        size = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(size) if size else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        try:
            path = urlparse(self.path).path
            if path == "/health":
                self.send_json(200, {"ok": True, "service": "aura-music-premium-bridge", "port": PORT})
            elif path == "/playlist":
                self.send_json(200, {"ok": True, "playlist": aura_refresh_playlist_metadata(False)})
            elif path == "/status":
                self.send_json(200, status_payload())
            elif path == "/library/state":
                self.send_json(200, {"ok": True, "library": load_library_state()})
            elif path == "/collections":
                self.send_json(200, {"ok": True, "collections": load_collections()})
            elif path == "/media/hotkeys":
                self.send_json(200, {"ok": True, "hotkeys": dict(AURA_MEDIA_HOTKEYS)})
            elif path == "/media/smtc":
                self.send_json(200, {"ok": True, "smtc": aura_read_smtc_status()})
            elif path == "/resume":
                self.send_json(200, {"ok": True, "resume": load_resume_state()})
            else:
                self.send_json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            data = self.body()
            if path == "/heartbeat":
                with LOCK:
                    AURA_UI_LIFECYCLE["last_heartbeat"] = time.time()
                self.send_json(200, {"ok": True, "heartbeat": True})
                return
            if path == "/lifecycle/close":
                with LOCK:
                    AURA_UI_LIFECYCLE["last_heartbeat"] = time.time()
                terminate_current()
                self.send_json(200, {"ok": True, "playback_stopped": True})
                return
            if path == "/metadata/refresh":
                self.send_json(200, {"ok": True, "playlist": aura_refresh_playlist_metadata(True)})
            elif path == "/pick":
                self.send_json(200, {"ok": True, **pick_and_update(str(data.get("kind") or "track"))})
            elif path == "/play":
                item = playlist_find(data.get("id"))
                result = launch_item(item)
                library = record_library_play(item)
                self.send_json(200, {**result, "library": library})
            elif path == "/analysis":
                self.send_json(200, {"ok": True, "analysis": aura_analyze_item(data.get("id"))})
            elif path == "/media/command":
                self.send_json(200, aura_media_command(data.get("action")))
            elif path == "/media/play-id":
                self.send_json(200, aura_media_play_id(data.get("id")))
            elif path == "/media/seek":
                self.send_json(200, aura_media_seek(data.get("position")))
            elif path == "/analysis/window":
                self.send_json(200, {"ok": True, "analysis": aura_analysis_window(
                    data.get("id"), data.get("position"), data.get("before", 1.5), data.get("after", 8.5)
                )})
            elif path == "/resume/update":
                self.send_json(200, {"ok": True, "resume": save_resume_state(data.get("id"), data.get("position"), data.get("duration"))})
            elif path == "/resume/clear":
                self.send_json(200, {"ok": True, "resume": clear_resume_state(data.get("id"))})
            elif path == "/playlist/export-m3u8":
                self.send_json(200, {"ok": True, **aura_export_m3u8()})
            elif path == "/playlist/import-m3u8":
                self.send_json(200, {"ok": True, **aura_import_m3u8()})
            elif path == "/collections/save":
                self.send_json(200, {"ok": True, "collections": collection_save_current(data.get("name"))})
            elif path == "/collections/load":
                self.send_json(200, {"ok": True, **collection_load(data.get("id"))})
            elif path == "/collections/rename":
                self.send_json(200, {"ok": True, "collections": collection_rename(data.get("id"), data.get("name"))})
            elif path == "/collections/delete":
                self.send_json(200, {"ok": True, "collections": collection_delete(data.get("id"))})
            elif path == "/library/favorite":
                self.send_json(200, {"ok": True, "library": toggle_library_favorite(data.get("id"), data.get("enabled"))})
            elif path == "/library/select":
                self.send_json(200, {"ok": True, "library": set_library_selected(data.get("id"))})
            elif path == "/library/clear-history":
                library = load_library_state()
                library["history"] = []
                self.send_json(200, {"ok": True, "library": save_library_state(library)})
            elif path == "/control":
                self.send_json(200, control(data.get("action"), data.get("value")))
            elif path == "/playlist/remove":
                item_id = str(data.get("id") or "")
                pl = load_playlist()
                removed = next((x for x in pl["items"] if str(x.get("id")) == item_id), None)
                items = [x for x in pl["items"] if str(x.get("id")) != item_id]
                if removed and str(removed.get("id")) == str(STATE.get("current_id") or ""):
                    terminate_current()
                self.send_json(200, {"ok": True, "playlist": save_playlist(items)})
            elif path == "/playlist/reorder":
                ids = [str(x) for x in (data.get("ids") or [])]
                pl = load_playlist()
                by_id = {str(x.get("id")): x for x in pl["items"]}
                ordered = [by_id[i] for i in ids if i in by_id]
                for item in pl["items"]:
                    if str(item.get("id")) not in ids:
                        ordered.append(item)
                self.send_json(200, {"ok": True, "playlist": save_playlist(ordered)})
            elif path == "/playlist/clear":
                terminate_current()
                self.send_json(200, {"ok": True, "playlist": save_playlist([])})
            else:
                self.send_json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})


def already_running():
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=0.5) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("service") == "aura-music-premium-bridge"
    except Exception:
        return False


def aura_ui_lifecycle_watchdog():
    # AURA_M180_UI4_R4_R5_NO_HEARTBEAT_KILL
    # Browser timers can be throttled or delayed. They are not a reliable
    # application-lifecycle signal and must never terminate audio.
    while True:
        time.sleep(30.0)

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    if already_running():
        return 0
    PIDFILE.write_text(str(os.getpid()), encoding="ascii")
    threading.Thread(
        target=aura_ui_lifecycle_watchdog,
        name="AURA-Music-Lifecycle-Watchdog",
        daemon=True,
    ).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        try:
            PIDFILE.unlink()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
