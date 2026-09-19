from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma",
})
VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalPlayerError(RuntimeError):
    pass


class LocalPlayerConfirmationRequired(LocalPlayerError):
    pass


class ControlledLocalPlayer:
    def __init__(
        self,
        *,
        index_path: str | Path,
        session_path: str | Path,
    ) -> None:
        self.index_path = Path(index_path).expanduser().resolve()
        self.session_path = Path(session_path).expanduser().resolve()

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            raise LocalPlayerError("media index missing")
        data = json.loads(self.index_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise LocalPlayerError("invalid media index")
        return data

    def _save_session(self, payload: Mapping[str, Any]) -> None:
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=self.session_path.name + ".",
            suffix=".tmp",
            dir=str(self.session_path.parent),
        )
        os.close(fd)
        temp = Path(temp_name)
        try:
            temp.write_text(
                json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temp, self.session_path)
        finally:
            if temp.exists():
                temp.unlink()

    def _find_item(
        self,
        *,
        media_id: str = "",
        query: str = "",
        first: bool = False,
    ) -> dict[str, Any]:
        rows = [
            dict(x)
            for x in self._load_index().get("items") or []
            if isinstance(x, Mapping)
        ]
        if not rows:
            raise LocalPlayerError("media index is empty")

        if media_id:
            for row in rows:
                if str(row.get("media_id") or "") == str(media_id):
                    return row
            raise LocalPlayerError("media_id not found")

        q = str(query or "").strip().casefold()
        if q:
            for row in rows:
                hay = " ".join(
                    str(row.get(k) or "")
                    for k in ("title", "artist", "album", "path")
                ).casefold()
                if q in hay:
                    return row
            raise LocalPlayerError("no media matches query")

        if first:
            return rows[0]

        raise LocalPlayerError("media selector required")

    def _validate_path(self, row: Mapping[str, Any]) -> Path:
        path = Path(str(row.get("path") or "")).expanduser()
        if not path.exists() or not path.is_file():
            raise LocalPlayerError("indexed media file no longer exists")
        ext = path.suffix.casefold()
        if ext not in AUDIO_EXTENSIONS and ext not in VIDEO_EXTENSIONS:
            raise LocalPlayerError("unsupported media extension")
        return path.resolve()

    def _vlc_path(self) -> str | None:
        override = str(os.environ.get("AURA_M180_PLAYER_EXECUTABLE") or "").strip()
        if override and Path(override).exists():
            return override

        found = shutil.which("vlc.exe") or shutil.which("vlc")
        if found:
            return found

        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "VideoLAN" / "VLC" / "vlc.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "VideoLAN" / "VLC" / "vlc.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def launch(
        self,
        *,
        media_id: str = "",
        query: str = "",
        first: bool = False,
        user_confirmed: bool,
    ) -> dict[str, Any]:
        if not user_confirmed:
            raise LocalPlayerConfirmationRequired(
                "explicit user confirmation required"
            )

        row = self._find_item(
            media_id=media_id,
            query=query,
            first=first,
        )
        path = self._validate_path(row)

        test_mode = str(
            os.environ.get("AURA_M180_PLAYER_TEST_MODE") or ""
        ).strip().casefold() in {"1", "true", "yes"}

        backend = "test_mode"
        pid = None
        launched = False

        if test_mode:
            launched = True
        else:
            vlc = self._vlc_path()
            if vlc:
                proc = subprocess.Popen(
                    [vlc, "--play-and-exit", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                backend = "vlc"
                pid = int(proc.pid)
                launched = True
            else:
                if not hasattr(os, "startfile"):
                    raise LocalPlayerError(
                        "no supported local player backend available"
                    )
                os.startfile(str(path))
                backend = "windows_shell"
                launched = True

        session = {
            "schema": "aura.controlled-local-player.v180",
            "state": "launch_confirmed",
            "media_id": row.get("media_id"),
            "title": row.get("title"),
            "artist": row.get("artist"),
            "media_type": row.get("media_type"),
            "path": str(path),
            "backend": backend,
            "pid": pid,
            "launched_at": _now(),
            "launch_succeeded": launched,
            "explicit_user_confirmation": True,
            "test_mode": test_mode,
            "filesystem_mutation_performed": False,
            "external_account_mutation_performed": False,
        }
        self._save_session(session)
        return session

    def status(self) -> dict[str, Any]:
        if not self.session_path.exists():
            return {
                "schema": "aura.controlled-local-player.v180",
                "state": "idle",
                "session_present": False,
                "filesystem_mutation_performed": False,
                "external_account_mutation_performed": False,
            }
        data = json.loads(
            self.session_path.read_text(encoding="utf-8-sig")
        )
        data["session_present"] = True
        return data

# AURA_M180_UI4_R3_R1_R1_VLC_PREMIUM_PLAYER
import socket as _aura_m180_ui4_r3_r1_socket
import threading as _aura_m180_ui4_r3_r1_threading
import time as _aura_m180_ui4_r3_r1_time
import uuid as _aura_m180_ui4_r3_r1_uuid
import re as _aura_m180_ui4_r3_r1_re
from pathlib import Path as _AuraM180Ui4R3Path

_AURA_M180_UI4_R3_R1_OLD_LAUNCH = ControlledLocalPlayer.launch
_AURA_M180_UI4_R3_R1_OLD_STATUS = ControlledLocalPlayer.status
_AURA_M180_UI4_R3_R1_LIVE = (
    _AuraM180Ui4R3Path.home()
    / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2"
    / "dist" / "aura_music_player_live_v180.json"
)

def _aura_m180_ui4_r3_r1_free_port():
    sock = _aura_m180_ui4_r3_r1_socket.socket(
        _aura_m180_ui4_r3_r1_socket.AF_INET,
        _aura_m180_ui4_r3_r1_socket.SOCK_STREAM,
    )
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()

def _aura_m180_ui4_r3_r1_rc(port, command, timeout=0.7):
    last = None
    for _ in range(6):
        sock = None
        try:
            sock = _aura_m180_ui4_r3_r1_socket.create_connection(
                ("127.0.0.1", int(port)),
                timeout=timeout,
            )
            sock.settimeout(timeout)
            try:
                sock.recv(4096)
            except Exception:
                pass
            sock.sendall((str(command).strip() + "\n").encode("utf-8"))
            _aura_m180_ui4_r3_r1_time.sleep(0.05)
            chunks = []
            while True:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
                    if len(b"".join(chunks)) > 16384:
                        break
                except Exception:
                    break
            return b"".join(chunks).decode("utf-8", errors="replace")
        except Exception as exc:
            last = exc
            _aura_m180_ui4_r3_r1_time.sleep(0.18)
        finally:
            try:
                if sock:
                    sock.close()
            except Exception:
                pass
    raise LocalPlayerError(f"VLC RC unavailable: {last}")

def _aura_m180_ui4_r3_r1_number(text):
    values = []
    for line in str(text or "").replace("\r", "\n").split("\n"):
        clean = line.strip().lstrip(">").strip()
        m = _aura_m180_ui4_r3_r1_re.search(r"(-?\d+(?:\.\d+)?)\s*$", clean)
        if m:
            try:
                values.append(float(m.group(1)))
            except Exception:
                pass
    return values[-1] if values else None

def _aura_m180_ui4_r3_r1_atomic_json(path, payload):
    path = _AuraM180Ui4R3Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)

def _aura_m180_ui4_r3_r1_monitor(session_path, monitor_id, port, pid, media_id, title):
    failures = 0
    while True:
        try:
            session_file = _AuraM180Ui4R3Path(session_path)
            if not session_file.exists():
                break
            current = json.loads(session_file.read_text(encoding="utf-8-sig"))
            if str(current.get("premium_monitor_id") or "") != str(monitor_id):
                break

            t = _aura_m180_ui4_r3_r1_number(
                _aura_m180_ui4_r3_r1_rc(port, "get_time", timeout=0.45)
            )
            length = _aura_m180_ui4_r3_r1_number(
                _aura_m180_ui4_r3_r1_rc(port, "get_length", timeout=0.45)
            )
            playing = _aura_m180_ui4_r3_r1_number(
                _aura_m180_ui4_r3_r1_rc(port, "is_playing", timeout=0.45)
            )

            duration = max(0.0, float(length or 0.0))
            position = max(0.0, float(t or 0.0))
            percent = (
                max(0.0, min(100.0, position * 100.0 / duration))
                if duration > 0 else 0.0
            )
            payload = {
                "schema": "aura.music-premium-live.v180",
                "monitor_id": monitor_id,
                "media_id": media_id,
                "title": title,
                "pid": pid,
                "rc_port": int(port),
                "playing": bool(int(playing or 0)),
                "position_seconds": round(position, 3),
                "duration_seconds": round(duration, 3),
                "position_percent": round(percent, 3),
                "volume_percent": current.get("volume_percent", 80),
                "playback_state": current.get("playback_state", "playing"),
                "captured_at": _now(),
            }
            _aura_m180_ui4_r3_r1_atomic_json(_AURA_M180_UI4_R3_R1_LIVE, payload)
            failures = 0
        except Exception:
            failures += 1
            if failures >= 12:
                try:
                    _aura_m180_ui4_r3_r1_atomic_json(
                        _AURA_M180_UI4_R3_R1_LIVE,
                        {
                            "schema": "aura.music-premium-live.v180",
                            "monitor_id": monitor_id,
                            "media_id": media_id,
                            "title": title,
                            "pid": pid,
                            "playing": False,
                            "position_seconds": 0,
                            "duration_seconds": 0,
                            "position_percent": 0,
                            "playback_state": "ended",
                            "captured_at": _now(),
                        },
                    )
                except Exception:
                    pass
                break
        _aura_m180_ui4_r3_r1_time.sleep(0.55)

def _aura_m180_ui4_r3_r1_stop_previous(self):
    try:
        old = _AURA_M180_UI4_R3_R1_OLD_STATUS(self)
    except Exception:
        return
    port = old.get("rc_port")
    if port:
        try:
            _aura_m180_ui4_r3_r1_rc(int(port), "quit", timeout=0.35)
            return
        except Exception:
            pass
    pid = old.get("pid")
    if pid and str(old.get("backend") or "") == "vlc":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
        except Exception:
            pass

def _aura_m180_ui4_r3_r1_launch(
    self,
    *,
    media_id="",
    query="",
    first=False,
    user_confirmed,
):
    if not user_confirmed:
        raise LocalPlayerConfirmationRequired("explicit user confirmation required")

    row = self._find_item(media_id=media_id, query=query, first=first)
    path = self._validate_path(row)

    test_mode = str(
        os.environ.get("AURA_M180_PLAYER_TEST_MODE") or ""
    ).strip().casefold() in {"1", "true", "yes"}

    if test_mode:
        return _AURA_M180_UI4_R3_R1_OLD_LAUNCH(
            self,
            media_id=media_id,
            query=query,
            first=first,
            user_confirmed=user_confirmed,
        )

    vlc = self._vlc_path()
    if not vlc:
        return _AURA_M180_UI4_R3_R1_OLD_LAUNCH(
            self,
            media_id=media_id,
            query=query,
            first=first,
            user_confirmed=user_confirmed,
        )

    _aura_m180_ui4_r3_r1_stop_previous(self)
    port = _aura_m180_ui4_r3_r1_free_port()
    monitor_id = "musicmon_" + _aura_m180_ui4_r3_r1_uuid.uuid4().hex[:16]

    args = [
        vlc,
        "--no-one-instance",
        "--no-video-title-show",
        "--extraintf=rc",
        f"--rc-host=127.0.0.1:{port}",
        "--rc-quiet",
        "--play-and-exit",
    ]
    if str(row.get("media_type") or "").casefold() == "audio":
        args.insert(1, "--intf=dummy")
    args.append(str(path))

    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    session = {
        "schema": "aura.controlled-local-player.v180",
        "state": "launch_confirmed",
        "playback_state": "playing",
        "media_id": row.get("media_id"),
        "title": row.get("title"),
        "artist": row.get("artist"),
        "media_type": row.get("media_type"),
        "path": str(path),
        "backend": "vlc",
        "pid": int(proc.pid),
        "rc_port": int(port),
        "premium_control": True,
        "premium_monitor_id": monitor_id,
        "volume_percent": 80,
        "launched_at": _now(),
        "launch_succeeded": True,
        "explicit_user_confirmation": True,
        "test_mode": False,
        "filesystem_mutation_performed": False,
        "external_account_mutation_performed": False,
    }
    self._save_session(session)

    thread = _aura_m180_ui4_r3_r1_threading.Thread(
        target=_aura_m180_ui4_r3_r1_monitor,
        args=(
            str(self.session_path),
            monitor_id,
            port,
            int(proc.pid),
            str(row.get("media_id") or ""),
            str(row.get("title") or ""),
        ),
        name="AURA-Music-Premium-Monitor",
        daemon=True,
    )
    thread.start()
    return session

def _aura_m180_ui4_r3_r1_control(self, action, value=None):
    session = _AURA_M180_UI4_R3_R1_OLD_STATUS(self)
    if not session.get("session_present"):
        raise LocalPlayerError("no active local player session")
    if str(session.get("backend") or "") != "vlc" or not session.get("rc_port"):
        raise LocalPlayerError("premium player control requires VLC RC session")

    action = str(action or "").strip().casefold()
    port = int(session["rc_port"])
    command = ""
    playback_state = str(session.get("playback_state") or "")

    if action == "pause":
        command = "pause"
        playback_state = "paused"
    elif action in {"resume", "play"}:
        command = "play"
        playback_state = "playing"
    elif action == "stop":
        command = "stop"
        playback_state = "stopped"
    elif action == "quit":
        command = "quit"
        playback_state = "closed"
    elif action == "seek_percent":
        pct = max(0.0, min(100.0, float(value or 0)))
        length = _aura_m180_ui4_r3_r1_number(
            _aura_m180_ui4_r3_r1_rc(port, "get_length")
        )
        if not length or length <= 0:
            raise LocalPlayerError("media duration unavailable")
        seconds = int(round(float(length) * pct / 100.0))
        command = f"seek {seconds}"
        session["seek_percent"] = pct
    elif action == "volume_percent":
        pct = int(max(0, min(100, int(float(value or 0)))))
        # VLC RC volume uses 256 as nominal 100%.
        command = f"volume {int(round(256 * pct / 100.0))}"
        session["volume_percent"] = pct
    else:
        raise LocalPlayerError(f"unsupported premium player action: {action}")

    output = _aura_m180_ui4_r3_r1_rc(port, command)
    session["playback_state"] = playback_state
    session["last_control_action"] = action
    session["last_control_at"] = _now()
    self._save_session(session)

    return {
        "schema": "aura.music-premium-control.v180",
        "action": action,
        "value": value,
        "playback_state": playback_state,
        "media_id": session.get("media_id"),
        "title": session.get("title"),
        "backend": session.get("backend"),
        "rc_port": port,
        "output": str(output or "")[-1000:],
        "filesystem_mutation_performed": False,
        "external_account_mutation_performed": False,
    }

def _aura_m180_ui4_r3_r1_status(self):
    data = _AURA_M180_UI4_R3_R1_OLD_STATUS(self)
    if not data.get("session_present"):
        return data
    try:
        if _AURA_M180_UI4_R3_R1_LIVE.exists():
            live = json.loads(
                _AURA_M180_UI4_R3_R1_LIVE.read_text(encoding="utf-8-sig")
            )
            if (
                str(live.get("monitor_id") or "")
                == str(data.get("premium_monitor_id") or "")
            ):
                data["premium_live"] = live
    except Exception:
        pass
    return data

ControlledLocalPlayer.launch = _aura_m180_ui4_r3_r1_launch
ControlledLocalPlayer.control = _aura_m180_ui4_r3_r1_control
ControlledLocalPlayer.status = _aura_m180_ui4_r3_r1_status

# AURA_M180_UI4_R3_R2_VLC_PREMIUM_PLAYER
import socket as _aura_m180_ui4_r3_socket
import threading as _aura_m180_ui4_r3_threading
import time as _aura_m180_ui4_r3_time
import uuid as _aura_m180_ui4_r3_uuid
import re as _aura_m180_ui4_r3_re
from pathlib import Path as _AuraM180Ui4R3Path

_AURA_M180_UI4_R3_OLD_LAUNCH = ControlledLocalPlayer.launch
_AURA_M180_UI4_R3_OLD_STATUS = ControlledLocalPlayer.status
_AURA_M180_UI4_R3_LIVE = (
    _AuraM180Ui4R3Path.home()
    / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2"
    / "dist" / "aura_music_player_live_v180.json"
)

def _aura_m180_ui4_r3_free_port():
    sock = _aura_m180_ui4_r3_socket.socket(
        _aura_m180_ui4_r3_socket.AF_INET,
        _aura_m180_ui4_r3_socket.SOCK_STREAM,
    )
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()

def _aura_m180_ui4_r3_rc(port, command, timeout=0.7):
    last = None
    for _ in range(6):
        sock = None
        try:
            sock = _aura_m180_ui4_r3_socket.create_connection(
                ("127.0.0.1", int(port)),
                timeout=timeout,
            )
            sock.settimeout(timeout)
            try:
                sock.recv(4096)
            except Exception:
                pass
            sock.sendall((str(command).strip() + "\n").encode("utf-8"))
            _aura_m180_ui4_r3_time.sleep(0.05)
            chunks = []
            while True:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
                    if len(b"".join(chunks)) > 16384:
                        break
                except Exception:
                    break
            return b"".join(chunks).decode("utf-8", errors="replace")
        except Exception as exc:
            last = exc
            _aura_m180_ui4_r3_time.sleep(0.18)
        finally:
            try:
                if sock:
                    sock.close()
            except Exception:
                pass
    raise LocalPlayerError(f"VLC RC unavailable: {last}")

def _aura_m180_ui4_r3_number(text):
    values = []
    for line in str(text or "").replace("\r", "\n").split("\n"):
        clean = line.strip().lstrip(">").strip()
        m = _aura_m180_ui4_r3_re.search(r"(-?\d+(?:\.\d+)?)\s*$", clean)
        if m:
            try:
                values.append(float(m.group(1)))
            except Exception:
                pass
    return values[-1] if values else None

def _aura_m180_ui4_r3_atomic_json(path, payload):
    path = _AuraM180Ui4R3Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)

def _aura_m180_ui4_r3_monitor(session_path, monitor_id, port, pid, media_id, title):
    failures = 0
    while True:
        try:
            session_file = _AuraM180Ui4R3Path(session_path)
            if not session_file.exists():
                break
            current = json.loads(session_file.read_text(encoding="utf-8-sig"))
            if str(current.get("premium_monitor_id") or "") != str(monitor_id):
                break

            t = _aura_m180_ui4_r3_number(
                _aura_m180_ui4_r3_rc(port, "get_time", timeout=0.45)
            )
            length = _aura_m180_ui4_r3_number(
                _aura_m180_ui4_r3_rc(port, "get_length", timeout=0.45)
            )
            playing = _aura_m180_ui4_r3_number(
                _aura_m180_ui4_r3_rc(port, "is_playing", timeout=0.45)
            )

            duration = max(0.0, float(length or 0.0))
            position = max(0.0, float(t or 0.0))
            percent = (
                max(0.0, min(100.0, position * 100.0 / duration))
                if duration > 0 else 0.0
            )
            payload = {
                "schema": "aura.music-premium-live.v180",
                "monitor_id": monitor_id,
                "media_id": media_id,
                "title": title,
                "pid": pid,
                "rc_port": int(port),
                "playing": bool(int(playing or 0)),
                "position_seconds": round(position, 3),
                "duration_seconds": round(duration, 3),
                "position_percent": round(percent, 3),
                "volume_percent": current.get("volume_percent", 80),
                "playback_state": current.get("playback_state", "playing"),
                "captured_at": _now(),
            }
            _aura_m180_ui4_r3_atomic_json(_AURA_M180_UI4_R3_LIVE, payload)
            failures = 0
        except Exception:
            failures += 1
            if failures >= 12:
                try:
                    _aura_m180_ui4_r3_atomic_json(
                        _AURA_M180_UI4_R3_LIVE,
                        {
                            "schema": "aura.music-premium-live.v180",
                            "monitor_id": monitor_id,
                            "media_id": media_id,
                            "title": title,
                            "pid": pid,
                            "playing": False,
                            "position_seconds": 0,
                            "duration_seconds": 0,
                            "position_percent": 0,
                            "playback_state": "ended",
                            "captured_at": _now(),
                        },
                    )
                except Exception:
                    pass
                break
        _aura_m180_ui4_r3_time.sleep(0.55)

def _aura_m180_ui4_r3_stop_previous(self):
    try:
        old = _AURA_M180_UI4_R3_OLD_STATUS(self)
    except Exception:
        return
    port = old.get("rc_port")
    if port:
        try:
            _aura_m180_ui4_r3_rc(int(port), "quit", timeout=0.35)
            return
        except Exception:
            pass
    pid = old.get("pid")
    if pid and str(old.get("backend") or "") == "vlc":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
        except Exception:
            pass

def _aura_m180_ui4_r3_launch(
    self,
    *,
    media_id="",
    query="",
    first=False,
    user_confirmed,
):
    if not user_confirmed:
        raise LocalPlayerConfirmationRequired("explicit user confirmation required")

    row = self._find_item(media_id=media_id, query=query, first=first)
    path = self._validate_path(row)

    test_mode = str(
        os.environ.get("AURA_M180_PLAYER_TEST_MODE") or ""
    ).strip().casefold() in {"1", "true", "yes"}

    if test_mode:
        return _AURA_M180_UI4_R3_OLD_LAUNCH(
            self,
            media_id=media_id,
            query=query,
            first=first,
            user_confirmed=user_confirmed,
        )

    vlc = self._vlc_path()
    if not vlc:
        return _AURA_M180_UI4_R3_OLD_LAUNCH(
            self,
            media_id=media_id,
            query=query,
            first=first,
            user_confirmed=user_confirmed,
        )

    _aura_m180_ui4_r3_stop_previous(self)
    port = _aura_m180_ui4_r3_free_port()
    monitor_id = "musicmon_" + _aura_m180_ui4_r3_uuid.uuid4().hex[:16]

    args = [
        vlc,
        "--no-one-instance",
        "--no-video-title-show",
        "--extraintf=rc",
        f"--rc-host=127.0.0.1:{port}",
        "--rc-quiet",
        "--play-and-exit",
    ]
    if str(row.get("media_type") or "").casefold() == "audio":
        args.insert(1, "--intf=dummy")
    args.append(str(path))

    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    session = {
        "schema": "aura.controlled-local-player.v180",
        "state": "launch_confirmed",
        "playback_state": "playing",
        "media_id": row.get("media_id"),
        "title": row.get("title"),
        "artist": row.get("artist"),
        "media_type": row.get("media_type"),
        "path": str(path),
        "backend": "vlc",
        "pid": int(proc.pid),
        "rc_port": int(port),
        "premium_control": True,
        "premium_monitor_id": monitor_id,
        "volume_percent": 80,
        "launched_at": _now(),
        "launch_succeeded": True,
        "explicit_user_confirmation": True,
        "test_mode": False,
        "filesystem_mutation_performed": False,
        "external_account_mutation_performed": False,
    }
    self._save_session(session)

    thread = _aura_m180_ui4_r3_threading.Thread(
        target=_aura_m180_ui4_r3_monitor,
        args=(
            str(self.session_path),
            monitor_id,
            port,
            int(proc.pid),
            str(row.get("media_id") or ""),
            str(row.get("title") or ""),
        ),
        name="AURA-Music-Premium-Monitor",
        daemon=True,
    )
    thread.start()
    return session

def _aura_m180_ui4_r3_control(self, action, value=None):
    session = _AURA_M180_UI4_R3_OLD_STATUS(self)
    if not session.get("session_present"):
        raise LocalPlayerError("no active local player session")
    if str(session.get("backend") or "") != "vlc" or not session.get("rc_port"):
        raise LocalPlayerError("premium player control requires VLC RC session")

    action = str(action or "").strip().casefold()
    port = int(session["rc_port"])
    command = ""
    playback_state = str(session.get("playback_state") or "")

    if action == "pause":
        command = "pause"
        playback_state = "paused"
    elif action in {"resume", "play"}:
        command = "play"
        playback_state = "playing"
    elif action == "stop":
        command = "stop"
        playback_state = "stopped"
    elif action == "quit":
        command = "quit"
        playback_state = "closed"
    elif action == "seek_percent":
        pct = max(0.0, min(100.0, float(value or 0)))
        length = _aura_m180_ui4_r3_number(
            _aura_m180_ui4_r3_rc(port, "get_length")
        )
        if not length or length <= 0:
            raise LocalPlayerError("media duration unavailable")
        seconds = int(round(float(length) * pct / 100.0))
        command = f"seek {seconds}"
        session["seek_percent"] = pct
    elif action == "volume_percent":
        pct = int(max(0, min(100, int(float(value or 0)))))
        # VLC RC volume uses 256 as nominal 100%.
        command = f"volume {int(round(256 * pct / 100.0))}"
        session["volume_percent"] = pct
    else:
        raise LocalPlayerError(f"unsupported premium player action: {action}")

    output = _aura_m180_ui4_r3_rc(port, command)
    session["playback_state"] = playback_state
    session["last_control_action"] = action
    session["last_control_at"] = _now()
    self._save_session(session)

    return {
        "schema": "aura.music-premium-control.v180",
        "action": action,
        "value": value,
        "playback_state": playback_state,
        "media_id": session.get("media_id"),
        "title": session.get("title"),
        "backend": session.get("backend"),
        "rc_port": port,
        "output": str(output or "")[-1000:],
        "filesystem_mutation_performed": False,
        "external_account_mutation_performed": False,
    }

def _aura_m180_ui4_r3_status(self):
    data = _AURA_M180_UI4_R3_OLD_STATUS(self)
    if not data.get("session_present"):
        return data
    try:
        if _AURA_M180_UI4_R3_LIVE.exists():
            live = json.loads(
                _AURA_M180_UI4_R3_LIVE.read_text(encoding="utf-8-sig")
            )
            if (
                str(live.get("monitor_id") or "")
                == str(data.get("premium_monitor_id") or "")
            ):
                data["premium_live"] = live
    except Exception:
        pass
    return data

ControlledLocalPlayer.launch = _aura_m180_ui4_r3_launch
ControlledLocalPlayer.control = _aura_m180_ui4_r3_control
ControlledLocalPlayer.status = _aura_m180_ui4_r3_status
