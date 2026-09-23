"""AURA A200-R16 read-only deployed UI discovery.

This module only reads metadata/content needed to locate integration seams.
It never writes to the deployed UI root.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Any


A200_R16_DISCOVERY_MARKER = "AURA_A200_R16_DEPLOYED_UI_DISCOVERY_READONLY_V1"
DEPLOYED_UI_MUTATION_ENABLED = False
DISCOVERY_READ_ONLY = True

_TEXT_EXTS = {".js", ".mjs", ".cjs", ".html", ".json", ".css", ".ts", ".tsx", ".jsx"}
_SKIP_PARTS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".aura_transactions",
    "backups",
    "_backups",
}
_TOKENS = {
    "conversation": ("conversation", "chat", "message", "composer"),
    "input": ("textarea", "contenteditable", "input", "send"),
    "transport": ("ipcRenderer", "invoke(", "fetch(", "WebSocket", "EventSource"),
    "router": ("router", "route", "dispatch", "handler"),
    "render": ("render", "appendChild", "innerHTML", "textContent"),
}


@dataclass(frozen=True)
class UiCandidate:
    relative_path: str
    sha256: str
    size: int
    score: int
    categories: tuple[str, ...]


@dataclass(frozen=True)
class UiDiscovery:
    ui_root: str
    tree_fingerprint: str
    file_count: int
    total_bytes: int
    entrypoints: tuple[str, ...]
    candidates: tuple[UiCandidate, ...]


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _SKIP_PARTS for part in rel.parts):
            continue
        yield path, rel


def tree_fingerprint(root: str | Path) -> tuple[str, int, int]:
    root = Path(root)
    digest = hashlib.sha256()
    count = 0
    total = 0
    for path, rel in iter_files(root):
        file_hash = _sha_file(path)
        size = int(path.stat().st_size)
        count += 1
        total += size
        digest.update(str(rel).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), count, total


def discover_ui_root() -> Path:
    explicit = os.environ.get("AURA_DEPLOYED_UI_ROOT")
    if explicit:
        candidate = Path(explicit)
        if candidate.is_dir():
            return candidate

    local = Path(os.environ.get("LOCALAPPDATA") or "")
    base = local / "AURA" / "ui"
    if not base.is_dir():
        raise FileNotFoundError(f"AURA deployed UI base not found: {base}")

    roots = [p for p in base.iterdir() if p.is_dir()]
    if not roots:
        raise FileNotFoundError(f"no deployed UI version folder under {base}")

    def root_score(path: Path):
        signals = 0
        if (path / "aura_ui_config.json").exists():
            signals += 4
        if (path / "index.html").exists():
            signals += 3
        if (path / "dist").is_dir():
            signals += 2
        return (signals, path.stat().st_mtime)

    roots.sort(key=root_score, reverse=True)
    return roots[0]


def scan_deployed_ui(root: str | Path | None = None) -> UiDiscovery:
    ui_root = discover_ui_root() if root is None else Path(root)
    if not ui_root.is_dir():
        raise FileNotFoundError(ui_root)

    fingerprint, file_count, total_bytes = tree_fingerprint(ui_root)
    entrypoints = []
    for rel in ("index.html", "dist/index.html", "aura_ui_config.json"):
        if (ui_root / rel).is_file():
            entrypoints.append(rel)

    candidates = []
    for path, rel in iter_files(ui_root):
        if path.suffix.lower() not in _TEXT_EXTS:
            continue
        if path.stat().st_size > 12 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        categories = []
        score = 0
        lower = text.lower()
        for category, tokens in _TOKENS.items():
            hits = 0
            for token in tokens:
                token_cmp = token.lower()
                if token_cmp in lower:
                    hits += 1
            if hits:
                categories.append(category)
                score += hits

        rel_text = str(rel).lower()
        if any(x in rel_text for x in ("main", "app", "chat", "conversation", "composer", "router", "index")):
            score += 2
        if path.suffix.lower() in {".js", ".mjs", ".html"}:
            score += 1

        if score >= 4:
            candidates.append(
                UiCandidate(
                    relative_path=str(rel).replace("\\", "/"),
                    sha256=_sha_file(path),
                    size=int(path.stat().st_size),
                    score=score,
                    categories=tuple(sorted(set(categories))),
                )
            )

    candidates.sort(key=lambda item: (-item.score, item.relative_path))
    return UiDiscovery(
        ui_root=str(ui_root),
        tree_fingerprint=fingerprint,
        file_count=file_count,
        total_bytes=total_bytes,
        entrypoints=tuple(entrypoints),
        candidates=tuple(candidates[:40]),
    )


def descriptor(discovery: UiDiscovery) -> dict[str, Any]:
    return {
        "schema": "aura.a200.r16.deployed-ui-binding-descriptor.v1",
        "ui_root": discovery.ui_root,
        "tree_fingerprint": discovery.tree_fingerprint,
        "file_count": discovery.file_count,
        "total_bytes": discovery.total_bytes,
        "entrypoints": list(discovery.entrypoints),
        "candidate_count": len(discovery.candidates),
        "candidates": [
            {
                "relative_path": item.relative_path,
                "sha256": item.sha256,
                "size": item.size,
                "score": item.score,
                "categories": list(item.categories),
            }
            for item in discovery.candidates
        ],
        "binding_protocol": "aura.ui-supervised-bridge.v1",
        "runtime_adapter": "runtime/aura_deployed_ui_bridge_adapter_v200.py",
        "live_ui_mutated": False,
    }


def assert_r16_discovery_safety_contract() -> None:
    if not DISCOVERY_READ_ONLY:
        raise RuntimeError("R16 discovery must remain read-only")
    if DEPLOYED_UI_MUTATION_ENABLED:
        raise RuntimeError("deployed UI mutation must remain disabled in R16")
