from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = "aura.obsidian-creative-studio.v140"
INDEX_SCHEMA = "aura.obsidian-creative-index.v140"

EXCLUDED_DIRS = frozenset({
    ".obsidian", ".trash", ".git", ".svn", ".hg", "node_modules",
})

TYPE_ALIASES = {
    "chapter": "chapter", "chapitre": "chapter", "chapters": "chapter", "chapitres": "chapter",
    "character": "character", "characters": "character", "personnage": "character", "personnages": "character",
    "scene": "scene", "scenes": "scene",
    "continuity": "continuity", "continuite": "continuity", "chronology": "continuity",
    "chronologie": "continuity", "timeline": "continuity",
    "world": "world", "worldbuilding": "world", "lore": "world",
    "location": "location", "locations": "location", "lieu": "location", "lieux": "location",
    "note": "note", "notes": "note",
}


class ObsidianStudioError(RuntimeError):
    pass


class VaultBoundaryError(ObsidianStudioError):
    pass


@dataclass(frozen=True)
class VaultInfo:
    path: str
    name: str
    config_present: bool


@dataclass(frozen=True)
class NoteRecord:
    relative_path: str
    title: str
    note_type: str
    tags: tuple[str, ...]
    aliases: tuple[str, ...]
    wikilinks: tuple[str, ...]
    headings: tuple[str, ...]
    frontmatter: dict[str, Any]
    body: str

    def public(self, include_body: bool = False) -> dict[str, Any]:
        out = {
            "relative_path": self.relative_path,
            "title": self.title,
            "note_type": self.note_type,
            "tags": list(self.tags),
            "aliases": list(self.aliases),
            "wikilinks": list(self.wikilinks),
            "headings": list(self.headings),
            "frontmatter": dict(self.frontmatter),
        }
        if include_body:
            out["body"] = self.body
        return out


def _clean(value: Any) -> str:
    s = str(value or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {"'", '"'}:
        s = s[1:-1].strip()
    return s


def _split_list(value: Any) -> list[str]:
    raw = _clean(value)
    if not raw:
        return []
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [_clean(x) for x in re.split(r"[,;]", raw) if _clean(x)]


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + 5:]
    out: dict[str, Any] = {}
    list_key = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) and list_key and line.strip().startswith("- "):
            out.setdefault(list_key, [])
            item = _clean(line.strip()[2:])
            if isinstance(out[list_key], list) and item:
                out[list_key].append(item)
            continue
        list_key = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().casefold()
        value = value.strip()
        if not key:
            continue
        if value == "":
            out[key] = []
            list_key = key
        elif value.startswith("[") and value.endswith("]"):
            out[key] = _split_list(value)
        else:
            out[key] = _clean(value)
    return out, body


def _tokens(text: Any) -> list[str]:
    return [
        x for x in re.findall(r"[a-z0-9\u00c0-\u024f]+", str(text or "").casefold())
        if len(x) >= 2
    ]


def _values(fm: Mapping[str, Any], *keys: str) -> list[str]:
    out = []
    for key in keys:
        value = fm.get(key)
        if isinstance(value, (list, tuple, set)):
            out.extend(_clean(x) for x in value if _clean(x))
        elif value not in (None, ""):
            out.extend(_split_list(value) or [_clean(value)])
    return [x for x in out if x]


def _infer_type(relative_path: str, title: str, fm: Mapping[str, Any]) -> str:
    for key in ("type", "kind", "category", "categorie"):
        value = fm.get(key)
        if isinstance(value, str):
            for token in _tokens(value):
                if token in TYPE_ALIASES:
                    return TYPE_ALIASES[token]
    for folder in reversed(Path(relative_path).parts[:-1]):
        for token in _tokens(folder):
            if token in TYPE_ALIASES:
                return TYPE_ALIASES[token]
    low = title.casefold()
    if re.match(r"^(chapter|chapitre)\s+\d+", low):
        return "chapter"
    if re.match(r"^(scene|sc\u00e8ne)\s+\d+", low):
        return "scene"
    return "note"


def _within(vault: Path, candidate: Path) -> Path:
    root = vault.expanduser().resolve()
    target = candidate.expanduser().resolve()
    try:
        target.relative_to(root)
    except Exception as exc:
        raise VaultBoundaryError(f"path escapes vault boundary: {candidate}") from exc
    return target


def _config_vault_paths() -> list[Path]:
    cfg = Path(os.environ.get("APPDATA", "")) / "obsidian" / "obsidian.json"
    if not cfg.exists():
        return []
    try:
        obj = json.loads(cfg.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    vaults = obj.get("vaults") if isinstance(obj, Mapping) else None
    if not isinstance(vaults, Mapping):
        return []
    out = []
    for row in vaults.values():
        if isinstance(row, Mapping) and isinstance(row.get("path"), str):
            out.append(Path(row["path"]))
    return out


def discover_vaults(extra_roots: Iterable[str | Path] = ()) -> list[VaultInfo]:
    candidates = list(_config_vault_paths())
    user = Path(os.environ.get("USERPROFILE", str(Path.home())))
    roots = [
        user / "Documents",
        user / "Desktop",
        user / "OneDrive",
        user / "OneDrive" / "Documents",
    ]
    roots.extend(Path(x) for x in extra_roots)

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        frontier = [(root, 0)]
        seen = set()
        while frontier:
            current, depth = frontier.pop()
            try:
                key = str(current.resolve()).casefold()
            except Exception:
                continue
            if key in seen:
                continue
            seen.add(key)
            if (current / ".obsidian").is_dir():
                candidates.append(current)
                continue
            if depth >= 4:
                continue
            try:
                children = list(current.iterdir())
            except Exception:
                continue
            for child in children:
                if child.is_dir() and child.name not in EXCLUDED_DIRS and not child.name.startswith("$"):
                    frontier.append((child, depth + 1))

    unique = {}
    for path in candidates:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            continue
        if resolved.is_dir() and (resolved / ".obsidian").is_dir():
            unique[str(resolved).casefold()] = resolved

    return [
        VaultInfo(str(path), path.name, True)
        for path in sorted(unique.values(), key=lambda p: str(p).casefold())
    ]


class ObsidianCreativeStudio:
    def __init__(self, vault_path: str | Path):
        self.vault = Path(vault_path).expanduser().resolve()
        if not self.vault.is_dir():
            raise ObsidianStudioError(f"vault not found: {self.vault}")
        if not (self.vault / ".obsidian").is_dir():
            raise ObsidianStudioError(f".obsidian missing: {self.vault}")
        self._notes: list[NoteRecord] = []
        self._by_stem: dict[str, list[NoteRecord]] = {}

    @property
    def notes(self):
        return tuple(self._notes)

    def _load_note(self, path: Path) -> NoteRecord:
        target = _within(self.vault, path)
        if target.suffix.casefold() != ".md":
            raise ObsidianStudioError("only Markdown notes are supported")
        text = target.read_text(encoding="utf-8-sig", errors="replace")
        fm, body = _parse_frontmatter(text)
        rel = target.relative_to(self.vault).as_posix()

        title = ""
        for key in ("title", "titre", "name", "nom"):
            value = fm.get(key)
            if isinstance(value, str) and value.strip():
                title = value.strip()
                break
        if not title:
            m = re.search(r"(?m)^#\s+(.+?)\s*$", body)
            title = m.group(1).strip() if m else target.stem

        tags = _values(fm, "tags", "tag")
        tags += [
            m.group(1)
            for m in re.finditer(r"(?<![\w/])#([A-Za-z0-9_\-/\u00c0-\u024f]+)", body)
        ]

        aliases = sorted(set(_values(fm, "aliases", "alias")))

        links = []
        for m in re.finditer(r"\[\[([^\]]+)\]\]", body):
            raw = m.group(1).strip()
            link = raw.split("|", 1)[0].split("#", 1)[0].strip()
            if link:
                links.append(link)

        headings = [
            m.group(1).strip()
            for m in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", body)
        ]

        return NoteRecord(
            relative_path=rel,
            title=title,
            note_type=_infer_type(rel, title, fm),
            tags=tuple(sorted(set(x.lstrip("#") for x in tags if x))),
            aliases=tuple(aliases),
            wikilinks=tuple(sorted(set(links), key=str.casefold)),
            headings=tuple(headings),
            frontmatter=dict(fm),
            body=body,
        )

    def build_index(self, max_notes: int = 5000) -> dict[str, Any]:
        max_notes = max(1, min(int(max_notes), 20000))
        rows = []
        for path in sorted(self.vault.rglob("*.md"), key=lambda p: str(p).casefold()):
            rel_parts = path.relative_to(self.vault).parts
            if any(part in EXCLUDED_DIRS for part in rel_parts[:-1]):
                continue
            if len(rows) >= max_notes:
                break
            try:
                rows.append(self._load_note(path))
            except (OSError, UnicodeError, ObsidianStudioError):
                continue

        self._notes = rows
        self._by_stem = {}
        for note in rows:
            self._by_stem.setdefault(Path(note.relative_path).stem.casefold(), []).append(note)
            for alias in note.aliases:
                self._by_stem.setdefault(alias.casefold(), []).append(note)

        counts = {}
        for note in rows:
            counts[note.note_type] = counts.get(note.note_type, 0) + 1

        unresolved = []
        for note in rows:
            for link in note.wikilinks:
                if Path(link).stem.casefold() not in self._by_stem:
                    unresolved.append({"from": note.relative_path, "link": link})

        return {
            "schema": INDEX_SCHEMA,
            "vault": str(self.vault),
            "vault_name": self.vault.name,
            "note_count": len(rows),
            "type_counts": dict(sorted(counts.items())),
            "wikilink_count": sum(len(n.wikilinks) for n in rows),
            "unresolved_wikilinks": unresolved[:200],
            "unresolved_wikilink_count": len(unresolved),
            "read_only": True,
        }

    def creative_snapshot(self) -> dict[str, Any]:
        if not self._notes:
            self.build_index()
        mapping = {
            "chapter": "chapters",
            "character": "characters",
            "scene": "scenes",
            "continuity": "continuity",
            "world": "world",
            "location": "locations",
            "note": "notes",
        }
        groups = {k: [] for k in ("chapters", "characters", "scenes", "continuity", "world", "locations", "notes")}
        for note in self._notes:
            groups[mapping.get(note.note_type, "notes")].append(note.public(False))
        return {
            "schema": SCHEMA,
            "vault": str(self.vault),
            "counts": {k: len(v) for k, v in groups.items()},
            "groups": groups,
            "read_only": True,
        }

    def read_note(self, relative_path: str) -> dict[str, Any]:
        return self._load_note(_within(self.vault, self.vault / relative_path)).public(True)

    def search_context(self, query: str, limit: int = 12) -> dict[str, Any]:
        if not self._notes:
            self.build_index()
        tokens = _tokens(query)
        phrase = str(query or "").strip().casefold()
        scored = []

        for note in self._notes:
            title = note.title.casefold()
            path = note.relative_path.casefold()
            tags = " ".join(note.tags).casefold()
            aliases = " ".join(note.aliases).casefold()
            headings = " ".join(note.headings).casefold()
            body = note.body.casefold()
            score = 0
            reasons = []

            if phrase and phrase in title:
                score += 20
                reasons.append("title_phrase")
            if phrase and phrase in body:
                score += 6
                reasons.append("body_phrase")

            for tok in tokens:
                if tok in title:
                    score += 8
                    reasons.append("title")
                if tok in aliases:
                    score += 7
                    reasons.append("alias")
                if tok in tags:
                    score += 5
                    reasons.append("tag")
                if tok in path:
                    score += 4
                    reasons.append("path")
                if tok in headings:
                    score += 3
                    reasons.append("heading")
                hits = body.count(tok)
                if hits:
                    score += min(hits, 5)
                    reasons.append("body")

            if score <= 0:
                continue

            plain = re.sub(r"\s+", " ", note.body).strip()
            positions = [plain.casefold().find(t) for t in tokens if plain.casefold().find(t) >= 0]
            if positions:
                pos = min(positions)
                snippet = plain[max(0, pos - 100): min(len(plain), pos + 260)].strip()
            else:
                snippet = plain[:320]

            scored.append({
                "score": score,
                "relative_path": note.relative_path,
                "title": note.title,
                "note_type": note.note_type,
                "tags": list(note.tags),
                "reasons": sorted(set(reasons)),
                "snippet": snippet,
            })

        scored.sort(key=lambda r: (-int(r["score"]), str(r["title"]).casefold(), str(r["relative_path"]).casefold()))
        limit = max(1, min(int(limit), 50))
        return {
            "schema": SCHEMA,
            "query": str(query or ""),
            "count": min(len(scored), limit),
            "results": scored[:limit],
            "read_only": True,
        }


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": "v1.4.0-o140.r1",
        "capabilities": [
            "obsidian.discover_vaults",
            "obsidian.build_index",
            "obsidian.creative_snapshot",
            "obsidian.read_note",
            "obsidian.search_context",
        ],
        "mutating_capabilities": [],
        "note_write": False,
        "note_delete": False,
        "shell_execution": False,
        "subprocess_execution": False,
        "vault_boundary_enforced": True,
    }
