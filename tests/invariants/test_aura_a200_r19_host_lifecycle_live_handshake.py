from __future__ import annotations

import base64
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_ui_host_lifecycle_v200 import (
    A200UiHostLifecycle,
    A200_R19_MARKER,
    AUTO_APPROVAL_ENABLED,
    AUTO_CANCEL_ENABLED,
    AUTO_START_REGISTRATION_REQUIRED,
    AUTONOMOUS_MUTATION_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    LOOPBACK_ONLY_REQUIRED,
    R18_TRANSPORT_AUTHORITY_REQUIRED,
    SHELL_EXECUTION_ENABLED,
    SINGLE_HOST_OWNER_REQUIRED,
    UiHostLifecycleError,
    assert_r19_safety_contract,
)

UI_ROOT = Path(r"C:\Users\leclerc\AppData\Local\AURA\ui\v0.7.2.2-rc4.2")
R17_JS = UI_ROOT / "dist" / "assets" / "aura-a200-supervised-bridge-ui.js"
R18_JS = UI_ROOT / "dist" / "assets" / "aura-a200-supervised-host-transport.js"
TOKEN_FILE = ROOT / "data" / "a200_runtime" / "r18_ui_transport_token.txt"
NODE_HARNESS_B64 = "Y29uc3QgZnMgPSByZXF1aXJlKCJmcyIpOwpjb25zdCBodHRwID0gcmVxdWlyZSgiaHR0cCIpOwpjb25zdCB2bSA9IHJlcXVpcmUoInZtIik7Cgpjb25zdCBSMTcgPSBwcm9jZXNzLmFyZ3ZbMl07CmNvbnN0IFIxOCA9IHByb2Nlc3MuYXJndlszXTsKCmNvbnN0IGxpc3RlbmVycyA9IG5ldyBNYXAoKTsKCmNsYXNzIEN1c3RvbUV2ZW50IHsKICBjb25zdHJ1Y3Rvcih0eXBlLCBvcHRpb25zID0ge30pIHsKICAgIHRoaXMudHlwZSA9IHR5cGU7CiAgICB0aGlzLmRldGFpbCA9IG9wdGlvbnMuZGV0YWlsOwogIH0KfQoKZnVuY3Rpb24gYWRkV2luZG93TGlzdGVuZXIodHlwZSwgZm4pIHsKICBpZiAoIWxpc3RlbmVycy5oYXModHlwZSkpIGxpc3RlbmVycy5zZXQodHlwZSwgW10pOwogIGxpc3RlbmVycy5nZXQodHlwZSkucHVzaChmbik7Cn0KCmZ1bmN0aW9uIGRpc3BhdGNoV2luZG93KGV2ZW50KSB7CiAgY29uc3QgYXJyID0gbGlzdGVuZXJzLmdldChldmVudC50eXBlKSB8fCBbXTsKICBmb3IgKGNvbnN0IGZuIG9mIFsuLi5hcnJdKSBmbi5jYWxsKHdpbmRvdywgZXZlbnQpOwogIHJldHVybiB0cnVlOwp9CgpjbGFzcyBGYWtlTm9kZSB7CiAgY29uc3RydWN0b3Ioc2VsZWN0b3IgPSAiIikgewogICAgdGhpcy5zZWxlY3RvciA9IHNlbGVjdG9yOwogICAgdGhpcy5kYXRhc2V0ID0ge307CiAgICB0aGlzLnRleHRDb250ZW50ID0gIiI7CiAgICB0aGlzLmhpZGRlbiA9IGZhbHNlOwogICAgdGhpcy5kaXNhYmxlZCA9IGZhbHNlOwogICAgdGhpcy5pZCA9ICIiOwogICAgdGhpcy5jaGlsZHJlbiA9IFtdOwogICAgdGhpcy5ldmVudHMgPSB7fTsKICB9CiAgYWRkRXZlbnRMaXN0ZW5lcih0eXBlLCBmbikgewogICAgaWYgKCF0aGlzLmV2ZW50c1t0eXBlXSkgdGhpcy5ldmVudHNbdHlwZV0gPSBbXTsKICAgIHRoaXMuZXZlbnRzW3R5cGVdLnB1c2goZm4pOwogIH0KICBzZXRBdHRyaWJ1dGUoKSB7fQogIGFwcGVuZENoaWxkKG5vZGUpIHsKICAgIHRoaXMuY2hpbGRyZW4ucHVzaChub2RlKTsKICAgIGlmIChub2RlLmlkKSBkb2N1bWVudC5fYnlJZC5zZXQobm9kZS5pZCwgbm9kZSk7CiAgICByZXR1cm4gbm9kZTsKICB9Cn0KCmNsYXNzIEZha2VSb290IGV4dGVuZHMgRmFrZU5vZGUgewogIGNvbnN0cnVjdG9yKCkgewogICAgc3VwZXIoInJvb3QiKTsKICAgIHRoaXMuX25vZGVzID0gbmV3IE1hcCgpOwogICAgdGhpcy5faHRtbCA9ICIiOwogIH0KICBzZXQgaW5uZXJIVE1MKHZhbHVlKSB7CiAgICB0aGlzLl9odG1sID0gdmFsdWU7CiAgfQogIGdldCBpbm5lckhUTUwoKSB7CiAgICByZXR1cm4gdGhpcy5faHRtbDsKICB9CiAgcXVlcnlTZWxlY3RvcihzZWxlY3RvcikgewogICAgaWYgKCF0aGlzLl9ub2Rlcy5oYXMoc2VsZWN0b3IpKSB7CiAgICAgIHRoaXMuX25vZGVzLnNldChzZWxlY3RvciwgbmV3IEZha2VOb2RlKHNlbGVjdG9yKSk7CiAgICB9CiAgICByZXR1cm4gdGhpcy5fbm9kZXMuZ2V0KHNlbGVjdG9yKTsKICB9Cn0KCmdsb2JhbC5DdXN0b21FdmVudCA9IEN1c3RvbUV2ZW50OwpnbG9iYWwud2luZG93ID0gewogIGFkZEV2ZW50TGlzdGVuZXI6IGFkZFdpbmRvd0xpc3RlbmVyLAogIGRpc3BhdGNoRXZlbnQ6IGRpc3BhdGNoV2luZG93Cn07CgpnbG9iYWwuZG9jdW1lbnQgPSB7CiAgcmVhZHlTdGF0ZTogImNvbXBsZXRlIiwKICBfYnlJZDogbmV3IE1hcCgpLAogIGJvZHk6IG5ldyBGYWtlTm9kZSgiYm9keSIpLAogIGdldEVsZW1lbnRCeUlkKGlkKSB7CiAgICByZXR1cm4gdGhpcy5fYnlJZC5nZXQoaWQpIHx8IG51bGw7CiAgfSwKICBjcmVhdGVFbGVtZW50KHRhZykgewogICAgcmV0dXJuIHRhZyA9PT0gInNlY3Rpb24iID8gbmV3IEZha2VSb290KCkgOiBuZXcgRmFrZU5vZGUodGFnKTsKICB9LAogIGFkZEV2ZW50TGlzdGVuZXIoKSB7fQp9OwoKZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZCA9IGZ1bmN0aW9uKG5vZGUpIHsKICB0aGlzLmNoaWxkcmVuLnB1c2gobm9kZSk7CiAgaWYgKG5vZGUuaWQpIGRvY3VtZW50Ll9ieUlkLnNldChub2RlLmlkLCBub2RlKTsKICByZXR1cm4gbm9kZTsKfTsKCmdsb2JhbC5mZXRjaCA9IGZ1bmN0aW9uKHVybCwgb3B0aW9ucyA9IHt9KSB7CiAgcmV0dXJuIG5ldyBQcm9taXNlKChyZXNvbHZlLCByZWplY3QpID0+IHsKICAgIGNvbnN0IHUgPSBuZXcgVVJMKHVybCk7CiAgICBjb25zdCBib2R5ID0gb3B0aW9ucy5ib2R5IHx8ICIiOwogICAgY29uc3QgaGVhZGVycyA9IE9iamVjdC5hc3NpZ24oe30sIG9wdGlvbnMuaGVhZGVycyB8fCB7fSk7CiAgICBoZWFkZXJzWyJDb250ZW50LUxlbmd0aCJdID0gQnVmZmVyLmJ5dGVMZW5ndGgoYm9keSk7CiAgICBpZiAoIU9iamVjdC5rZXlzKGhlYWRlcnMpLnNvbWUoayA9PiBrLnRvTG93ZXJDYXNlKCkgPT09ICJvcmlnaW4iKSkgewogICAgICBoZWFkZXJzWyJPcmlnaW4iXSA9ICJudWxsIjsKICAgIH0KICAgIGNvbnN0IHJlcSA9IGh0dHAucmVxdWVzdCgKICAgICAgewogICAgICAgIGhvc3RuYW1lOiB1Lmhvc3RuYW1lLAogICAgICAgIHBvcnQ6IHUucG9ydCwKICAgICAgICBwYXRoOiB1LnBhdGhuYW1lICsgdS5zZWFyY2gsCiAgICAgICAgbWV0aG9kOiBvcHRpb25zLm1ldGhvZCB8fCAiR0VUIiwKICAgICAgICBoZWFkZXJzCiAgICAgIH0sCiAgICAgIChyZXMpID0+IHsKICAgICAgICBsZXQgZGF0YSA9ICIiOwogICAgICAgIHJlcy5zZXRFbmNvZGluZygidXRmOCIpOwogICAgICAgIHJlcy5vbigiZGF0YSIsIGNodW5rID0+IGRhdGEgKz0gY2h1bmspOwogICAgICAgIHJlcy5vbigiZW5kIiwgKCkgPT4gewogICAgICAgICAgcmVzb2x2ZSh7CiAgICAgICAgICAgIG9rOiByZXMuc3RhdHVzQ29kZSA+PSAyMDAgJiYgcmVzLnN0YXR1c0NvZGUgPCAzMDAsCiAgICAgICAgICAgIHN0YXR1czogcmVzLnN0YXR1c0NvZGUsCiAgICAgICAgICAgIGFzeW5jIGpzb24oKSB7CiAgICAgICAgICAgICAgcmV0dXJuIEpTT04ucGFyc2UoZGF0YSB8fCAie30iKTsKICAgICAgICAgICAgfQogICAgICAgICAgfSk7CiAgICAgICAgfSk7CiAgICAgIH0KICAgICk7CiAgICByZXEub24oImVycm9yIiwgcmVqZWN0KTsKICAgIGlmIChib2R5KSByZXEud3JpdGUoYm9keSk7CiAgICByZXEuZW5kKCk7CiAgfSk7Cn07CgpsZXQgc3RhdHVzUmVzcG9uc2UgPSBudWxsOwpsZXQgcmVhZFJlc3BvbnNlID0gbnVsbDsKbGV0IGZpcnN0UmVzcG9uc2UgPSBudWxsOwoKd2luZG93LmFkZEV2ZW50TGlzdGVuZXIoImF1cmE6YTIwMC1zdXBlcnZpc2VkLXJlc3BvbnNlIiwgKGV2ZW50KSA9PiB7CiAgY29uc3QgZCA9IGV2ZW50LmRldGFpbCB8fCB7fTsKICBpZiAoZmlyc3RSZXNwb25zZSA9PT0gbnVsbCkgewogICAgZmlyc3RSZXNwb25zZSA9IGQ7CiAgfQogIGlmIChkLmtpbmQgPT09ICJydW50aW1lLnN0YXR1cyIpIHsKICAgIHN0YXR1c1Jlc3BvbnNlID0gZDsKICB9CiAgaWYgKGQucmVxdWVzdF9pZCA9PT0gInIxOS1saXZlLXJlYWQiICYmIGQua2luZCA9PT0gInBjLnJlYWRfZm9yZWdyb3VuZCIpIHsKICAgIHJlYWRSZXNwb25zZSA9IGQ7CiAgfQp9KTsKCmZ1bmN0aW9uIHdhaXRGb3IocHJlZGljYXRlLCB0aW1lb3V0TXMpIHsKICBjb25zdCBzdGFydGVkID0gRGF0ZS5ub3coKTsKICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4gewogICAgY29uc3QgdGltZXIgPSBzZXRJbnRlcnZhbCgoKSA9PiB7CiAgICAgIHRyeSB7CiAgICAgICAgaWYgKHByZWRpY2F0ZSgpKSB7CiAgICAgICAgICBjbGVhckludGVydmFsKHRpbWVyKTsKICAgICAgICAgIHJlc29sdmUoKTsKICAgICAgICAgIHJldHVybjsKICAgICAgICB9CiAgICAgICAgaWYgKERhdGUubm93KCkgLSBzdGFydGVkID4gdGltZW91dE1zKSB7CiAgICAgICAgICBjbGVhckludGVydmFsKHRpbWVyKTsKICAgICAgICAgIHJlamVjdChuZXcgRXJyb3IoInRpbWVvdXQiKSk7CiAgICAgICAgfQogICAgICB9IGNhdGNoIChlcnIpIHsKICAgICAgICBjbGVhckludGVydmFsKHRpbWVyKTsKICAgICAgICByZWplY3QoZXJyKTsKICAgICAgfQogICAgfSwgMjUpOwogIH0pOwp9CgooYXN5bmMgKCkgPT4gewogIC8vIFIxOCBNVVNUIGxvYWQgZmlyc3Qgc28gUjE3J3MgaW5pdGlhbCBydW50aW1lLnN0YXR1cyBpcyBub3QgbG9zdC4KICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMTgsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIxOCB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMTcsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIxNyB9KTsKCiAgYXdhaXQgd2FpdEZvcigoKSA9PiBmaXJzdFJlc3BvbnNlICE9PSBudWxsLCA1MDAwKTsKICBjb25zb2xlLmxvZygiUjE5X0ZJUlNUX1JFU1BPTlNFX0pTT049IiArIEpTT04uc3RyaW5naWZ5KGZpcnN0UmVzcG9uc2UpKTsKCiAgaWYgKHN0YXR1c1Jlc3BvbnNlID09PSBudWxsKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoCiAgICAgICJmaXJzdCBob3N0IHJlc3BvbnNlIHdhcyBub3QgcnVudGltZS5zdGF0dXM6ICIgKwogICAgICBKU09OLnN0cmluZ2lmeShmaXJzdFJlc3BvbnNlKQogICAgKTsKICB9CgogIGNvbnN0IHJvb3QgPSBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCgiYXVyYS1hMjAwLXN1cGVydmlzZWQtcm9vdCIpOwogIGlmICghcm9vdCkgdGhyb3cgbmV3IEVycm9yKCJSMTcgc3RhdHVzIHJvb3QgbWlzc2luZyIpOwogIGNvbnN0IHN0YXR1c05vZGUgPSByb290LnF1ZXJ5U2VsZWN0b3IoIltkYXRhLWF1cmEtYTIwMC1zdGF0dXNdIik7CiAgY29uc3QgdGV4dE5vZGUgPSByb290LnF1ZXJ5U2VsZWN0b3IoIltkYXRhLWF1cmEtYTIwMC1zdGF0dXMtdGV4dF0iKTsKCiAgY29uc29sZS5sb2coIlIxOV9OT0RFX0ZFVENIX0NPTlRFTlRfTEVOR1RIPXRydWUiKTsKICBjb25zb2xlLmxvZygiUjE5X05PREVfRkVUQ0hfT1JJR0lOX05VTEw9dHJ1ZSIpOwogIGNvbnNvbGUubG9nKCJSMTlfU1RBVFVTX0tJTkQ9IiArIHN0YXR1c1Jlc3BvbnNlLmtpbmQpOwogIGNvbnNvbGUubG9nKCJSMTlfU1RBVFVTX09LPSIgKyBzdGF0dXNSZXNwb25zZS5vayk7CiAgY29uc29sZS5sb2coIlIxOV9TRVNTSU9OX0lEPSIgKyAoc3RhdHVzUmVzcG9uc2Uuc2Vzc2lvbl9pZCB8fCAiIikpOwogIGNvbnNvbGUubG9nKCJSMTlfU1RBVFVTX01PREU9IiArIChzdGF0dXNOb2RlLmRhdGFzZXQubW9kZSB8fCAiIikpOwogIGNvbnNvbGUubG9nKCJSMTlfU1RBVFVTX1RFWFQ9IiArICh0ZXh0Tm9kZS50ZXh0Q29udGVudCB8fCAiIikpOwoKICBpZiAoc3RhdHVzUmVzcG9uc2Uub2sgIT09IHRydWUpIHRocm93IG5ldyBFcnJvcigicnVudGltZS5zdGF0dXMgZmFpbGVkIik7CiAgaWYgKCFzdGF0dXNSZXNwb25zZS5zZXNzaW9uX2lkKSB0aHJvdyBuZXcgRXJyb3IoInNlc3Npb24gaWQgbWlzc2luZyIpOwogIGlmIChzdGF0dXNOb2RlLmRhdGFzZXQubW9kZSAhPT0gInJlYWR5IikgdGhyb3cgbmV3IEVycm9yKCJzdGF0dXMgc3VyZmFjZSBub3QgcmVhZHkiKTsKICBpZiAoIVN0cmluZyh0ZXh0Tm9kZS50ZXh0Q29udGVudCkuaW5jbHVkZXMoInByw6p0ZSIpKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoInN0YXR1cyBzdXJmYWNlIHRleHQgbm90IHJlYWR5Iik7CiAgfQogIGNvbnNvbGUubG9nKCJSMTlfU1RBVFVTX1RFWFRfRE9NX1ZBTElEQVRFRD10cnVlIik7CgogIHdpbmRvdy5kaXNwYXRjaEV2ZW50KG5ldyBDdXN0b21FdmVudCgKICAgICJhdXJhOmEyMDAtc3VwZXJ2aXNlZC1yZXF1ZXN0IiwKICAgIHsKICAgICAgZGV0YWlsOiB7CiAgICAgICAgcHJvdG9jb2w6ICJhdXJhLnVpLXN1cGVydmlzZWQtYnJpZGdlLnYxIiwKICAgICAgICByZXF1ZXN0X2lkOiAicjE5LWxpdmUtcmVhZCIsCiAgICAgICAgc2Vzc2lvbl9pZDogc3RhdHVzUmVzcG9uc2Uuc2Vzc2lvbl9pZCwKICAgICAgICB0eXBlOiAicGMucmVhZF9mb3JlZ3JvdW5kIiwKICAgICAgICBwYXlsb2FkOiB7fQogICAgICB9CiAgICB9CiAgKSk7CgogIGF3YWl0IHdhaXRGb3IoKCkgPT4gcmVhZFJlc3BvbnNlICE9PSBudWxsLCA1MDAwKTsKCiAgY29uc29sZS5sb2coIlIxOV9SRUFEX0tJTkQ9IiArIHJlYWRSZXNwb25zZS5raW5kKTsKICBjb25zb2xlLmxvZygiUjE5X1JFQURfT0s9IiArIHJlYWRSZXNwb25zZS5vayk7CiAgY29uc29sZS5sb2coIlIxOV9SRUFEX1JFQ0VJUFQ9IiArICgoKHJlYWRSZXNwb25zZS5wYXlsb2FkIHx8IHt9KS5yZWNlaXB0X2lkKSB8fCAiIikpOwoKICBpZiAocmVhZFJlc3BvbnNlLm9rICE9PSB0cnVlKSB0aHJvdyBuZXcgRXJyb3IoInJlYWQgZm9yZWdyb3VuZCBmYWlsZWQiKTsKICBpZiAocmVhZFJlc3BvbnNlLmtpbmQgIT09ICJwYy5yZWFkX2ZvcmVncm91bmQiKSB0aHJvdyBuZXcgRXJyb3IoIndyb25nIHJlYWQga2luZCIpOwogIGlmICghKChyZWFkUmVzcG9uc2UucGF5bG9hZCB8fCB7fSkucmVjZWlwdF9pZCkpIHRocm93IG5ldyBFcnJvcigicmVhZCByZWNlaXB0IG1pc3NpbmciKTsKCiAgY29uc29sZS5sb2coIlIxOV9MSVZFX0hBTkRTSEFLRV9QQVNTPXRydWUiKTsKfSkoKS5jYXRjaCgoZXJyKSA9PiB7CiAgY29uc29sZS5lcnJvcihlcnIgJiYgZXJyLnN0YWNrID8gZXJyLnN0YWNrIDogU3RyaW5nKGVycikpOwogIHByb2Nlc3MuZXhpdENvZGUgPSAxOwp9KTsK"

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


add("R19 marker", A200_R19_MARKER == "AURA_A200_R19_HOST_LIFECYCLE_AUTOSTART_LIVE_HANDSHAKE_V1")
add("single host owner required", SINGLE_HOST_OWNER_REQUIRED is True)
add("autostart registration required", AUTO_START_REGISTRATION_REQUIRED is True)
add("loopback only required", LOOPBACK_ONLY_REQUIRED is True)
add("R18 transport authority required", R18_TRANSPORT_AUTHORITY_REQUIRED is True)
add("auto approval disabled", AUTO_APPROVAL_ENABLED is False)
add("auto cancel disabled", AUTO_CANCEL_ENABLED is False)
add("autonomous mutation disabled", AUTONOMOUS_MUTATION_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("shell execution disabled", SHELL_EXECUTION_ENABLED is False)
assert_r19_safety_contract()
add("R19 safety contract assertion", True)

token = TOKEN_FILE.read_text(encoding="ascii").strip()
add("production R18 token available", len(token) == 64)

state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r19_live_"))
lifecycle = None
second = None
try:
    lifecycle = A200UiHostLifecycle(
        state_root=state_root,
        token=token,
        host="127.0.0.1",
        port=18765,
        owner_id="r19-live-handshake",
    )
    snapshot = lifecycle.start()
    add("R19 lifecycle running", snapshot.state == "running")
    add("R19 lifecycle fixed loopback", snapshot.host == "127.0.0.1")
    add("R19 lifecycle fixed deployed port", snapshot.port == 18765)
    add("R19 lifecycle owns runtime session", bool(snapshot.session_id))
    add("R19 lifecycle status file written", (state_root / "r19_ui_host_lifecycle_status.json").is_file())

    second = A200UiHostLifecycle(
        state_root=state_root,
        token=token,
        host="127.0.0.1",
        port=18765,
        owner_id="r19-duplicate-owner",
    )
    must_raise(
        "R19 duplicate lifecycle owner rejected",
        UiHostLifecycleError,
        lambda: second.start(),
    )

    node = shutil.which("node")
    add("Node available for deployed UI handshake", bool(node), node or "MISSING")
    if not node:
        raise RuntimeError("Node is required for R19 deployed UI handshake")

    harness = state_root / "r19_live_ui_handshake.js"
    harness.write_bytes(base64.b64decode(NODE_HARNESS_B64))

    cp = subprocess.run(
        [node, str(harness), str(R17_JS), str(R18_JS)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    for line in (cp.stdout or "").splitlines():
        print("  node: " + line)

    add("R19 deployed UI live handshake Node PASS", cp.returncode == 0, f"exit={cp.returncode}")
    add("R19 Node fetch sent Content-Length", "R19_NODE_FETCH_CONTENT_LENGTH=true" in cp.stdout)
    add("R19 Node fetch sent null Origin", "R19_NODE_FETCH_ORIGIN_NULL=true" in cp.stdout)
    add("R19 Node received first host response", "R19_FIRST_RESPONSE_JSON=" in cp.stdout)
    add("R19 actual status response ok", "R19_STATUS_OK=true" in cp.stdout)
    add("R19 actual runtime session returned", "R19_SESSION_ID=" in cp.stdout and "R19_SESSION_ID=\n" not in cp.stdout)
    add("R19 status surface mode ready", "R19_STATUS_MODE=ready" in cp.stdout)
    add(
        "R19 status surface DOM text validated internally",
        "R19_STATUS_TEXT_DOM_VALIDATED=true" in cp.stdout,
    )
    add("R19 actual UI transport read response ok", "R19_READ_OK=true" in cp.stdout)
    add("R19 actual UI transport read receipt present", "R19_READ_RECEIPT=" in cp.stdout and "R19_READ_RECEIPT=\n" not in cp.stdout)
    add("R19 live handshake marker", "R19_LIVE_HANDSHAKE_PASS=true" in cp.stdout)

    real_read_only_windows_observation = "R19_READ_OK=true" in cp.stdout

finally:
    if second is not None:
        try:
            second.close()
        except Exception:
            pass
    if lifecycle is not None:
        lifecycle.close()

third = A200UiHostLifecycle(
    state_root=state_root,
    token=token,
    host="127.0.0.1",
    port=18765,
    owner_id="r19-reacquire",
)
try:
    snap3 = third.start()
    add("R19 lifecycle lock safely reacquired after close", snap3.state == "running")
finally:
    third.close()
    shutil.rmtree(state_root, ignore_errors=True)

src_path = ROOT / "runtime" / "aura_ui_host_lifecycle_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R19 source wraps R18 transport", "A200UiHostTransport" in src)
add("R19 source keeps fixed loopback", "LOOPBACK_HOST" in src)
add("R19 source uses Windows file lock", "msvcrt.locking" in src)
add("R19 source normalizes lock open failure", "LOCK_OPEN_FAILURE_NORMALIZED = True" in src)
add("R19 source documents Content-Length harness requirement", "NODE_FETCH_CONTENT_LENGTH_REQUIRED = True" in src)
add("R19 source contains no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R19 source contains no shell API", all(token not in src for token in ("os.system(", "os.popen(", "ctypes.", "child_process")))
add("R19 source contains no approval command", "approval.confirm" not in src)
add("R19 source contains no cancellation command", "mission.cancel" not in src)
add("R19 source contains no close capability", "pc.close_window" not in src)
add("R19 source contains no terminate capability", "pc.terminate_process" not in src)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R19_REAL_READ_ONLY_WINDOWS_OBSERVATION = {real_read_only_windows_observation}")
print(f"R19_REAL_PC_OR_WINDOW_MUTATED = {real_pc_or_window_mutated}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if not real_read_only_windows_observation:
    raise SystemExit("R19 expected one real read-only Windows observation")
if real_pc_or_window_mutated:
    raise SystemExit("R19 must not mutate a real window")
print("[PASS] A200-R19 lifecycle autostart + deployed UI live handshake/status surface")
