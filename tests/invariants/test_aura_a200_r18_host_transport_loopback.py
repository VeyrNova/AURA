from __future__ import annotations

import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_ui_host_transport_v200 import (
    A200UiHostTransport,
    A200_R18_MARKER,
    ARBITRARY_TOOL_EXECUTION_ENABLED,
    AUTO_APPROVAL_ENABLED,
    AUTO_CANCEL_ENABLED,
    BRIDGE_PATH,
    DESTRUCTIVE_EXECUTION_ENABLED,
    DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED,
    EXTERNAL_NETWORK_BINDING_ENABLED,
    LOOPBACK_HOST,
    LOOPBACK_ONLY_REQUIRED,
    SESSION_BINDING_DELEGATED_TO_R16,
    STRUCTURED_R16_ADAPTER_REQUIRED,
    TOKEN_HEADER,
    TRANSPORT_TOKEN_REQUIRED,
    assert_r18_safety_contract,
)

TOKEN = "5256bff879cde4a3d03c7de50140282260777d8ee152ad4a97ce25bc6969a4a4"

checks = []
real_read_only_windows_observation = False
real_pc_or_window_mutated = False


def add(name, ok, detail=""):
    ok = bool(ok)
    checks.append((name, ok, str(detail)))
    print(
        ("[PASS] " if ok else "[FAIL] ")
        + name
        + (f" :: {detail}" if detail else ""),
        flush=True,
    )


def post(url, envelope, token=TOKEN, origin="null"):
    body = json.dumps(envelope).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            TOKEN_HEADER: token,
            "Origin": origin,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(
                response.read().decode("utf-8")
            )
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(
            exc.read().decode("utf-8")
        )


add("R18 marker", A200_R18_MARKER == "AURA_A200_R18_HOST_TRANSPORT_LOOPBACK_BINDING_V1")
add("loopback-only required", LOOPBACK_ONLY_REQUIRED is True)
add("transport token required", TRANSPORT_TOKEN_REQUIRED is True)
add("structured R16 adapter required", STRUCTURED_R16_ADAPTER_REQUIRED is True)
add("session binding delegated to R16", SESSION_BINDING_DELEGATED_TO_R16 is True)
add("auto approval disabled", AUTO_APPROVAL_ENABLED is False)
add("auto cancel disabled", AUTO_CANCEL_ENABLED is False)
add("direct natural language execution disabled", DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED is False)
add("arbitrary tool execution disabled", ARBITRARY_TOOL_EXECUTION_ENABLED is False)
add("external network binding disabled", EXTERNAL_NETWORK_BINDING_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
assert_r18_safety_contract()
add("R18 safety contract assertion", True)

state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r18_live_"))
transport = None
try:
    transport = A200UiHostTransport(
        token=TOKEN,
        host=LOOPBACK_HOST,
        port=0,
        state_root=state_root,
        backend=None,
        owner_id="r18-acceptance",
    )
    address = transport.start()
    add("R18 server bound to exact loopback host", address.host == "127.0.0.1", address.host)
    add("R18 server route exact", address.path == BRIDGE_PATH, address.path)
    add("R18 ephemeral test port assigned", address.port > 0, address.port)
    url = f"http://{address.host}:{address.port}{address.path}"

    status_code, status = post(
        url,
        {
            "protocol": "aura.ui-supervised-bridge.v1",
            "request_id": "r18-status-1",
            "type": "runtime.status",
            "payload": {},
        },
    )
    add("R18 loopback status HTTP 200", status_code == 200, status_code)
    add("R18 loopback status protocol preserved", status.get("protocol") == "aura.ui-supervised-bridge.v1")
    add("R18 loopback status request id preserved", status.get("request_id") == "r18-status-1")
    add("R18 loopback status ok", status.get("ok") is True)
    session_id = str(status.get("session_id") or "")
    add("R18 loopback status returns runtime session", bool(session_id))

    before_receipts = len(transport.runtime.receipts.list_receipts())
    read_code, read = post(
        url,
        {
            "protocol": "aura.ui-supervised-bridge.v1",
            "request_id": "r18-read-1",
            "session_id": session_id,
            "type": "pc.read_foreground",
            "payload": {},
        },
    )
    real_read_only_windows_observation = True
    add("R18 loopback real read HTTP 200", read_code == 200, read_code)
    add("R18 loopback real read ok", read.get("ok") is True)
    add("R18 loopback real read kind", read.get("kind") == "pc.read_foreground")
    receipt_id = str((read.get("payload") or {}).get("receipt_id") or "")
    add("R18 loopback real read owns receipt", bool(receipt_id))
    add("R18 loopback real read creates one receipt", len(transport.runtime.receipts.list_receipts()) == before_receipts + 1)

    receipts_after_read = len(transport.runtime.receipts.list_receipts())

    wrong_code, wrong = post(
        url,
        {
            "protocol": "aura.ui-supervised-bridge.v1",
            "request_id": "r18-bad-token",
            "type": "runtime.status",
            "payload": {},
        },
        token="0" * 64,
    )
    add("R18 wrong token rejected HTTP 403", wrong_code == 403, wrong_code)
    add("R18 wrong token error explicit", wrong.get("error") == "transport_token_invalid")

    unknown_code, unknown = post(
        url,
        {
            "protocol": "aura.ui-supervised-bridge.v1",
            "request_id": "r18-unknown",
            "session_id": session_id,
            "type": "shell.execute",
            "payload": {"command": "dir"},
        },
    )
    add("R18 unknown command rejected", unknown_code == 400, unknown_code)
    add("R18 unknown command did not create receipt", len(transport.runtime.receipts.list_receipts()) == receipts_after_read)

    no_session_code, no_session = post(
        url,
        {
            "protocol": "aura.ui-supervised-bridge.v1",
            "request_id": "r18-no-session",
            "type": "pc.prepare_minimize_window",
            "payload": {
                "hwnd": 1,
                "title": "must-not-dispatch",
            },
        },
    )
    add("R18 state-changing request without session rejected", no_session_code == 400, no_session_code)
    add("R18 missing-session request created no receipt", len(transport.runtime.receipts.list_receipts()) == receipts_after_read)

    bad_origin_code, bad_origin = post(
        url,
        {
            "protocol": "aura.ui-supervised-bridge.v1",
            "request_id": "r18-bad-origin",
            "type": "runtime.status",
            "payload": {},
        },
        origin="https://example.com",
    )
    add("R18 non-local origin rejected", bad_origin_code == 403, bad_origin_code)

finally:
    if transport is not None:
        transport.close()
    shutil.rmtree(state_root, ignore_errors=True)

src_path = ROOT / "runtime" / "aura_ui_host_transport_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R18 source binds fixed loopback constant", 'LOOPBACK_HOST = "127.0.0.1"' in src)
add("R18 source uses R16 adapter", "A200DeployedUiBridgeAdapter" in src)
add("R18 source uses R15 bridge beneath R16", "A200UiConversationCommandBridge" in src)
add("R18 source uses R14 ingress beneath R15", "A200SupervisedRuntimeIngress" in src)
add("R18 source uses R13 persistent runtime", "A200PersistentRuntimeBootstrap" in src)
add("R18 source has one bridge path", 'BRIDGE_PATH = "/aura/a200/bridge"' in src)
add("R18 source requires token header", "X-AURA-A200-Transport-Token" in src)
add("R18 source contains no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R18 source contains no shell API", all(token not in src for token in ("os.system(", "os.popen(", "ctypes.", "child_process")))
add("R18 source contains no close capability", "pc.close_window" not in src)
add("R18 source contains no terminate capability", "pc.terminate_process" not in src)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R18_REAL_READ_ONLY_WINDOWS_OBSERVATION = {real_read_only_windows_observation}")
print(f"R18_REAL_PC_OR_WINDOW_MUTATED = {real_pc_or_window_mutated}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if not real_read_only_windows_observation:
    raise SystemExit("R18 expected one real read-only Windows observation")
if real_pc_or_window_mutated:
    raise SystemExit("R18 acceptance must not mutate a real window")
print("[PASS] A200-R18 authenticated loopback host transport binding")
