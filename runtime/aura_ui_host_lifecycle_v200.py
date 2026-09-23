"""AURA A200-R19 host lifecycle.

Lifecycle-only companion over the certified R18 loopback host transport.
No mission/policy/receipt/integration authority is duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import msvcrt
import os
from pathlib import Path
import time

from runtime.aura_ui_host_transport_v200 import (
    A200UiHostTransport,
    DEFAULT_PORT,
    LOOPBACK_HOST,
    TOKEN_FILE,
    load_transport_token,
)

A200_R19_MARKER = "AURA_A200_R19_HOST_LIFECYCLE_AUTOSTART_LIVE_HANDSHAKE_V1"

DEFAULT_STATE_ROOT = Path(r"C:\AURA GPT version\data\a200_runtime")

SINGLE_HOST_OWNER_REQUIRED = True
AUTO_START_REGISTRATION_REQUIRED = True
LOOPBACK_ONLY_REQUIRED = True
R18_TRANSPORT_AUTHORITY_REQUIRED = True
AUTO_APPROVAL_ENABLED = False
AUTO_CANCEL_ENABLED = False
AUTONOMOUS_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
SHELL_EXECUTION_ENABLED = False
LOCK_OPEN_FAILURE_NORMALIZED = True
NODE_FETCH_CONTENT_LENGTH_REQUIRED = True


class UiHostLifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class LifecycleSnapshot:
    state: str
    owner_pid: int
    host: str
    port: int
    started_at: float
    session_id: str | None


class _ProcessFileLock:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = None

    def acquire(self) -> None:
        if self._handle is not None:
            return
        try:
            handle = self.path.open("a+b")
        except OSError as exc:
            raise UiHostLifecycleError(
                "another AURA A200 UI host lifecycle owner is active"
            ) from exc

        try:
            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise UiHostLifecycleError(
                "another AURA A200 UI host lifecycle owner is active"
            ) from exc

        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            handle.close()
            self._handle = None


class A200UiHostLifecycle:
    def __init__(
        self,
        *,
        state_root: str | Path = DEFAULT_STATE_ROOT,
        token: str | None = None,
        port: int = DEFAULT_PORT,
        host: str = LOOPBACK_HOST,
        owner_id: str = "aura-r19-ui-host-lifecycle",
    ) -> None:
        if host != LOOPBACK_HOST:
            raise UiHostLifecycleError("R19 may bind only certified loopback")
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.state_root / "r19_ui_host_lifecycle.lock"
        self.status_file = self.state_root / "r19_ui_host_lifecycle_status.json"
        self._lock = _ProcessFileLock(self.lock_file)
        self._token = token
        self._port = int(port)
        self._host = host
        self._owner_id = owner_id
        self._transport = None
        self._started_at = 0.0

    def _write_status(self, state: str) -> None:
        session_id = None
        if self._transport is not None:
            session_id = self._transport.runtime.session_id
        payload = {
            "schema": "aura.a200.r19.host-lifecycle-status.v1",
            "state": state,
            "owner_pid": os.getpid(),
            "host": self._host,
            "port": self._port,
            "started_at": self._started_at,
            "session_id": session_id,
            "runtime_chain": "R19->R18->R16->R15->R14->R13->MissionEngine",
            "auto_approval_enabled": False,
            "auto_cancel_enabled": False,
            "destructive_execution_enabled": False,
        }
        tmp = self.status_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.status_file)

    def start(self) -> LifecycleSnapshot:
        if self._transport is not None:
            return self.snapshot()
        self._lock.acquire()
        try:
            token = self._token or load_transport_token(TOKEN_FILE)
            transport = A200UiHostTransport(
                token=token,
                host=self._host,
                port=self._port,
                state_root=self.state_root,
                backend=None,
                owner_id=self._owner_id,
            )
            address = transport.start()
            self._transport = transport
            self._port = int(address.port)
            self._started_at = time.time()
            self._write_status("running")
            return self.snapshot()
        except Exception:
            self._lock.release()
            raise

    def snapshot(self) -> LifecycleSnapshot:
        return LifecycleSnapshot(
            state="running" if self._transport is not None else "stopped",
            owner_pid=os.getpid(),
            host=self._host,
            port=self._port,
            started_at=self._started_at,
            session_id=None if self._transport is None else self._transport.runtime.session_id,
        )

    def close(self) -> None:
        try:
            if self._transport is not None:
                self._transport.close()
                self._transport = None
                self._write_status("stopped")
        finally:
            self._lock.release()

    def serve_forever(self) -> None:
        self._lock.acquire()
        try:
            token = self._token or load_transport_token(TOKEN_FILE)
            transport = A200UiHostTransport(
                token=token,
                host=self._host,
                port=self._port,
                state_root=self.state_root,
                backend=None,
                owner_id=self._owner_id,
            )
            self._transport = transport
            self._started_at = time.time()
            self._write_status("running")
            transport.serve_forever()
        finally:
            self._transport = None
            try:
                self._write_status("stopped")
            finally:
                self._lock.release()


def assert_r19_safety_contract() -> None:
    if not SINGLE_HOST_OWNER_REQUIRED:
        raise RuntimeError("single host owner is mandatory")
    if not AUTO_START_REGISTRATION_REQUIRED:
        raise RuntimeError("autostart registration is mandatory")
    if not LOOPBACK_ONLY_REQUIRED or not R18_TRANSPORT_AUTHORITY_REQUIRED:
        raise RuntimeError("loopback/R18 authority contract violated")
    if AUTO_APPROVAL_ENABLED or AUTO_CANCEL_ENABLED:
        raise RuntimeError("automatic approval/cancel must remain disabled")
    if AUTONOMOUS_MUTATION_ENABLED:
        raise RuntimeError("autonomous mutation must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED or SHELL_EXECUTION_ENABLED:
        raise RuntimeError("destructive/shell execution must remain disabled")


def main() -> int:
    assert_r19_safety_contract()
    lifecycle = A200UiHostLifecycle()
    try:
        lifecycle.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
