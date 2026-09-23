from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(r"C:\AURA GPT version")
UI_DIST = Path.home() / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2" / "dist"
INDEX = ROOT / "data" / "media" / "local_media_index_v180.json"
UI_INDEX = UI_DIST / "aura_music_media_index_v180.json"
ART_DIR = UI_DIST / "aura_music_artwork_v180"

GENERIC_PARENT_NAMES = {
    "music", "musique", "videos", "video", "vidéos", "media", "medias",
    "downloads", "download", "desktop", "bureau"
}
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
GENERIC_COVERS = ("cover", "folder", "front", "album", "artwork", "pochette")

def _text(value: Any) -> str:
    return str(value or "").strip()

def _duration_label(seconds: Any) -> str:
    try:
        sec = int(float(seconds or 0))
    except Exception:
        sec = 0
    if sec <= 0:
        return "--:--"
    return f"{sec // 60}:{sec % 60:02d}"

def _clean_timestamp_title(title: str) -> str:
    raw = _text(title)
    patterns = [
        r"^(20\d{2})[-_.](\d{2})[-_.](\d{2})[ _-]+(\d{2})[-_.](\d{2})[-_.](\d{2})$",
        r"^(20\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})$",
    ]
    for pat in patterns:
        m = re.match(pat, raw)
        if m:
            y, mo, d, hh, mm, ss = m.groups()
            return f"Capture locale • {d}/{mo}/{y} {hh}:{mm}"
    return raw.replace("_", " ").strip()

def _fallback_artist(path: Path, album: str, artist: str) -> str:
    if _text(artist):
        return _text(artist)
    if _text(album) and _text(album).casefold() not in GENERIC_PARENT_NAMES:
        return _text(album)
    parent = path.parent.name.strip()
    if parent and parent.casefold() not in GENERIC_PARENT_NAMES:
        return parent
    return "Bibliothèque locale"

def _find_artwork(media_path: Path) -> Path | None:
    parent = media_path.parent
    stem = media_path.stem
    candidates: list[Path] = []
    for ext in IMAGE_EXTENSIONS:
        candidates.append(parent / f"{stem}{ext}")
        for base in GENERIC_COVERS:
            candidates.append(parent / f"{base}{ext}")
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None

def _copy_artwork(source: Path) -> str:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(source.resolve()).casefold().encode("utf-8")).hexdigest()[:20]
    target = ART_DIR / f"{digest}{source.suffix.casefold()}"
    if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
        shutil.copy2(source, target)
    return f"./aura_music_artwork_v180/{target.name}"

def build_ui_index() -> dict[str, Any]:
    if not INDEX.exists():
        raise FileNotFoundError(INDEX)

    data = json.loads(INDEX.read_text(encoding="utf-8-sig"))
    rows = [dict(x) for x in (data.get("items") or []) if isinstance(x, dict)]

    enriched = []
    artwork_count = 0

    for row in rows:
        media_path = Path(_text(row.get("path")))
        title = _clean_timestamp_title(_text(row.get("title") or media_path.stem or "Media"))
        artist = _fallback_artist(media_path, _text(row.get("album")), _text(row.get("artist")))
        album = _text(row.get("album"))
        media_type = _text(row.get("media_type") or "media").casefold()
        kind = "AUDIO" if media_type == "audio" else "VIDÉO" if media_type == "video" else media_type.upper()

        artwork_url = ""
        if media_path.exists():
            artwork = _find_artwork(media_path)
            if artwork:
                artwork_url = _copy_artwork(artwork)
                artwork_count += 1

        row.update({
            "display_title": title,
            "display_artist": artist,
            "display_album": album,
            "duration_label": _duration_label(row.get("duration_seconds")),
            "media_kind_label": kind,
            "artwork_url": artwork_url,
        })
        enriched.append(row)

    payload = {
        "schema": "aura.music-ui-index.v180.ui2",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_schema": data.get("schema"),
        "source_captured_at": data.get("captured_at"),
        "item_count": len(enriched),
        "audio_count": sum(1 for x in enriched if str(x.get("media_type") or "") == "audio"),
        "video_count": sum(1 for x in enriched if str(x.get("media_type") or "") == "video"),
        "artwork_count": artwork_count,
        "items": enriched,
        "filesystem_media_mutation_performed": False,
        "external_account_mutation_performed": False,
    }

    UI_DIST.mkdir(parents=True, exist_ok=True)
    UI_INDEX.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload

if __name__ == "__main__":
    result = build_ui_index()
    print(
        "[PASS] AURA Music UI2 sync:",
        result["item_count"], "items |",
        result["audio_count"], "audio |",
        result["video_count"], "video |",
        result["artwork_count"], "artworks",
    )
