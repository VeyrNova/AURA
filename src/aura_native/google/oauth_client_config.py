"""Offline-safe Google OAuth client configuration import service."""
from __future__ import annotations
import json, os, tempfile
from dataclasses import dataclass
from pathlib import Path

class OAuthClientConfigError(ValueError):
    def __init__(self, code: str, message: str = "invalid OAuth client"):
        self.code = code
        super().__init__(message)

@dataclass(frozen=True)
class OAuthClientMetadata:
    filename: str
    client_id_present: bool = True
    source: str = "user"

def validate_client_file(path: Path) -> OAuthClientMetadata:
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise OAuthClientConfigError("file_unreadable", "OAuth client file is unreadable") from exc
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OAuthClientConfigError("invalid_json", "OAuth client JSON is invalid") from exc
    if not isinstance(doc, dict):
        raise OAuthClientConfigError("invalid_oauth_client", "OAuth client must be an object")
    if "web" in doc and "installed" not in doc:
        raise OAuthClientConfigError("unsupported_oauth_client_type", "web OAuth clients are unsupported")
    installed = doc.get("installed")
    if not isinstance(installed, dict):
        raise OAuthClientConfigError("invalid_oauth_client", "installed OAuth client is missing")
    if not installed.get("client_id"):
        raise OAuthClientConfigError("missing_client_id", "client_id is required")
    for key in ("client_secret", "token_uri"):
        if not installed.get(key):
            raise OAuthClientConfigError("missing_required_field", f"{key} is required")
    return OAuthClientMetadata(p.name)

class GoogleOAuthClientConfigService:
    def __init__(self, user_root: Path | None = None, env_path: str | None = None):
        root = user_root or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AURA" / "credentials"
        self.root = Path(root)
        self.env_path = env_path if env_path is not None else os.environ.get("AURA_GOOGLE_OAUTH_CLIENT_FILE")
        self.active_path = self.root / "google_oauth_client.json"

    def status(self) -> dict:
        if self.env_path:
            p = Path(self.env_path)
            return {"configured": p.is_file(), "source": "env_override", "filename": p.name if p.is_file() else ""}
        return {"configured": self.active_path.is_file(), "source": "user", "filename": self.active_path.name if self.active_path.is_file() else ""}

    def import_client(self, source: Path, replace: bool = False) -> OAuthClientMetadata:
        metadata = validate_client_file(Path(source))
        self.root.mkdir(parents=True, exist_ok=True)
        if self.active_path.exists() and not replace:
            raise OAuthClientConfigError("replacement_required", "existing client requires replacement")
        fd, tmp = tempfile.mkstemp(prefix="google_oauth_client.", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as out, Path(source).open("rb") as inp:
                out.write(inp.read()); out.flush(); os.fsync(out.fileno())
            os.replace(tmp, self.active_path)
        finally:
            try: Path(tmp).unlink()
            except FileNotFoundError: pass
        return metadata
