from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def session_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "AURA" / "ui" / "runtime" / "rc4_2_session.json"
    return Path.home() / "AppData" / "Local" / "AURA" / "ui" / "runtime" / "rc4_2_session.json"


def probe(timeout: float = 2.0) -> tuple[int, dict]:
    path = session_path()
    if not path.is_file():
        return 10, {
            "ok": False,
            "reason": "session_not_found",
            "session_path": str(path),
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return 11, {
            "ok": False,
            "reason": "session_invalid",
            "detail": type(exc).__name__,
        }

    try:
        port = int(data.get("port") or 0)
        token = str(data.get("token") or "").strip()
    except Exception:
        return 12, {"ok": False, "reason": "session_contract_invalid"}

    if not (1 <= port <= 65535) or len(token) < 24:
        return 12, {"ok": False, "reason": "session_contract_invalid"}

    url = (
        f"http://127.0.0.1:{port}/api/status"
        f"?token={urllib.parse.quote(token, safe='')}"
    )
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as response:
            raw = response.read(1024 * 1024)
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        return 13, {
            "ok": False,
            "reason": "http_error",
            "status": int(getattr(exc, "code", 0) or 0),
        }
    except Exception as exc:
        return 14, {
            "ok": False,
            "reason": "core_unreachable",
            "detail": type(exc).__name__,
        }

    if not bool(payload.get("ok")):
        return 15, {
            "ok": False,
            "reason": "status_not_ok",
            "status": payload,
        }

    return 0, {
        "ok": True,
        "session_path": str(path),
        "pid": int(data.get("pid") or 0),
        "port": port,
        "release": str(payload.get("release") or data.get("release") or ""),
        "interaction_ready": bool(payload.get("interaction_ready")),
        "voice_state": str(payload.get("voice_state") or ""),
        "core_service_bridge": bool(payload.get("core_service_bridge")),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    rc, info = probe(timeout=args.timeout)

    if rc == 0 and args.require_ready and not info.get("interaction_ready"):
        rc = 16
        info = {
            **info,
            "ok": False,
            "reason": "interaction_not_ready",
        }

    if not args.quiet:
        if args.json:
            print(json.dumps(info, ensure_ascii=False))
        elif rc == 0:
            print("[OK] AURA Core session reachable")
            print(f"     PID               : {info.get('pid')}")
            print(f"     Port              : {info.get('port')}")
            print(f"     Release           : {info.get('release')}")
            print(f"     Interaction ready : {info.get('interaction_ready')}")
            print(f"     Voice state       : {info.get('voice_state')}")
            print(f"     Service bridge    : {info.get('core_service_bridge')}")
        else:
            print(f"[OFFLINE] {info.get('reason', 'unknown')}")
            if info.get("detail"):
                print(f"          {info['detail']}")

    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
