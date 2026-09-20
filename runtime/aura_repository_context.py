
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import hashlib
import os
import re

DEFAULT_IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "dist", "build", "coverage", ".coverage",
    "venv", ".venv", "env", ".envdir",
    "_patch_backups", ".aura_transactions",
}
SENSITIVE_BASENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials", "credentials.json", "secrets.json",
    "id_rsa", "id_ed25519", ".npmrc", ".pypirc",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore"}
TEXT_SUFFIXES = {
    ".py",".js",".ts",".tsx",".jsx",".json",".jsonl",".md",".txt",".toml",".yaml",".yml",
    ".ini",".cfg",".conf",".xml",".html",".css",".scss",".sql",".sh",".bat",".cmd",".ps1",
    ".java",".kt",".go",".rs",".c",".h",".cpp",".hpp",".cs",".php",".rb",".swift",".vue",
}
MAX_DEFAULT_FILE_BYTES = 512 * 1024

class WorkspaceBoundaryError(ValueError):
    pass

@dataclass(frozen=True)
class FileRecord:
    path: str
    size_bytes: int
    sha256: str
    suffix: str
    language: str
    lines: int

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def language_for(path: Path) -> str:
    return {
        ".py":"python",".js":"javascript",".ts":"typescript",".tsx":"typescript",
        ".jsx":"javascript",".json":"json",".md":"markdown",".toml":"toml",
        ".yaml":"yaml",".yml":"yaml",".sh":"shell",".bat":"batch",".cmd":"batch",
        ".ps1":"powershell",".go":"go",".rs":"rust",".java":"java",".kt":"kotlin",
        ".cs":"csharp",".cpp":"cpp",".c":"c",".h":"c",".hpp":"cpp",
    }.get(path.suffix.lower(), path.suffix.lower().lstrip(".") or "text")

class WorkspaceBoundary:
    def __init__(self, root: Path | str):
        self.root=Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise WorkspaceBoundaryError("workspace root must be a directory")

    def resolve(self, relative: str | Path, *, must_exist: bool=False) -> Path:
        candidate=Path(relative)
        if candidate.is_absolute():
            resolved=candidate.resolve(strict=must_exist)
        else:
            resolved=(self.root/candidate).resolve(strict=must_exist)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceBoundaryError(f"path escapes workspace: {relative}") from exc
        return resolved

    def relative(self, path: Path | str) -> str:
        resolved=Path(path).resolve()
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise WorkspaceBoundaryError(f"path escapes workspace: {path}") from exc

def is_sensitive_relative(relative: str) -> bool:
    p=Path(relative)
    low=p.name.lower()
    if low in SENSITIVE_BASENAMES:
        return True
    if p.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    parts={x.lower() for x in p.parts}
    if ".ssh" in parts or ".aws" in parts or ".gnupg" in parts:
        return True
    if any(token in low for token in ("secret", "credential")) and p.suffix.lower() in {".json",".yaml",".yml",".txt",".ini",".cfg"}:
        return True
    return False

def _looks_text(path: Path, data: bytes) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if b"\x00" in data[:4096]:
        return False
    try:
        data[:16384].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False

class RepositoryScanner:
    def __init__(self, workspace: Path | str, *, max_file_bytes: int=MAX_DEFAULT_FILE_BYTES, max_files: int=20000):
        self.boundary=WorkspaceBoundary(workspace)
        self.max_file_bytes=int(max_file_bytes)
        self.max_files=int(max_files)

    def _ignored(self, relative: Path) -> bool:
        if any(part in DEFAULT_IGNORED_DIRS for part in relative.parts[:-1]):
            return True
        return is_sensitive_relative(relative.as_posix())

    def scan(self) -> dict[str, Any]:
        records=[]
        skipped={"ignored":0,"sensitive":0,"too_large":0,"binary":0,"symlink":0}
        for root, dirs, files in os.walk(self.boundary.root, topdown=True, followlinks=False):
            rootp=Path(root)
            dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORED_DIRS and not (rootp/d).is_symlink()]
            for name in sorted(files):
                p=rootp/name
                rel=p.relative_to(self.boundary.root)
                if p.is_symlink():
                    skipped["symlink"]+=1
                    continue
                if is_sensitive_relative(rel.as_posix()):
                    skipped["sensitive"]+=1
                    continue
                if self._ignored(rel):
                    skipped["ignored"]+=1
                    continue
                try:
                    size=p.stat().st_size
                except OSError:
                    continue
                if size>self.max_file_bytes:
                    skipped["too_large"]+=1
                    continue
                try:
                    data=p.read_bytes()
                except OSError:
                    continue
                if not _looks_text(p,data):
                    skipped["binary"]+=1
                    continue
                text=data.decode("utf-8",errors="replace")
                records.append(FileRecord(
                    path=rel.as_posix(),
                    size_bytes=size,
                    sha256=sha256_bytes(data),
                    suffix=p.suffix.lower(),
                    language=language_for(p),
                    lines=text.count("\n")+1 if text else 0,
                ))
                if len(records)>=self.max_files:
                    break
            if len(records)>=self.max_files:
                break
        records.sort(key=lambda r:r.path)
        return {
            "schema":"aura.repository-scan.v1",
            "workspace":str(self.boundary.root),
            "file_count":len(records),
            "files":[asdict(r) for r in records],
            "skipped":skipped,
            "policy":{
                "follow_symlinks":False,
                "sensitive_files_excluded":True,
                "ignored_dirs":sorted(DEFAULT_IGNORED_DIRS),
                "max_file_bytes":self.max_file_bytes,
                "max_files":self.max_files,
            },
        }

def _tokens(text: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[A-Za-z0-9_./-]{2,}",text or "")}

def build_context_pack(
    workspace: Path | str,
    *,
    query: str="",
    target_paths: Iterable[str] | None=None,
    max_bytes: int=256*1024,
    max_files: int=80,
) -> dict[str, Any]:
    scanner=RepositoryScanner(workspace)
    scan=scanner.scan()
    boundary=scanner.boundary
    qtokens=_tokens(query)
    targets={Path(x).as_posix() for x in (target_paths or [])}
    ranked=[]
    for rec in scan["files"]:
        path=rec["path"]
        score=0
        if path in targets:
            score+=10000
        p_tokens=_tokens(path)
        score+=25*len(qtokens & p_tokens)
        if any(tok in path.lower() for tok in qtokens):
            score+=10
        if Path(path).name.lower() in {"readme.md","pyproject.toml","package.json","requirements.txt","cargo.toml","go.mod"}:
            score+=3
        ranked.append((score,rec))
    ranked.sort(key=lambda x:(-x[0],x[1]["size_bytes"],x[1]["path"]))

    files=[]
    used=0
    for score,rec in ranked:
        if len(files)>=max_files:
            break
        p=boundary.resolve(rec["path"],must_exist=True)
        raw=p.read_bytes()
        if used+len(raw)>max_bytes and files:
            continue
        text=raw.decode("utf-8",errors="replace")
        files.append({
            "path":rec["path"],"sha256":rec["sha256"],"language":rec["language"],
            "size_bytes":rec["size_bytes"],"relevance_score":score,"content":text,
        })
        used+=len(raw)
        if used>=max_bytes:
            break
    return {
        "schema":"aura.repository-context-pack.v1",
        "workspace":scan["workspace"],
        "query":query,
        "target_paths":sorted(targets),
        "file_count":len(files),
        "bytes":used,
        "max_bytes":max_bytes,
        "files":files,
        "scan_summary":{"file_count":scan["file_count"],"skipped":scan["skipped"]},
        "guardrails":{"workspace_bounded":True,"sensitive_files_excluded":True,"symlinks_not_followed":True},
    }

def capability_snapshot() -> dict[str, Any]:
    return {
        "schema":"aura.repository-context-capabilities.v1",
        "repository_scan":True,
        "bounded_context_pack":True,
        "hashes":True,
        "language_detection":True,
        "sensitive_file_exclusion":True,
        "symlink_following":False,
        "outside_workspace_denied":True,
    }
