from __future__ import annotations
import hmac, json, os, secrets, socket, socketserver, threading
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

_MAX_BYTES = 1024 * 1024
_lock = threading.RLock()
_server: Optional[socketserver.ThreadingTCPServer] = None
_thread: Optional[threading.Thread] = None
_token: Optional[str] = None
_callback: Optional[Callable[[Mapping[str, Any]], None]] = None

def _endpoint_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "AURA" / "ui" / "runtime" / "personal-result-ipc-v123.json"

def _write_endpoint(port: int, token: str) -> Path:
    path = _endpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "schema":"aura.v123.personal-result-ipc.v1",
        "host":"127.0.0.1",
        "port":int(port),
        "token":token,
        "pid":os.getpid(),
    }, separators=(",",":")), encoding="utf-8")
    try: os.chmod(tmp, 0o600)
    except Exception: pass
    os.replace(tmp, path)
    return path

class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            raw = self.rfile.readline(_MAX_BYTES + 1)
            if not raw or len(raw) > _MAX_BYTES:
                self.wfile.write(b"ERR\n"); return
            msg = json.loads(raw.decode("utf-8"))
            token = str(msg.get("token") or "")
            payload = msg.get("payload")
            with _lock:
                expected = _token or ""
                callback = _callback
            if not expected or not hmac.compare_digest(token, expected):
                self.wfile.write(b"DENY\n"); return
            if not isinstance(payload, Mapping) or callback is None:
                self.wfile.write(b"ERR\n"); return
            callback(dict(payload))
            self.wfile.write(b"OK\n")
        except Exception:
            try: self.wfile.write(b"ERR\n")
            except Exception: pass

class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

def start_personal_result_ipc_server_v123(callback: Callable[[Mapping[str, Any]], None]):
    global _server, _thread, _token, _callback
    with _lock:
        if _server is not None:
            _callback = callback
            return _server
        token = secrets.token_urlsafe(32)
        server = _Server(("127.0.0.1", 0), _Handler)
        _server, _token, _callback = server, token, callback
        _write_endpoint(server.server_address[1], token)
        thread = threading.Thread(target=server.serve_forever, name="AURA-v123-PersonalResultIPC", daemon=True)
        _thread = thread
        thread.start()
        return server

def stop_personal_result_ipc_server_v123() -> None:
    global _server, _thread, _token, _callback
    with _lock:
        server, thread = _server, _thread
        _server = _thread = _token = _callback = None
    if server is not None:
        try: server.shutdown()
        except Exception: pass
        try: server.server_close()
        except Exception: pass
    if thread is not None:
        try: thread.join(timeout=1.5)
        except Exception: pass
    try: _endpoint_path().unlink(missing_ok=True)
    except Exception: pass

def publish_personal_result_ipc_v123(payload: Mapping[str, Any]) -> bool:
    try:
        meta = json.loads(_endpoint_path().read_text(encoding="utf-8"))
        host = str(meta.get("host") or "")
        port = int(meta.get("port") or 0)
        token = str(meta.get("token") or "")
        if host != "127.0.0.1" or not (1 <= port <= 65535) or not token:
            return False
        body = (json.dumps({"token":token,"payload":dict(payload or {})}, ensure_ascii=False, separators=(",",":")).encode("utf-8") + b"\n")
        if len(body) > _MAX_BYTES: return False
        with socket.create_connection((host, port), timeout=0.8) as sock:
            sock.settimeout(1.5)
            sock.sendall(body)
            reply = b""
            while not reply.endswith(b"\n") and len(reply) < 16:
                chunk = sock.recv(16)
                if not chunk: break
                reply += chunk
        return reply.strip() == b"OK"
    except Exception:
        return False
