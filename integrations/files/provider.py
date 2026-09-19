from __future__ import annotations

import inspect
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional

from integrations.registry import (
    IntegrationCapability,
    IntegrationManifest,
    IntegrationRequest,
)
from integrations.email import (
    EmailProvider,
    SyntheticEmailBackend,
)
from integrations.calendar import (
    CalendarProvider,
    SyntheticCalendarBackend,
)

FILES_PROVIDER_ID = "files.provider"

READ_CAPABILITIES = (
    "files.list",
    "files.search",
    "files.read",
)

WRITE_CAPABILITIES = (
    "files.create",
    "files.update",
    "files.move",
    "files.delete",
)

CONFIRMATION_CAPABILITIES = WRITE_CAPABILITIES

FILES_CAPABILITIES = (
    *READ_CAPABILITIES,
    *WRITE_CAPABILITIES,
)

MAX_READ_BYTES = 262144


def _clean(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class FileItem:
    path: str
    name: str
    is_dir: bool
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "is_dir": self.is_dir,
            "size": int(self.size),
        }


@dataclass(frozen=True)
class FileQuery:
    text: str = ""
    limit: int = 20

    @classmethod
    def from_value(cls, value: Any) -> "FileQuery":
        if isinstance(value, cls):
            return value

        if isinstance(value, Mapping):
            return cls(
                text=_clean(value.get("text")),
                limit=max(
                    1,
                    min(
                        100,
                        int(value.get("limit") or 20),
                    ),
                ),
            )

        return cls(
            text=_clean(value),
            limit=20,
        )


@dataclass(frozen=True)
class FileContent:
    path: str
    text: str
    size: int
    encoding: str = "utf-8"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "text": self.text,
            "size": int(self.size),
            "encoding": self.encoding,
        }


@dataclass(frozen=True)
class FileOperationResult:
    operation: str
    path: str
    destination: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "path": self.path,
            "destination": self.destination,
        }


class FilesProviderError(RuntimeError):
    pass


class FilesPathSecurityError(FilesProviderError):
    pass


class FileLookupError(FilesProviderError):
    pass


class FileValidationError(FilesProviderError):
    pass


class SyntheticFilesBackend:
    def __init__(
        self,
        *,
        root: Optional[Path] = None,
        seed: bool = True,
    ) -> None:
        self._owned_root = root is None

        if root is None:
            root = Path(
                tempfile.mkdtemp(
                    prefix="aura_files_v094_"
                )
            )

        self.root = Path(root).resolve()
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        if seed:
            self._seed()

    def _seed(self) -> None:
        docs = self.root / "documents"
        docs.mkdir(
            parents=True,
            exist_ok=True,
        )

        welcome = docs / "welcome.txt"

        if not welcome.exists():
            welcome.write_text(
                "AURA Files sandbox ready.",
                encoding="utf-8",
            )

        notes = self.root / "notes"
        notes.mkdir(
            parents=True,
            exist_ok=True,
        )

        sample = notes / "aura.txt"

        if not sample.exists():
            sample.write_text(
                "Synthetic local file for AURA v0.9.4.",
                encoding="utf-8",
            )

    def _relative_parts(
        self,
        value: Any,
        *,
        allow_empty: bool = False,
    ) -> tuple[str, ...]:
        raw = _clean(value).replace("\\", "/")

        if not raw:
            if allow_empty:
                return ()
            raise FilesPathSecurityError(
                "empty path is not allowed"
            )

        if "\x00" in raw:
            raise FilesPathSecurityError(
                "NUL byte denied"
            )

        if (
            raw.startswith("/")
            or raw.startswith("//")
            or raw.startswith("~")
            or re.match(r"^[A-Za-z]:", raw)
        ):
            raise FilesPathSecurityError(
                "absolute or host path denied"
            )

        pure = PurePosixPath(raw)
        parts = tuple(
            part
            for part in pure.parts
            if part not in {"", "."}
        )

        if any(part == ".." for part in parts):
            raise FilesPathSecurityError(
                "path traversal denied"
            )

        if not parts and not allow_empty:
            raise FilesPathSecurityError(
                "root path is not a file"
            )

        return parts

    def _resolve(
        self,
        value: Any,
        *,
        must_exist: bool = False,
        allow_root: bool = False,
    ) -> Path:
        parts = self._relative_parts(
            value,
            allow_empty=allow_root,
        )

        candidate = (
            self.root.joinpath(*parts)
            if parts
            else self.root
        )

        resolved = candidate.resolve(
            strict=False
        )

        if not (
            resolved == self.root
            or self.root in resolved.parents
        ):
            raise FilesPathSecurityError(
                "path escaped allowed sandbox root"
            )

        if must_exist and not resolved.exists():
            raise FileLookupError(
                "file not found: " + str(value)
            )

        return resolved

    def _virtual(self, path: Path) -> str:
        resolved = Path(path).resolve(
            strict=False
        )

        if not (
            resolved == self.root
            or self.root in resolved.parents
        ):
            raise FilesPathSecurityError(
                "resolved path escaped sandbox"
            )

        rel = resolved.relative_to(
            self.root
        )

        return rel.as_posix()

    def _item(self, path: Path) -> FileItem:
        path = Path(path)
        stat = path.stat()

        return FileItem(
            path=self._virtual(path),
            name=path.name,
            is_dir=path.is_dir(),
            size=0 if path.is_dir() else int(stat.st_size),
        )

    def list_files(
        self,
        path: str = "",
    ) -> tuple[FileItem, ...]:
        folder = self._resolve(
            path,
            must_exist=True,
            allow_root=True,
        )

        if not folder.is_dir():
            raise FileValidationError(
                "list target is not a directory"
            )

        return tuple(
            self._item(item)
            for item in sorted(
                folder.iterdir(),
                key=lambda p: (
                    not p.is_dir(),
                    p.name.casefold(),
                ),
            )
        )

    def search_files(
        self,
        query: FileQuery,
    ) -> tuple[FileItem, ...]:
        needle = query.text.casefold().strip()
        rows = []

        for item in self.root.rglob("*"):
            try:
                resolved = item.resolve(
                    strict=False
                )
            except OSError:
                continue

            if not (
                resolved == self.root
                or self.root in resolved.parents
            ):
                continue

            rel = self._virtual(resolved)

            if needle and needle not in rel.casefold():
                continue

            rows.append(
                self._item(resolved)
            )

            if len(rows) >= query.limit:
                break

        rows.sort(
            key=lambda row: (
                not row.is_dir,
                row.path.casefold(),
            )
        )

        return tuple(rows[:query.limit])

    def read_file(
        self,
        path: str,
    ) -> FileContent:
        target = self._resolve(
            path,
            must_exist=True,
        )

        if not target.is_file():
            raise FileValidationError(
                "read target is not a file"
            )

        size = int(
            target.stat().st_size
        )

        if size > MAX_READ_BYTES:
            raise FileValidationError(
                "file exceeds synthetic read limit"
            )

        data = target.read_bytes()

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode(
                "utf-8",
                errors="replace",
            )

        return FileContent(
            path=self._virtual(target),
            text=text,
            size=len(data),
        )

    def create_file(
        self,
        *,
        path: str,
        text: str = "",
    ) -> tuple[FileOperationResult, FileItem]:
        target = self._resolve(
            path,
            must_exist=False,
        )

        if target.exists():
            raise FileValidationError(
                "create target already exists"
            )

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Parent containment is re-checked after mkdir in case any
        # existing symlink changes the resolved destination.
        target = self._resolve(
            path,
            must_exist=False,
        )

        target.write_text(
            str(text or ""),
            encoding="utf-8",
        )

        return (
            FileOperationResult(
                operation="create",
                path=self._virtual(target),
            ),
            self._item(target),
        )

    def update_file(
        self,
        *,
        path: str,
        text: str,
        append: bool = False,
    ) -> tuple[FileOperationResult, FileItem]:
        target = self._resolve(
            path,
            must_exist=True,
        )

        if not target.is_file():
            raise FileValidationError(
                "update target is not a file"
            )

        if append:
            with target.open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(
                    str(text or "")
                )
        else:
            target.write_text(
                str(text or ""),
                encoding="utf-8",
            )

        return (
            FileOperationResult(
                operation=(
                    "append"
                    if append
                    else "update"
                ),
                path=self._virtual(target),
            ),
            self._item(target),
        )

    def move_file(
        self,
        *,
        source: str,
        destination: str,
    ) -> tuple[FileOperationResult, FileItem]:
        src = self._resolve(
            source,
            must_exist=True,
        )

        if not src.is_file():
            raise FileValidationError(
                "only files can be moved"
            )

        dst = self._resolve(
            destination,
            must_exist=False,
        )

        if dst.exists():
            raise FileValidationError(
                "move destination already exists"
            )

        dst.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        dst = self._resolve(
            destination,
            must_exist=False,
        )

        shutil.move(
            str(src),
            str(dst),
        )

        final = self._resolve(
            destination,
            must_exist=True,
        )

        return (
            FileOperationResult(
                operation="move",
                path=str(source).replace("\\", "/"),
                destination=self._virtual(final),
            ),
            self._item(final),
        )

    def delete_file(
        self,
        *,
        path: str,
    ) -> FileOperationResult:
        target = self._resolve(
            path,
            must_exist=True,
        )

        if not target.is_file():
            raise FileValidationError(
                "only files can be deleted"
            )

        virtual = self._virtual(
            target
        )

        target.unlink()

        return FileOperationResult(
            operation="delete",
            path=virtual,
        )

    def health_snapshot(self) -> Mapping[str, Any]:
        return {
            "available": True,
            "health_state": "synthetic-sandbox-ready",
            "provider_id": FILES_PROVIDER_ID,
            "mode": "SYNTHETIC_LOCAL_SANDBOX",
            "external_connection": False,
            "allowed_roots_only": True,
            "network_side_effects": False,
        }


def _reference_capabilities() -> dict[str, IntegrationCapability]:
    email_manifest = EmailProvider(
        backend=SyntheticEmailBackend()
    ).manifest

    calendar_manifest = CalendarProvider(
        backend=SyntheticCalendarBackend()
    ).manifest

    refs = {
        getattr(capability, "capability_id", ""): capability
        for capability in (
            tuple(email_manifest.capabilities)
            + tuple(calendar_manifest.capabilities)
        )
    }

    required = {
        "email.search",
        "email.read",
        "calendar.create_event",
        "calendar.update_event",
        "calendar.delete_event",
    }

    missing = sorted(
        required.difference(refs)
    )

    if missing:
        raise RuntimeError(
            "missing certified reference capabilities: "
            + ", ".join(missing)
        )

    return refs


_REFERENCE_CAPS = _reference_capabilities()

_REFERENCE_BY_FILES_CAPABILITY = {
    "files.list": "email.search",
    "files.search": "email.search",
    "files.read": "email.read",
    "files.create": "calendar.create_event",
    "files.update": "calendar.update_event",
    "files.move": "calendar.update_event",
    "files.delete": "calendar.delete_event",
}


def _cap(
    capability_id: str,
    *,
    mutating: bool,
) -> IntegrationCapability:
    signature = inspect.signature(
        IntegrationCapability
    )

    reference_id = (
        _REFERENCE_BY_FILES_CAPABILITY[
            capability_id
        ]
    )
    reference = _REFERENCE_CAPS[
        reference_id
    ]

    values = {
        "capability_id": capability_id,
        "action": capability_id,
        "description": capability_id,
        "mutating": mutating,
        "read_only": not mutating,
        "requires_confirmation": mutating,
        "kind": (
            "write"
            if mutating
            else "read"
        ),
        "risk_tier": getattr(
            reference,
            "risk_tier",
            None,
        ),
        "side_effect_class": getattr(
            reference,
            "side_effect_class",
            None,
        ),
        "evidence_required": getattr(
            reference,
            "evidence_required",
            None,
        ),
    }

    kwargs = {}

    for name, parameter in signature.parameters.items():
        if (
            name in values
            and values[name] is not None
        ):
            kwargs[name] = values[name]
        elif hasattr(reference, name):
            kwargs[name] = getattr(
                reference,
                name,
            )
        elif parameter.default is inspect._empty:
            raise RuntimeError(
                "cannot derive required IntegrationCapability field "
                + name
                + " from certified reference "
                + reference_id
            )

    capability = IntegrationCapability(
        **kwargs
    )

    if getattr(
        capability,
        "risk_tier",
        None,
    ) is None:
        raise RuntimeError(
            "Files capability missing risk_tier: "
            + capability_id
        )

    if getattr(
        capability,
        "side_effect_class",
        None,
    ) is None:
        raise RuntimeError(
            "Files capability missing side_effect_class: "
            + capability_id
        )

    return capability


def _manifest() -> IntegrationManifest:
    signature = inspect.signature(
        IntegrationManifest
    )

    values = {
        "provider_id": FILES_PROVIDER_ID,
        "display_name": "Files",
        "provider_version": "0.9.4",
        "capabilities": tuple(
            _cap(
                capability_id,
                mutating=(
                    capability_id
                    in WRITE_CAPABILITIES
                ),
            )
            for capability_id
            in FILES_CAPABILITIES
        ),
        "auth_kind": "none",
        "metadata": {
            "mode": "synthetic-local-sandbox",
            "provider_neutral": True,
            "external_connection": False,
            "allowed_roots_only": True,
            "path_traversal": "fail-closed",
            "symlink_escape": "deny",
            "network_side_effects": False,
        },
    }

    kwargs = {
        name: values[name]
        for name in signature.parameters
        if name in values
    }

    return IntegrationManifest(
        **kwargs
    )


FILES_MANIFEST = _manifest()


class FilesProvider:
    def __init__(
        self,
        *,
        backend: Optional[SyntheticFilesBackend] = None,
    ) -> None:
        self.backend = (
            backend
            if backend is not None
            else SyntheticFilesBackend()
        )

    @property
    def manifest(self) -> IntegrationManifest:
        return FILES_MANIFEST

    def health_snapshot(self) -> Mapping[str, Any]:
        return self.backend.health_snapshot()

    def execute(
        self,
        request: IntegrationRequest,
    ) -> Mapping[str, Any]:
        if request.provider_id != FILES_PROVIDER_ID:
            raise FilesProviderError(
                "wrong provider_id: "
                + str(request.provider_id)
            )

        capability = request.capability_id
        params = dict(
            request.params or {}
        )

        if capability == "files.list":
            items = self.backend.list_files(
                _clean(
                    params.get("path")
                )
            )
            return {
                "items": [
                    item.to_dict()
                    for item in items
                ]
            }

        if capability == "files.search":
            query = FileQuery.from_value(
                params.get("query")
            )
            items = self.backend.search_files(
                query
            )
            return {
                "items": [
                    item.to_dict()
                    for item in items
                ]
            }

        if capability == "files.read":
            content = self.backend.read_file(
                _clean(
                    params.get("path")
                )
            )
            return {
                "content": content.to_dict()
            }

        if capability == "files.create":
            operation, item = (
                self.backend.create_file(
                    path=_clean(
                        params.get("path")
                    ),
                    text=str(
                        params.get("text")
                        or ""
                    ),
                )
            )
            return {
                "operation": operation.to_dict(),
                "item": item.to_dict(),
            }

        if capability == "files.update":
            operation, item = (
                self.backend.update_file(
                    path=_clean(
                        params.get("path")
                    ),
                    text=str(
                        params.get("text")
                        or ""
                    ),
                    append=bool(
                        params.get("append")
                    ),
                )
            )
            return {
                "operation": operation.to_dict(),
                "item": item.to_dict(),
            }

        if capability == "files.move":
            operation, item = (
                self.backend.move_file(
                    source=_clean(
                        params.get("source")
                    ),
                    destination=_clean(
                        params.get(
                            "destination"
                        )
                    ),
                )
            )
            return {
                "operation": operation.to_dict(),
                "item": item.to_dict(),
            }

        if capability == "files.delete":
            operation = (
                self.backend.delete_file(
                    path=_clean(
                        params.get("path")
                    )
                )
            )
            return {
                "operation": operation.to_dict()
            }

        raise FilesProviderError(
            "unsupported Files capability: "
            + str(capability)
        )


FileProvider = FilesProvider


__all__ = [
    "FILES_PROVIDER_ID",
    "FILES_CAPABILITIES",
    "READ_CAPABILITIES",
    "WRITE_CAPABILITIES",
    "CONFIRMATION_CAPABILITIES",
    "FILES_MANIFEST",
    "MAX_READ_BYTES",
    "FileItem",
    "FileQuery",
    "FileContent",
    "FileOperationResult",
    "FilesProvider",
    "FileProvider",
    "SyntheticFilesBackend",
    "FilesProviderError",
    "FilesPathSecurityError",
    "FileLookupError",
    "FileValidationError",
]
