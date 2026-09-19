from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(r"C:\AURA GPT version")
INDEX = ROOT / "data" / "media" / "local_media_index_v180.json"
SELECTION = ROOT / "data" / "media" / "music_pc_selection_v180.json"

AUDIO = {".mp3",".wav",".flac",".m4a",".aac",".ogg",".opus",".wma"}
VIDEO = {".mp4",".mkv",".mov",".avi",".webm",".m4v",".wmv"}
MEDIA = AUDIO | VIDEO

def _now():
    return datetime.now(timezone.utc).isoformat()

def _media_id(path: Path):
    raw = str(path.resolve()).casefold().encode("utf-8", errors="replace")
    return "media_" + hashlib.sha256(raw).hexdigest()[:20]

def _parse_name(path: Path):
    stem = path.stem.strip()
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return title.strip() or stem, artist.strip()
    return stem, ""

def _ps(script: str) -> str:
    cp = subprocess.run(
        ["powershell.exe","-NoProfile","-STA","-ExecutionPolicy","Bypass","-Command",script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout or "native picker failed").strip())
    return (cp.stdout or "").strip()

def pick_music():
    script = r'''
Add-Type -AssemblyName System.Windows.Forms
$d=New-Object System.Windows.Forms.OpenFileDialog
$d.Title="AURA - Choisir une musique ou un media"
$d.Filter="Audio et video|*.mp3;*.wav;*.flac;*.m4a;*.aac;*.ogg;*.opus;*.wma;*.mp4;*.mkv;*.mov;*.avi;*.webm;*.m4v;*.wmv|Tous les fichiers|*.*"
$d.Multiselect=$true
if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){
 [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
 ConvertTo-Json -InputObject @($d.FileNames) -Compress
}
'''
    raw = _ps(script)
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, str):
        data = [data]
    return [Path(x).expanduser().resolve() for x in data if Path(x).expanduser().exists()]

def pick_playlist():
    script = r'''
Add-Type -AssemblyName System.Windows.Forms
$d=New-Object System.Windows.Forms.OpenFileDialog
$d.Title="AURA - Choisir une playlist"
$d.Filter="Playlists|*.m3u;*.m3u8;*.pls|M3U|*.m3u;*.m3u8|PLS|*.pls"
if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){
 [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
 [Console]::Write($d.FileName)
}
'''
    raw = _ps(script)
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    return p if p.exists() else None

def pick_folder():
    script = r'''
Add-Type -AssemblyName System.Windows.Forms
$d=New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description="AURA - Choisir un dossier musique / media"
$d.ShowNewFolderButton=$false
if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){
 [Console]::OutputEncoding=[System.Text.Encoding]::UTF8
 [Console]::Write($d.SelectedPath)
}
'''
    raw = _ps(script)
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    return p if p.exists() and p.is_dir() else None

def _norm(raw: str, base: Path):
    value = str(raw or "").strip().strip('"').strip("'")
    if value.casefold().startswith("file://"):
        u = urlparse(value)
        value = unquote(u.path or "")
        if re.match(r"^/[A-Za-z]:/", value):
            value = value[1:]
        value = value.replace("/", os.sep)
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = base / p
    return p.resolve()

def parse_playlist(path: Path):
    ext = path.suffix.casefold()
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    out = []
    if ext in {".m3u",".m3u8"}:
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            try:
                p = _norm(s, path.parent)
            except Exception:
                continue
            if p.exists() and p.is_file() and p.suffix.casefold() in MEDIA:
                out.append(p)
    elif ext == ".pls":
        rows = []
        for line in text.splitlines():
            m = re.match(r"(?i)^\s*File(\d+)\s*=\s*(.+?)\s*$", line)
            if not m:
                continue
            try:
                p = _norm(m.group(2), path.parent)
            except Exception:
                continue
            if p.exists() and p.is_file() and p.suffix.casefold() in MEDIA:
                rows.append((int(m.group(1)), p))
        rows.sort(key=lambda x: x[0])
        out = [x[1] for x in rows]
    return out

def scan_folder(folder: Path, limit=5000):
    out = []
    for current, dirs, files in os.walk(folder):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d.casefold() not in {"system volume information","$recycle.bin"}
        ]
        for name in files:
            p = Path(current) / name
            if p.suffix.casefold() in MEDIA:
                out.append(p.resolve())
                if len(out) >= limit:
                    return out
    return out

def _item(path: Path):
    st = path.stat()
    title, artist = _parse_name(path)
    ext = path.suffix.casefold()
    return {
        "media_id": _media_id(path),
        "title": title,
        "artist": artist,
        "media_type": "audio" if ext in AUDIO else "video",
        "genre": "",
        "album": path.parent.name,
        "duration_seconds": 0.0,
        "rating": 0.0,
        "play_count": 0,
        "path": str(path),
        "extension": ext,
        "size_bytes": int(st.st_size),
        "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        "indexed_at": _now(),
        "added_via": "pc_browser",
    }

def register(paths, source_kind, source_path=""):
    clean = []
    seen = set()
    for p in paths:
        try:
            p = p.expanduser().resolve()
        except Exception:
            continue
        key = str(p).casefold()
        if key in seen or not p.exists() or not p.is_file() or p.suffix.casefold() not in MEDIA:
            continue
        seen.add(key)
        clean.append(p)

    data = (
        json.loads(INDEX.read_text(encoding="utf-8-sig"))
        if INDEX.exists()
        else {"schema":"aura.local-media-index.v180","items":[]}
    )
    existing = [dict(x) for x in data.get("items") or [] if isinstance(x, dict)]
    by_path = {}

    for row in existing:
        raw = str(row.get("path") or "").strip()
        if not raw:
            continue
        try:
            key = str(Path(raw).expanduser().resolve()).casefold()
        except Exception:
            key = raw.casefold()
        by_path[key] = row

    new_count = 0
    selected = []
    for p in clean:
        key = str(p).casefold()
        if key not in by_path:
            by_path[key] = _item(p)
            new_count += 1
        selected.append(by_path[key])

    items = list(by_path.values())
    items.sort(key=lambda x:(
        str(x.get("media_type") or ""),
        str(x.get("artist") or "").casefold(),
        str(x.get("title") or "").casefold(),
    ))

    data["captured_at"] = _now()
    data["item_count"] = len(items)
    data["audio_count"] = sum(1 for x in items if x.get("media_type") == "audio")
    data["video_count"] = sum(1 for x in items if x.get("media_type") == "video")
    data["items"] = items
    data["filesystem_mutation_performed"] = False

    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    SELECTION.parent.mkdir(parents=True, exist_ok=True)
    SELECTION.write_text(
        json.dumps({
            "schema":"aura.music-pc-selection.v180",
            "selected_at":_now(),
            "source_kind":source_kind,
            "source_path":source_path,
            "selected_count":len(clean),
            "selected_media_ids":[x.get("media_id") for x in selected],
            "selected_paths":[str(x) for x in clean],
            "new_index_items":new_count,
            "media_file_mutation_performed":False,
            "external_account_mutation_performed":False,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        from runtime.aura_music_ui_sync_v180 import build_ui_index
        build_ui_index()
    except Exception:
        pass

    return {
        "schema":"aura.music-pc-browser.v180",
        "cancelled":False,
        "source_kind":source_kind,
        "source_path":source_path,
        "selected_count":len(clean),
        "new_index_items":new_count,
        "selected":[{
            "media_id":x.get("media_id"),
            "title":x.get("title"),
            "artist":x.get("artist"),
            "path":x.get("path"),
            "media_type":x.get("media_type"),
        } for x in selected],
        "media_file_mutation_performed":False,
        "external_account_mutation_performed":False,
    }

def browse_music():
    paths = pick_music()
    if not paths:
        return {
            "schema":"aura.music-pc-browser.v180",
            "cancelled":True,
            "source_kind":"music_files",
            "selected_count":0,
        }
    return register(paths, "music_files")

def browse_playlist():
    p = pick_playlist()
    if p is None:
        return {
            "schema":"aura.music-pc-browser.v180",
            "cancelled":True,
            "source_kind":"playlist_file",
            "selected_count":0,
        }
    result = register(parse_playlist(p), "playlist_file", str(p))
    result["playlist_path"] = str(p)
    return result

def browse_folder():
    p = pick_folder()
    if p is None:
        return {
            "schema":"aura.music-pc-browser.v180",
            "cancelled":True,
            "source_kind":"folder",
            "selected_count":0,
        }
    result = register(scan_folder(p), "folder", str(p))
    result["folder_path"] = str(p)
    return result

# AURA_M180_UI4_R3_R1_R1_SELECTION_SNAPSHOT
_AURA_M180_UI4_R3_R1_OLD_REGISTER = register
_AURA_M180_UI4_R3_R1_UI_SELECTION = (
    Path.home() / "AppData" / "Local" / "AURA" / "ui"
    / "v0.7.2.2-rc4.2" / "dist"
    / "aura_music_pc_selection_v180.json"
)

def register(paths, source_kind, source_path=""):
    result = _AURA_M180_UI4_R3_R1_OLD_REGISTER(
        paths,
        source_kind,
        source_path,
    )
    try:
        selection = json.loads(SELECTION.read_text(encoding="utf-8-sig"))
        _AURA_M180_UI4_R3_R1_UI_SELECTION.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        _AURA_M180_UI4_R3_R1_UI_SELECTION.write_text(
            json.dumps(selection, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    return result

# AURA_M180_UI4_R3_R2_SELECTION_SNAPSHOT
_AURA_M180_UI4_R3_OLD_REGISTER = register
_AURA_M180_UI4_R3_UI_SELECTION = (
    Path.home() / "AppData" / "Local" / "AURA" / "ui"
    / "v0.7.2.2-rc4.2" / "dist"
    / "aura_music_pc_selection_v180.json"
)

def register(paths, source_kind, source_path=""):
    result = _AURA_M180_UI4_R3_OLD_REGISTER(
        paths,
        source_kind,
        source_path,
    )
    try:
        selection = json.loads(SELECTION.read_text(encoding="utf-8-sig"))
        _AURA_M180_UI4_R3_UI_SELECTION.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        _AURA_M180_UI4_R3_UI_SELECTION.write_text(
            json.dumps(selection, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    return result
