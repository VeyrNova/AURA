from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

INDEX_SCHEMA = "aura.local-media-index.v180"

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma",
})
VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_media_id(path: Path) -> str:
    raw = str(path.resolve()).casefold().encode("utf-8", errors="replace")
    return "media_" + hashlib.sha256(raw).hexdigest()[:20]


def _parse_filename(path: Path) -> tuple[str, str]:
    stem = path.stem.strip()
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return title.strip() or stem, artist.strip()
    return stem, ""


def default_media_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        home / "Music",
        home / "Videos",
        home / "OneDrive" / "Music",
        home / "OneDrive" / "Videos",
        Path(r"C:\Users\Public\Music"),
        Path(r"C:\Users\Public\Videos"),
        Path(r"C:\AURA GPT version\media"),
    ]
    out = []
    seen = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).casefold()
        if key in seen or not path.exists() or not path.is_dir():
            continue
        seen.add(key)
        out.append(path)
    return out


class LocalMediaScanner:
    def __init__(self, *, max_files: int = 25000) -> None:
        self.max_files = max(1, int(max_files))

    def scan(self, roots: Iterable[str | Path]) -> dict[str, Any]:
        root_paths = []
        seen_roots = set()
        for raw in roots:
            p = Path(raw).expanduser()
            if not p.exists() or not p.is_dir():
                continue
            try:
                rp = p.resolve()
            except Exception:
                rp = p
            key = str(rp).casefold()
            if key in seen_roots:
                continue
            seen_roots.add(key)
            root_paths.append(rp)

        items = []
        scanned_files = 0
        errors = []

        for root in root_paths:
            for current, dirs, files in os.walk(root):
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d.casefold() not in {"system volume information", "$recycle.bin"}
                ]
                for name in files:
                    if scanned_files >= self.max_files:
                        break
                    path = Path(current) / name
                    ext = path.suffix.casefold()
                    if ext not in AUDIO_EXTENSIONS and ext not in VIDEO_EXTENSIONS:
                        continue
                    scanned_files += 1
                    try:
                        stat = path.stat()
                        title, artist = _parse_filename(path)
                        media_type = "audio" if ext in AUDIO_EXTENSIONS else "video"
                        items.append({
                            "media_id": _stable_media_id(path),
                            "title": title,
                            "artist": artist,
                            "media_type": media_type,
                            "genre": "",
                            "album": path.parent.name,
                            "duration_seconds": 0.0,
                            "rating": 0.0,
                            "play_count": 0,
                            "path": str(path),
                            "extension": ext,
                            "size_bytes": int(stat.st_size),
                            "modified_at": datetime.fromtimestamp(
                                stat.st_mtime, tz=timezone.utc
                            ).isoformat(),
                            "indexed_at": _now(),
                        })
                    except Exception as exc:
                        errors.append({
                            "path": str(path),
                            "error": type(exc).__name__,
                        })
                if scanned_files >= self.max_files:
                    break
            if scanned_files >= self.max_files:
                break

        items.sort(
            key=lambda x: (
                str(x.get("media_type") or ""),
                str(x.get("artist") or "").casefold(),
                str(x.get("title") or "").casefold(),
            )
        )

        return {
            "schema": INDEX_SCHEMA,
            "captured_at": _now(),
            "roots": [str(x) for x in root_paths],
            "root_count": len(root_paths),
            "item_count": len(items),
            "audio_count": sum(1 for x in items if x["media_type"] == "audio"),
            "video_count": sum(1 for x in items if x["media_type"] == "video"),
            "items": items,
            "errors": errors[:100],
            "read_only_scan": True,
            "filesystem_mutation_performed": False,
        }


def save_index(index_path: str | Path, payload: dict[str, Any]) -> Path:
    path = Path(index_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    os.close(fd)
    temp = Path(temp_name)
    try:
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return path


def refresh_default_index(
    index_path: str | Path,
    *,
    roots: Iterable[str | Path] | None = None,
    max_files: int = 25000,
) -> dict[str, Any]:
    scanner = LocalMediaScanner(max_files=max_files)
    payload = scanner.scan(roots or default_media_roots())
    save_index(index_path, payload)
    return payload
