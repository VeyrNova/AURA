from __future__ import annotations

import io

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from integrations.files.provider import (
    FileContent,
    FileItem,
    FileLookupError,
    FileOperationResult,
    FileQuery,
    FileValidationError,
)
from runtime.connected_accounts_v120 import (
    get_connected_accounts_service_v120,
)


def _default_for(name: str):
    low = name.lower()
    if low.startswith(("is_", "has_", "can_")) or low in {"primary", "all_day", "read", "trashed"}:
        return False
    if low.endswith(("s", "_ids", "_emails", "_phones", "_labels", "_attachments", "_messages", "_items", "_results")):
        return ()
    if low in {"count", "total", "size", "size_bytes", "minutes"}:
        return 0
    return ""

def _make(cls, values):
    import inspect
    sig = inspect.signature(cls)
    kwargs = {}
    for name, param in sig.parameters.items():
        if name in values:
            kwargs[name] = values[name]
        elif param.default is inspect._empty:
            kwargs[name] = _default_for(name)
    return cls(**kwargs)

def _value(obj, *names, default=None):
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


_FOLDER = "application/vnd.google-apps.folder"
_EXPORTS = {
    "application/vnd.google-apps.document": ("text/plain", ".txt"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": ("text/plain", ".txt"),
}

def _item(raw):
    values = {
        "file_id": str(raw.get("id", "")),
        "id": str(raw.get("id", "")),
        "path": str(raw.get("name", "")),
        "name": str(raw.get("name", "")),
        "mime_type": str(raw.get("mimeType", "")),
        "size": int(raw.get("size", 0) or 0),
        "size_bytes": int(raw.get("size", 0) or 0),
        "modified_at": str(raw.get("modifiedTime", "")),
        "created_at": str(raw.get("createdTime", "")),
        "web_view_link": str(raw.get("webViewLink", "")),
        "is_directory": str(raw.get("mimeType", "")) == _FOLDER,
        "is_folder": str(raw.get("mimeType", "")) == _FOLDER,
        "parents": tuple(raw.get("parents", []) or []),
    }
    return _make(FileItem, values)

class GoogleLiveFilesBackendV121:
    mode = "GOOGLE_DRIVE_LIVE_READ_ONLY"

    def __init__(self, *, service=None, api_factory=build):
        self.service = service or get_connected_accounts_service_v120()
        self.api_factory = api_factory

    def _account(self):
        rows = self.service.list_accounts("google")
        if not rows:
            raise FileLookupError("Google account is not connected")
        return rows[0]

    def _drive(self):
        account = self._account()
        credentials = self.service._credentials(account)
        return self.api_factory(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    @staticmethod
    def _fields():
        return "files(id,name,mimeType,size,modifiedTime,createdTime,webViewLink,parents,trashed),nextPageToken"

    def list_files(self, path="/"):
        parent = str(path or "/").strip()
        query = "trashed=false"
        if parent not in {"", "/", "root"}:
            query += " and '" + parent.replace("'", "\\'") + "' in parents"
        response = self._drive().files().list(
            q=query,
            pageSize=100,
            orderBy="folder,name",
            fields=self._fields(),
        ).execute()
        return tuple(_item(x) for x in response.get("files", []) or [])

    def search_files(self, query):
        text = str(_value(query, "text", "query", "search", default=query if isinstance(query, str) else "") or "").strip()
        q = "trashed=false"
        if text:
            escaped = text.replace("\\", "\\\\").replace("'", "\\'")
            q += " and name contains '" + escaped + "'"
        response = self._drive().files().list(
            q=q,
            pageSize=100,
            orderBy="modifiedTime desc",
            fields=self._fields(),
        ).execute()
        return tuple(_item(x) for x in response.get("files", []) or [])

    def _resolve_id(self, value):
        value = str(value or "").strip()
        if not value:
            raise FileLookupError("file identifier required")
        try:
            meta = self._drive().files().get(
                fileId=value,
                fields="id,name,mimeType,size,modifiedTime,createdTime,webViewLink,parents,trashed",
            ).execute()
            return meta
        except Exception:
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            response = self._drive().files().list(
                q="trashed=false and name = '" + escaped + "'",
                pageSize=2,
                fields=self._fields(),
            ).execute()
            rows = response.get("files", []) or []
            if not rows:
                raise FileLookupError("Drive file not found")
            return rows[0]

    def read_file(self, path):
        meta = self._resolve_id(path)
        file_id = meta["id"]
        mime_type = str(meta.get("mimeType", ""))
        if mime_type == _FOLDER:
            raise FileValidationError("cannot read a Drive folder as file")
        drive = self._drive()
        if mime_type in _EXPORTS:
            export_mime, _suffix = _EXPORTS[mime_type]
            request = drive.files().export_media(
                fileId=file_id,
                mimeType=export_mime,
            )
        else:
            request = drive.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
        data = buffer.getvalue()
        text = data.decode("utf-8", errors="replace")
        return _make(
            FileContent,
            {
                "file_id": file_id,
                "id": file_id,
                "path": str(meta.get("name", "")),
                "name": str(meta.get("name", "")),
                "mime_type": mime_type,
                "content": text,
                "text": text,
                "data": data,
                "bytes": data,
                "size": len(data),
                "size_bytes": len(data),
            },
        )

    def _read_only(self, action):
        raise FileValidationError(
            "Google Drive is connected read-only in AURA v1.2.1; "
            + str(action)
            + " is not authorized by the current OAuth scope"
        )

    def create_file(self, *args, **kwargs):
        return self._read_only("create")

    def update_file(self, *args, **kwargs):
        return self._read_only("update")

    def move_file(self, *args, **kwargs):
        return self._read_only("move")

    def delete_file(self, *args, **kwargs):
        return self._read_only("delete")

    def health_snapshot(self):
        account = self._account()
        return {
            "health_state": "google-live-ready",
            "mode": self.mode,
            "provider": "google",
            "account": account.display_label,
            "read_only": True,
            "network_on_demand": True,
        }

__all__ = ["GoogleLiveFilesBackendV121"]
