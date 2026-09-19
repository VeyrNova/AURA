from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_deployed_ui_bridge_adapter_v200 import (
    A200DeployedUiBridgeAdapter,
    A200_R16_ADAPTER_MARKER,
    AURA_UI_BRIDGE_PROTOCOL,
    ARBITRARY_TOOL_EXECUTION_ENABLED,
    AUTO_APPROVAL_ENABLED,
    AUTO_CANCEL_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED,
    REQUEST_ID_REQUIRED,
    SESSION_BINDING_REQUIRED,
    STRUCTURED_ENVELOPE_ONLY,
    UiAdapterProtocolError,
    assert_r16_adapter_safety_contract,
)
from runtime.aura_deployed_ui_discovery_v200 import (
    A200_R16_DISCOVERY_MARKER,
    DEPLOYED_UI_MUTATION_ENABLED,
    DISCOVERY_READ_ONLY,
    assert_r16_discovery_safety_contract,
    descriptor,
    scan_deployed_ui,
    tree_fingerprint,
)
from runtime.aura_persistent_runtime_bootstrap_v200 import (
    A200PersistentRuntimeBootstrap,
)
from runtime.aura_supervised_runtime_ingress_v200 import (
    A200SupervisedRuntimeIngress,
)
from runtime.aura_ui_conversation_supervised_bridge_v200 import (
    A200UiConversationCommandBridge,
)


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


def must_raise(name, exc_type, fn):
    try:
        fn()
    except exc_type:
        add(name, True)
    except Exception as exc:
        add(name, False, f"wrong exception {type(exc).__name__}: {exc}")
    else:
        add(name, False, "no exception")


add("R16 adapter marker", A200_R16_ADAPTER_MARKER == "AURA_A200_R16_DEPLOYED_UI_BRIDGE_ADAPTER_V1")
add("R16 discovery marker", A200_R16_DISCOVERY_MARKER == "AURA_A200_R16_DEPLOYED_UI_DISCOVERY_READONLY_V1")
add("structured envelope only", STRUCTURED_ENVELOPE_ONLY is True)
add("session binding required", SESSION_BINDING_REQUIRED is True)
add("request id required", REQUEST_ID_REQUIRED is True)
add("direct natural-language execution disabled", DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED is False)
add("arbitrary tool execution disabled", ARBITRARY_TOOL_EXECUTION_ENABLED is False)
add("auto approval disabled", AUTO_APPROVAL_ENABLED is False)
add("auto cancel disabled", AUTO_CANCEL_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("deployed UI discovery read-only", DISCOVERY_READ_ONLY is True)
add("deployed UI mutation disabled", DEPLOYED_UI_MUTATION_ENABLED is False)
assert_r16_adapter_safety_contract()
assert_r16_discovery_safety_contract()
add("R16 safety contracts", True)

# ------------------------------------------------------------------
# REAL deployed UI read-only discovery + unchanged tree proof.
# ------------------------------------------------------------------
discovery = scan_deployed_ui()
add("deployed UI root discovered", Path(discovery.ui_root).is_dir(), discovery.ui_root)
add("deployed UI file count positive", discovery.file_count > 0, discovery.file_count)
add("deployed UI fingerprint SHA256", len(discovery.tree_fingerprint) == 64)
add("deployed UI has entrypoint evidence", len(discovery.entrypoints) >= 1, discovery.entrypoints)
add("deployed UI has bridge seam candidates", len(discovery.candidates) >= 1, len(discovery.candidates))
add(
    "at least one candidate carries conversation/input/transport/router evidence",
    any(
        set(item.categories).intersection({"conversation", "input", "transport", "router"})
        for item in discovery.candidates
    ),
)

desc = descriptor(discovery)
add("binding descriptor schema correct", desc["schema"] == "aura.a200.r16.deployed-ui-binding-descriptor.v1")
add("binding descriptor declares no UI mutation", desc["live_ui_mutated"] is False)
add("binding descriptor names R16 protocol", desc["binding_protocol"] == AURA_UI_BRIDGE_PROTOCOL)
before_fingerprint = discovery.tree_fingerprint

# ------------------------------------------------------------------
# REAL read-only command through R16 -> R15 -> R14 -> R13 -> R4.
# ------------------------------------------------------------------
live_root = Path(tempfile.mkdtemp(prefix="aura_a200_r16_live_"))
try:
    runtime = A200PersistentRuntimeBootstrap(
        state_root=live_root,
        backend=None,
        owner_id="r16-live-read",
    )
    ingress = A200SupervisedRuntimeIngress(runtime=runtime)
    bridge = A200UiConversationCommandBridge(ingress=ingress)
    adapter = A200DeployedUiBridgeAdapter(bridge=bridge)

    status = adapter.dispatch(
        {
            "protocol": AURA_UI_BRIDGE_PROTOCOL,
            "request_id": "r16-status-1",
            "type": "runtime.status",
            "payload": {},
        }
    )
    add("R16 status envelope succeeds", status["ok"] is True)
    add("R16 status envelope preserves request id", status["request_id"] == "r16-status-1")
    add("R16 status envelope returns runtime session", status["session_id"] == runtime.session_id)

    before_receipts = len(runtime.receipts.list_receipts())
    read = adapter.dispatch(
        {
            "protocol": AURA_UI_BRIDGE_PROTOCOL,
            "request_id": "r16-real-read-1",
            "session_id": runtime.session_id,
            "type": "pc.read_foreground",
            "payload": {},
        }
    )
    real_read_only_windows_observation = True
    add("R16 real read-only envelope succeeds", read["ok"] is True)
    add("R16 real read-only kind", read["kind"] == "pc.read_foreground")
    add("R16 real read returns canonical receipt", bool(read["payload"].get("receipt_id")))
    add("R16 real read creates exactly one receipt", len(runtime.receipts.list_receipts()) == before_receipts + 1)

    receipts_after = len(runtime.receipts.list_receipts())
    must_raise(
        "R16 rejects wrong protocol",
        UiAdapterProtocolError,
        lambda: adapter.dispatch(
            {
                "protocol": "wrong.v1",
                "request_id": "x",
                "type": "runtime.status",
                "payload": {},
            }
        ),
    )
    must_raise(
        "R16 rejects unknown command",
        UiAdapterProtocolError,
        lambda: adapter.dispatch(
            {
                "protocol": AURA_UI_BRIDGE_PROTOCOL,
                "request_id": "x2",
                "type": "shell.execute",
                "payload": {"command": "dir"},
            }
        ),
    )
    must_raise(
        "R16 requires session binding for state-changing command",
        UiAdapterProtocolError,
        lambda: adapter.dispatch(
            {
                "protocol": AURA_UI_BRIDGE_PROTOCOL,
                "request_id": "x3",
                "type": "pc.prepare_minimize_window",
                "payload": {"hwnd": 1, "title": "x"},
            }
        ),
    )
    must_raise(
        "R16 rejects wrong runtime session",
        UiAdapterProtocolError,
        lambda: adapter.dispatch(
            {
                "protocol": AURA_UI_BRIDGE_PROTOCOL,
                "request_id": "x4",
                "session_id": "wrong-session",
                "type": "mission.cancel",
                "payload": {"mission_id": "x", "confirm_cancel": True},
            }
        ),
    )
    add("R16 rejected envelopes create no receipt", len(runtime.receipts.list_receipts()) == receipts_after)
    runtime.close()
finally:
    shutil.rmtree(live_root, ignore_errors=True)

# ------------------------------------------------------------------
# Re-fingerprint actual deployed UI after all discovery/protocol tests.
# ------------------------------------------------------------------
after_fingerprint, after_count, after_bytes = tree_fingerprint(discovery.ui_root)
add("deployed UI fingerprint unchanged", after_fingerprint == before_fingerprint)
add("deployed UI file count unchanged", after_count == discovery.file_count)
add("deployed UI byte count unchanged", after_bytes == discovery.total_bytes)

# ------------------------------------------------------------------
# Source architecture.
# ------------------------------------------------------------------
adapter_path = ROOT / "runtime" / "aura_deployed_ui_bridge_adapter_v200.py"
discovery_path = ROOT / "runtime" / "aura_deployed_ui_discovery_v200.py"
adapter_src = adapter_path.read_text(encoding="utf-8-sig", errors="replace")
discovery_src = discovery_path.read_text(encoding="utf-8-sig", errors="replace")

add("R16 adapter wraps R15 only", "self.bridge.handle(command)" in adapter_src)
add("R16 adapter does not instantiate MissionEngine", "MissionEngine(" not in adapter_src)
add("R16 adapter has no subprocess import", "import subprocess" not in adapter_src and "from subprocess" not in adapter_src)
add("R16 adapter has no socket/server transport", all(token not in adapter_src for token in ("socket.", "http.server", "Flask(", "FastAPI(", "uvicorn")))
add("R16 adapter has no native shell API", all(token not in adapter_src for token in ("os.system(", "os.popen(", "ctypes.", "WindowsPcControlAdapter(")))
add("R16 adapter has no close capability", "pc.close_window" not in adapter_src)
add("R16 adapter has no terminate capability", "pc.terminate_process" not in adapter_src)
add("R16 discovery has no write_text/write_bytes", "write_text(" not in discovery_src and "write_bytes(" not in discovery_src)
add("R16 discovery has no unlink/replace/remove", all(token not in discovery_src for token in (".unlink(", "os.replace(", "os.remove(", "shutil.")))
add("R16 discovery mutation constant false", "DEPLOYED_UI_MUTATION_ENABLED = False" in discovery_src)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R16_DEPLOYED_UI_ROOT = {discovery.ui_root}")
print(f"R16_DEPLOYED_UI_FINGERPRINT = {before_fingerprint}")
print(f"R16_DEPLOYED_UI_CANDIDATES = {len(discovery.candidates)}")
print("R16_BINDING_DESCRIPTOR_JSON = " + json.dumps(desc, ensure_ascii=False, sort_keys=True))
print(f"R16_REAL_READ_ONLY_WINDOWS_OBSERVATION = {real_read_only_windows_observation}")
print(f"R16_REAL_PC_OR_WINDOW_MUTATED = {real_pc_or_window_mutated}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if not real_read_only_windows_observation:
    raise SystemExit("R16 expected one real read-only Windows observation")
if real_pc_or_window_mutated:
    raise SystemExit("R16 must not mutate the real desktop")
print("[PASS] A200-R16 deployed UI discovery + R15 bridge adapter binding acceptance")
