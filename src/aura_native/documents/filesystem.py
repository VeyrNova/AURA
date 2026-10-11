from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path, PureWindowsPath
import shutil
import stat
import tempfile
from typing import Callable

from .models import DocumentItem, TextDocument

MAX_TEXT_READ_BYTES = 262_144
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".json", ".csv", ".tsv", ".log", ".py", ".qml", ".js", ".css", ".html", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
RESERVED_WINDOWS_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class FileSystemError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code); self.code = code


class FileSystemRepository:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve(strict=False)

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_relative(value: object, *, allow_root: bool = False) -> tuple[str, ...]:
        raw = str(value or "").strip().replace("\\", "/")
        if not raw and allow_root: return ()
        if not raw or "\x00" in raw: raise FileSystemError("INVALID_PATH")
        win = PureWindowsPath(raw)
        if raw.startswith(("/", "//", "~")) or win.is_absolute() or win.drive:
            raise FileSystemError("OUTSIDE_ALLOWED_ROOT")
        parts = tuple(part for part in raw.split("/") if part not in {"", "."})
        if not parts or any(part == ".." for part in parts): raise FileSystemError("OUTSIDE_ALLOWED_ROOT")
        return parts

    @staticmethod
    def validate_name(name: object) -> str:
        value = str(name or "").strip()
        if not value or value in {".", ".."} or any(ch in value for ch in '<>:"/\\|?*\x00'):
            raise FileSystemError("INVALID_NAME")
        if value.endswith((" ", ".")) or value.split(".")[0].upper() in RESERVED_WINDOWS_NAMES:
            raise FileSystemError("INVALID_NAME")
        return value

    @staticmethod
    def _is_reparse(path: Path) -> bool:
        try:
            attrs = getattr(path.lstat(), "st_file_attributes", 0)
            return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        except OSError:
            return False

    def resolve(self, value: object = "", *, must_exist: bool = False, allow_root: bool = False) -> Path:
        parts = self._validate_relative(value, allow_root=allow_root)
        candidate = self.root.joinpath(*parts)
        current = self.root
        for part in parts:
            current = current / part
            if current.exists() and (current.is_symlink() or self._is_reparse(current)):
                raise FileSystemError("OUTSIDE_ALLOWED_ROOT")
        try: resolved = candidate.resolve(strict=False)
        except (OSError, RuntimeError) as exc: raise FileSystemError("INVALID_PATH") from exc
        if resolved != self.root and self.root not in resolved.parents:
            raise FileSystemError("OUTSIDE_ALLOWED_ROOT")
        if must_exist and not resolved.exists(): raise FileSystemError("NOT_FOUND")
        return resolved

    def virtual(self, path: Path) -> str:
        resolved = path.resolve(strict=False)
        if resolved != self.root and self.root not in resolved.parents: raise FileSystemError("OUTSIDE_ALLOWED_ROOT")
        return resolved.relative_to(self.root).as_posix()

    def item(self, path: Path) -> DocumentItem:
        try: info = path.stat()
        except PermissionError as exc: raise FileSystemError("PERMISSION_DENIED") from exc
        return DocumentItem(path.name, self.virtual(path), "folder" if path.is_dir() else "file", 0 if path.is_dir() else info.st_size,
                            datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(), "" if path.is_dir() else path.suffix.lower(),
                            os.access(path, os.R_OK), os.access(path, os.W_OK))

    def list_directory(self, path: str = ""):
        folder = self.resolve(path, must_exist=True, allow_root=True)
        if not folder.is_dir(): raise FileSystemError("INVALID_PATH")
        try: rows = [self.item(child) for child in folder.iterdir() if not child.is_symlink() and not self._is_reparse(child)]
        except PermissionError as exc: raise FileSystemError("PERMISSION_DENIED") from exc
        return tuple(sorted(rows, key=lambda x: (x.kind != "folder", x.name.casefold())))

    def search(self, query: str, *, limit: int = 50, max_depth: int = 5, cancelled: Callable[[], bool] | None = None):
        needle = str(query or "").casefold().strip(); rows=[]
        if not needle: return ()
        for base, dirs, files in os.walk(self.root, followlinks=False):
            base_path=Path(base); depth=len(base_path.relative_to(self.root).parts)
            dirs[:] = [d for d in dirs if depth < max_depth and not (base_path/d).is_symlink() and not self._is_reparse(base_path/d)]
            for name in [*dirs, *files]:
                if cancelled and cancelled(): return tuple(rows)
                path=base_path/name
                if needle in name.casefold() or needle in path.suffix.casefold(): rows.append(self.item(path))
                if len(rows)>=limit: return tuple(sorted(rows,key=lambda x:(x.kind!="folder",x.path.casefold())))
        return tuple(sorted(rows,key=lambda x:(x.kind!="folder",x.path.casefold())))

    @staticmethod
    def _fingerprint(path: Path, data: bytes | None = None) -> str:
        data = path.read_bytes() if data is None else data; info=path.stat()
        return f"{info.st_mtime_ns}:{info.st_size}:{hashlib.sha256(data).hexdigest()}"

    def read_text(self, path: str) -> TextDocument:
        target=self.resolve(path,must_exist=True)
        if not target.is_file(): raise FileSystemError("INVALID_PATH")
        if target.suffix.lower() not in TEXT_EXTENSIONS: raise FileSystemError("UNSUPPORTED_BINARY")
        size=target.stat().st_size
        if size>MAX_TEXT_READ_BYTES: raise FileSystemError("FILE_TOO_LARGE")
        data=target.read_bytes()
        if b"\x00" in data: raise FileSystemError("UNSUPPORTED_BINARY")
        try: content=data.decode("utf-8-sig")
        except UnicodeDecodeError as exc: raise FileSystemError("UNSUPPORTED_BINARY") from exc
        return TextDocument(self.virtual(target),content,len(data),self._fingerprint(target,data))

    def create_folder(self, parent: str, name: str):
        target=self.resolve("/".join(filter(None,(parent,self.validate_name(name)))))
        if target.exists(): raise FileSystemError("ALREADY_EXISTS")
        target.mkdir(parents=False); return self.item(target)

    def create_text(self, parent: str, name: str, content: str = "", *, overwrite: bool = False):
        target=self.resolve("/".join(filter(None,(parent,self.validate_name(name)))))
        if target.exists() and not overwrite: raise FileSystemError("OVERWRITE_REQUIRED")
        if target.exists() and not target.is_file(): raise FileSystemError("ALREADY_EXISTS")
        self._atomic_write(target,str(content).encode("utf-8")); return self.item(target)

    def _atomic_write(self, target: Path, data: bytes) -> None:
        target.parent.mkdir(parents=False,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix=".aura-save-",suffix=".tmp",dir=target.parent)
        try:
            with os.fdopen(fd,"wb") as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp,target)
        except Exception:
            try: Path(tmp).unlink(missing_ok=True)
            finally: raise

    def save_text(self, path: str, content: str, fingerprint: str, *, overwrite_external: bool = False):
        target=self.resolve(path,must_exist=True)
        if target.suffix.lower() not in TEXT_EXTENSIONS: raise FileSystemError("UNSUPPORTED_BINARY")
        if not overwrite_external and self._fingerprint(target)!=fingerprint: raise FileSystemError("EXTERNAL_CHANGE")
        self._atomic_write(target,str(content).encode("utf-8")); return self.read_text(path)

    def move(self, source: str, destination: str, *, overwrite: bool = False):
        src=self.resolve(source,must_exist=True); dst=self.resolve(destination)
        if src==dst: raise FileSystemError("INVALID_PATH")
        if src.is_dir() and (dst==src or src in dst.parents): raise FileSystemError("INVALID_PATH")
        if dst.exists() and not overwrite: raise FileSystemError("OVERWRITE_REQUIRED")
        if dst.exists():
            if dst.is_dir(): raise FileSystemError("ALREADY_EXISTS")
            dst.unlink()
        dst.parent.mkdir(parents=False,exist_ok=True); shutil.move(str(src),str(dst)); return self.item(dst)

    def delete(self, path: str, *, confirmed: bool = False, recursive_confirmed: bool = False):
        if not confirmed: raise FileSystemError("CONFIRMATION_REQUIRED")
        target=self.resolve(path,must_exist=True)
        if target==self.root: raise FileSystemError("OUTSIDE_ALLOWED_ROOT")
        if target.is_dir():
            non_empty=next(target.iterdir(),None) is not None
            if non_empty and not recursive_confirmed: raise FileSystemError("NON_EMPTY_CONFIRMATION_REQUIRED")
            if non_empty: shutil.rmtree(target)
            else: target.rmdir()
        else: target.unlink()
