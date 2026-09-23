from __future__ import annotations

import base64
import ctypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_deployed_live_approval_acceptance_v200 import (
    A200_R22_MARKER,
    APPROVAL_ONE_USE_REQUIRED,
    AUTO_APPROVAL_ENABLED,
    AUTO_CANCEL_ENABLED,
    AUTOMATIC_EXACT_RESTORE_REQUIRED,
    AUTONOMOUS_MULTI_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    CANONICAL_RECEIPTS_REQUIRED,
    CLOSE_WINDOW_ENABLED,
    CRASH_JOURNAL_CLEAR_REQUIRED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED,
    EXPLICIT_HUMAN_APPROVAL_REQUIRED,
    EXPLICIT_R17_UI_CONFIRMATION_REQUIRED,
    LIVE_CAPABILITY,
    LIVE_SELF_WINDOW_ONLY,
    MISSIONENGINE_COMPLETION_REQUIRED,
    SHELL_EXECUTION_ENABLED,
    SINGLE_REVERSIBLE_MUTATION_REQUIRED,
    TERMINATE_PROCESS_ENABLED,
    R22AcceptanceDenied,
    assert_r22_safety_contract,
    foreground_hwnd,
    task_by_key,
)
from runtime.aura_conversation_intent_handoff_v200 import (
    A200IntentPreviewHost,
)
from runtime.aura_ui_host_lifecycle_v200 import (
    A200UiHostLifecycle,
)
from runtime.aura_ui_conversation_supervised_bridge_v200 import (
    UiApprovalPresentationError,
)

UI_ROOT = Path(
    r"C:\Users\leclerc\AppData\Local\AURA\ui\v0.7.2.2-rc4.2"
)
R17 = UI_ROOT / "dist" / "assets" / "aura-a200-supervised-bridge-ui.js"
R18 = UI_ROOT / "dist" / "assets" / "aura-a200-supervised-host-transport.js"
R20 = UI_ROOT / "dist" / "assets" / "aura-a200-conversation-intent-preview.js"
R21 = UI_ROOT / "dist" / "assets" / "aura-a200-composer-supervised-plan.js"
TOKEN_FILE = ROOT / "data" / "a200_runtime" / "r18_ui_transport_token.txt"
NODE_HARNESS_B64 = "Y29uc3QgZnMgPSByZXF1aXJlKCJmcyIpOwpjb25zdCBodHRwID0gcmVxdWlyZSgiaHR0cCIpOwpjb25zdCB2bSA9IHJlcXVpcmUoInZtIik7Cgpjb25zdCBSMTcgPSBwcm9jZXNzLmFyZ3ZbMl07CmNvbnN0IFIxOCA9IHByb2Nlc3MuYXJndlszXTsKY29uc3QgUjIwID0gcHJvY2Vzcy5hcmd2WzRdOwpjb25zdCBSMjEgPSBwcm9jZXNzLmFyZ3ZbNV07CmNvbnN0IFNFTEZfTUFSS0VSID0gcHJvY2Vzcy5hcmd2WzZdIHx8ICIiOwoKY29uc3QgbGlzdGVuZXJzID0gbmV3IE1hcCgpOwpjb25zdCByZXF1ZXN0QXVkaXQgPSBbXTsKCmNsYXNzIEN1c3RvbUV2ZW50IHsKICBjb25zdHJ1Y3Rvcih0eXBlLCBvcHRpb25zID0ge30pIHsKICAgIHRoaXMudHlwZSA9IHR5cGU7CiAgICB0aGlzLmRldGFpbCA9IG9wdGlvbnMuZGV0YWlsOwogIH0KfQoKY2xhc3MgRmFrZU11dGF0aW9uT2JzZXJ2ZXIgewogIGNvbnN0cnVjdG9yKGZuKSB7IHRoaXMuZm4gPSBmbjsgfQogIG9ic2VydmUoKSB7fQogIGRpc2Nvbm5lY3QoKSB7fQp9Cmdsb2JhbC5NdXRhdGlvbk9ic2VydmVyID0gRmFrZU11dGF0aW9uT2JzZXJ2ZXI7CgpmdW5jdGlvbiBhZGRXaW5kb3dMaXN0ZW5lcih0eXBlLCBmbikgewogIGlmICghbGlzdGVuZXJzLmhhcyh0eXBlKSkgbGlzdGVuZXJzLnNldCh0eXBlLCBbXSk7CiAgbGlzdGVuZXJzLmdldCh0eXBlKS5wdXNoKGZuKTsKfQoKZnVuY3Rpb24gZGlzcGF0Y2hXaW5kb3coZXZlbnQpIHsKICBpZiAoZXZlbnQudHlwZSA9PT0gImF1cmE6YTIwMC1zdXBlcnZpc2VkLXJlcXVlc3QiKSB7CiAgICByZXF1ZXN0QXVkaXQucHVzaChKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KGV2ZW50LmRldGFpbCB8fCB7fSkpKTsKICB9CiAgZm9yIChjb25zdCBmbiBvZiBbLi4uKGxpc3RlbmVycy5nZXQoZXZlbnQudHlwZSkgfHwgW10pXSkgewogICAgZm4uY2FsbCh3aW5kb3csIGV2ZW50KTsKICB9CiAgcmV0dXJuIHRydWU7Cn0KCmNsYXNzIEZha2VOb2RlIHsKICBjb25zdHJ1Y3RvcihzZWxlY3RvciA9ICIiKSB7CiAgICB0aGlzLnNlbGVjdG9yID0gc2VsZWN0b3I7CiAgICB0aGlzLmRhdGFzZXQgPSB7fTsKICAgIHRoaXMudGV4dENvbnRlbnQgPSAiIjsKICAgIHRoaXMuaGlkZGVuID0gZmFsc2U7CiAgICB0aGlzLmRpc2FibGVkID0gZmFsc2U7CiAgICB0aGlzLmlkID0gIiI7CiAgICB0aGlzLnR5cGUgPSAiIjsKICAgIHRoaXMudmFsdWUgPSAiIjsKICAgIHRoaXMucGFyZW50RWxlbWVudCA9IG51bGw7CiAgICB0aGlzLmNoaWxkcmVuID0gW107CiAgICB0aGlzLmV2ZW50cyA9IHt9OwogICAgdGhpcy5fYXR0cnMgPSB7fTsKICAgIHRoaXMuX3F1ZXJpZXMgPSBuZXcgTWFwKCk7CiAgfQogIGFkZEV2ZW50TGlzdGVuZXIodHlwZSwgZm4pIHsKICAgIGlmICghdGhpcy5ldmVudHNbdHlwZV0pIHRoaXMuZXZlbnRzW3R5cGVdID0gW107CiAgICB0aGlzLmV2ZW50c1t0eXBlXS5wdXNoKGZuKTsKICB9CiAgY2xpY2soKSB7CiAgICBmb3IgKGNvbnN0IGZuIG9mIHRoaXMuZXZlbnRzLmNsaWNrIHx8IFtdKSB7CiAgICAgIGZuLmNhbGwodGhpcywgeyB0eXBlOiAiY2xpY2siLCB0YXJnZXQ6IHRoaXMgfSk7CiAgICB9CiAgfQogIHNldEF0dHJpYnV0ZShuYW1lLCB2YWx1ZSkgewogICAgdGhpcy5fYXR0cnNbbmFtZV0gPSBTdHJpbmcodmFsdWUpOwogIH0KICBoYXNBdHRyaWJ1dGUobmFtZSkgewogICAgcmV0dXJuIE9iamVjdC5wcm90b3R5cGUuaGFzT3duUHJvcGVydHkuY2FsbCh0aGlzLl9hdHRycywgbmFtZSk7CiAgfQogIGFwcGVuZENoaWxkKG5vZGUpIHsKICAgIG5vZGUucGFyZW50RWxlbWVudCA9IHRoaXM7CiAgICB0aGlzLmNoaWxkcmVuLnB1c2gobm9kZSk7CiAgICBpZiAobm9kZS5pZCkgZG9jdW1lbnQuX2J5SWQuc2V0KG5vZGUuaWQsIG5vZGUpOwogICAgcmV0dXJuIG5vZGU7CiAgfQogIHF1ZXJ5U2VsZWN0b3Ioc2VsZWN0b3IpIHsKICAgIGlmIChzZWxlY3RvciA9PT0gIltkYXRhLWF1cmEtYTIwMC1yMjEtcGxhbl0iKSB7CiAgICAgIHJldHVybiB0aGlzLmNoaWxkcmVuLmZpbmQoCiAgICAgICAgbiA9PiBuLmhhc0F0dHJpYnV0ZSAmJgogICAgICAgICAgbi5oYXNBdHRyaWJ1dGUoImRhdGEtYXVyYS1hMjAwLXIyMS1wbGFuIikKICAgICAgKSB8fCBudWxsOwogICAgfQogICAgaWYgKCF0aGlzLl9xdWVyaWVzLmhhcyhzZWxlY3RvcikpIHsKICAgICAgdGhpcy5fcXVlcmllcy5zZXQoc2VsZWN0b3IsIG5ldyBGYWtlTm9kZShzZWxlY3RvcikpOwogICAgfQogICAgcmV0dXJuIHRoaXMuX3F1ZXJpZXMuZ2V0KHNlbGVjdG9yKTsKICB9Cn0KCmNsYXNzIEZha2VSb290IGV4dGVuZHMgRmFrZU5vZGUgewogIGNvbnN0cnVjdG9yKCkgewogICAgc3VwZXIoInJvb3QiKTsKICAgIHRoaXMuX2h0bWwgPSAiIjsKICB9CiAgc2V0IGlubmVySFRNTCh2YWx1ZSkgeyB0aGlzLl9odG1sID0gdmFsdWU7IH0KICBnZXQgaW5uZXJIVE1MKCkgeyByZXR1cm4gdGhpcy5faHRtbDsgfQp9Cgpjb25zdCBjb21wb3NlclBhcmVudCA9IG5ldyBGYWtlTm9kZSgiY29tcG9zZXItcGFyZW50Iik7CmNvbnN0IGNvbXBvc2VySW5wdXQgPSBuZXcgRmFrZU5vZGUoImNvbXBvc2VyLWlucHV0Iik7CmNvbXBvc2VySW5wdXQudmFsdWUgPSAibWluaW1pc2UgbGEgZmVuw6p0cmUgYWN0aXZlIjsKY29tcG9zZXJQYXJlbnQuYXBwZW5kQ2hpbGQoY29tcG9zZXJJbnB1dCk7CgpnbG9iYWwuQ3VzdG9tRXZlbnQgPSBDdXN0b21FdmVudDsKZ2xvYmFsLndpbmRvdyA9IHsKICBhZGRFdmVudExpc3RlbmVyOiBhZGRXaW5kb3dMaXN0ZW5lciwKICBkaXNwYXRjaEV2ZW50OiBkaXNwYXRjaFdpbmRvdwp9OwoKZ2xvYmFsLmRvY3VtZW50ID0gewogIHJlYWR5U3RhdGU6ICJjb21wbGV0ZSIsCiAgX2J5SWQ6IG5ldyBNYXAoKSwKICBib2R5OiBuZXcgRmFrZU5vZGUoImJvZHkiKSwKICBjb250YWlucyhub2RlKSB7IHJldHVybiAhIW5vZGU7IH0sCiAgZ2V0RWxlbWVudEJ5SWQoaWQpIHsKICAgIHJldHVybiB0aGlzLl9ieUlkLmdldChpZCkgfHwgbnVsbDsKICB9LAogIGNyZWF0ZUVsZW1lbnQodGFnKSB7CiAgICByZXR1cm4gdGFnID09PSAic2VjdGlvbiIKICAgICAgPyBuZXcgRmFrZVJvb3QoKQogICAgICA6IG5ldyBGYWtlTm9kZSh0YWcpOwogIH0sCiAgYWRkRXZlbnRMaXN0ZW5lcigpIHt9LAogIHF1ZXJ5U2VsZWN0b3Ioc2VsZWN0b3IpIHsKICAgIGlmIChzZWxlY3RvciA9PT0gIltkYXRhLWF1cmEtY29tcG9zZXJdIHRleHRhcmVhIikgewogICAgICByZXR1cm4gY29tcG9zZXJJbnB1dDsKICAgIH0KICAgIHJldHVybiBudWxsOwogIH0KfTsKCmRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQgPSBmdW5jdGlvbihub2RlKSB7CiAgbm9kZS5wYXJlbnRFbGVtZW50ID0gdGhpczsKICB0aGlzLmNoaWxkcmVuLnB1c2gobm9kZSk7CiAgaWYgKG5vZGUuaWQpIGRvY3VtZW50Ll9ieUlkLnNldChub2RlLmlkLCBub2RlKTsKICByZXR1cm4gbm9kZTsKfTsKCmZ1bmN0aW9uIGZldGNoV2l0aE9uZVRyYW5zaWVudFJldHJ5KHVybCwgb3B0aW9ucyA9IHt9LCBhdHRlbXB0ID0gMCkgewogIHJldHVybiBuZXcgUHJvbWlzZSgocmVzb2x2ZSwgcmVqZWN0KSA9PiB7CiAgICBjb25zdCB1ID0gbmV3IFVSTCh1cmwpOwogICAgY29uc3QgYm9keSA9IG9wdGlvbnMuYm9keSB8fCAiIjsKICAgIGNvbnN0IGhlYWRlcnMgPSBPYmplY3QuYXNzaWduKHt9LCBvcHRpb25zLmhlYWRlcnMgfHwge30pOwogICAgaGVhZGVyc1siQ29udGVudC1MZW5ndGgiXSA9IEJ1ZmZlci5ieXRlTGVuZ3RoKGJvZHkpOwogICAgaWYgKCFPYmplY3Qua2V5cyhoZWFkZXJzKS5zb21lKGsgPT4gay50b0xvd2VyQ2FzZSgpID09PSAib3JpZ2luIikpIHsKICAgICAgaGVhZGVyc1siT3JpZ2luIl0gPSAibnVsbCI7CiAgICB9CgogICAgY29uc3QgcmVxID0gaHR0cC5yZXF1ZXN0KAogICAgICB7CiAgICAgICAgaG9zdG5hbWU6IHUuaG9zdG5hbWUsCiAgICAgICAgcG9ydDogdS5wb3J0LAogICAgICAgIHBhdGg6IHUucGF0aG5hbWUgKyB1LnNlYXJjaCwKICAgICAgICBtZXRob2Q6IG9wdGlvbnMubWV0aG9kIHx8ICJHRVQiLAogICAgICAgIGhlYWRlcnMKICAgICAgfSwKICAgICAgKHJlcykgPT4gewogICAgICAgIGxldCBkYXRhID0gIiI7CiAgICAgICAgcmVzLnNldEVuY29kaW5nKCJ1dGY4Iik7CiAgICAgICAgcmVzLm9uKCJkYXRhIiwgY2h1bmsgPT4gZGF0YSArPSBjaHVuayk7CiAgICAgICAgcmVzLm9uKCJlbmQiLCAoKSA9PiB7CiAgICAgICAgICByZXNvbHZlKHsKICAgICAgICAgICAgb2s6IHJlcy5zdGF0dXNDb2RlID49IDIwMCAmJiByZXMuc3RhdHVzQ29kZSA8IDMwMCwKICAgICAgICAgICAgc3RhdHVzOiByZXMuc3RhdHVzQ29kZSwKICAgICAgICAgICAgYXN5bmMganNvbigpIHsKICAgICAgICAgICAgICByZXR1cm4gSlNPTi5wYXJzZShkYXRhIHx8ICJ7fSIpOwogICAgICAgICAgICB9CiAgICAgICAgICB9KTsKICAgICAgICB9KTsKICAgICAgfQogICAgKTsKCiAgICByZXEub24oImVycm9yIiwgKGVycikgPT4gewogICAgICBjb25zdCB0cmFuc2llbnQgPQogICAgICAgIGVyciAmJgogICAgICAgIChlcnIuY29kZSA9PT0gIkVDT05OUkVTRVQiIHx8CiAgICAgICAgIGVyci5jb2RlID09PSAiRUNPTk5BQk9SVEVEIik7CiAgICAgIGlmICh0cmFuc2llbnQgJiYgYXR0ZW1wdCA8IDEpIHsKICAgICAgICBzZXRUaW1lb3V0KCgpID0+IHsKICAgICAgICAgIGZldGNoV2l0aE9uZVRyYW5zaWVudFJldHJ5KHVybCwgb3B0aW9ucywgYXR0ZW1wdCArIDEpCiAgICAgICAgICAgIC50aGVuKHJlc29sdmUsIHJlamVjdCk7CiAgICAgICAgfSwgMTUwKTsKICAgICAgICByZXR1cm47CiAgICAgIH0KICAgICAgcmVqZWN0KGVycik7CiAgICB9KTsKCiAgICBpZiAoYm9keSkgcmVxLndyaXRlKGJvZHkpOwogICAgcmVxLmVuZCgpOwogIH0pOwp9Cmdsb2JhbC5mZXRjaCA9IGZldGNoV2l0aE9uZVRyYW5zaWVudFJldHJ5OwoKbGV0IHN0YXR1c0NvdW50ID0gMDsKbGV0IGxhdGVzdFN0YXR1cyA9IG51bGw7CmxldCBhcHByb3ZhbFJlcXVpcmVkID0gbnVsbDsKbGV0IGFwcHJvdmFsQ29tcGxldGVkID0gbnVsbDsKCndpbmRvdy5hZGRFdmVudExpc3RlbmVyKCJhdXJhOmEyMDAtc3VwZXJ2aXNlZC1yZXNwb25zZSIsIChldmVudCkgPT4gewogIGNvbnN0IGQgPSBldmVudC5kZXRhaWwgfHwge307CiAgaWYgKGQua2luZCA9PT0gInJ1bnRpbWUuc3RhdHVzIikgewogICAgc3RhdHVzQ291bnQgKz0gMTsKICAgIGxhdGVzdFN0YXR1cyA9IGQ7CiAgfQogIGlmIChkLmtpbmQgPT09ICJhcHByb3ZhbC5yZXF1aXJlZCIpIHsKICAgIGFwcHJvdmFsUmVxdWlyZWQgPSBkOwogIH0KICBpZiAoZC5raW5kID09PSAiYXBwcm92YWwuY29tcGxldGVkIikgewogICAgYXBwcm92YWxDb21wbGV0ZWQgPSBkOwogIH0KfSk7CgpmdW5jdGlvbiB3YWl0Rm9yKHByZWRpY2F0ZSwgdGltZW91dE1zKSB7CiAgY29uc3Qgc3RhcnQgPSBEYXRlLm5vdygpOwogIHJldHVybiBuZXcgUHJvbWlzZSgocmVzb2x2ZSwgcmVqZWN0KSA9PiB7CiAgICBjb25zdCB0aW1lciA9IHNldEludGVydmFsKCgpID0+IHsKICAgICAgdHJ5IHsKICAgICAgICBpZiAocHJlZGljYXRlKCkpIHsKICAgICAgICAgIGNsZWFySW50ZXJ2YWwodGltZXIpOwogICAgICAgICAgcmVzb2x2ZSgpOwogICAgICAgICAgcmV0dXJuOwogICAgICAgIH0KICAgICAgICBpZiAoRGF0ZS5ub3coKSAtIHN0YXJ0ID4gdGltZW91dE1zKSB7CiAgICAgICAgICBjbGVhckludGVydmFsKHRpbWVyKTsKICAgICAgICAgIHJlamVjdChuZXcgRXJyb3IoInRpbWVvdXQiKSk7CiAgICAgICAgfQogICAgICB9IGNhdGNoIChlcnIpIHsKICAgICAgICBjbGVhckludGVydmFsKHRpbWVyKTsKICAgICAgICByZWplY3QoZXJyKTsKICAgICAgfQogICAgfSwgMjUpOwogIH0pOwp9CgooYXN5bmMgKCkgPT4gewogIHZtLnJ1bkluVGhpc0NvbnRleHQoZnMucmVhZEZpbGVTeW5jKFIxOCwgInV0ZjgiKSwgeyBmaWxlbmFtZTogUjE4IH0pOwogIHZtLnJ1bkluVGhpc0NvbnRleHQoZnMucmVhZEZpbGVTeW5jKFIxNywgInV0ZjgiKSwgeyBmaWxlbmFtZTogUjE3IH0pOwogIHZtLnJ1bkluVGhpc0NvbnRleHQoZnMucmVhZEZpbGVTeW5jKFIyMCwgInV0ZjgiKSwgeyBmaWxlbmFtZTogUjIwIH0pOwogIHZtLnJ1bkluVGhpc0NvbnRleHQoZnMucmVhZEZpbGVTeW5jKFIyMSwgInV0ZjgiKSwgeyBmaWxlbmFtZTogUjIxIH0pOwoKICBhd2FpdCB3YWl0Rm9yKCgpID0+IGxhdGVzdFN0YXR1cyAhPT0gbnVsbCwgNTAwMCk7CiAgaWYgKGxhdGVzdFN0YXR1cy5vayAhPT0gdHJ1ZSkgewogICAgdGhyb3cgbmV3IEVycm9yKCJpbml0aWFsIHJ1bnRpbWUuc3RhdHVzIGZhaWxlZCIpOwogIH0KCiAgY29uc3Qgc2VhbSA9IHdpbmRvdy5BVVJBX0EyMDBfQ09NUE9TRVJfU1VQRVJWSVNJT047CiAgaWYgKCFzZWFtKSB0aHJvdyBuZXcgRXJyb3IoIlIyMSBzZWFtIEFQSSB1bmF2YWlsYWJsZSIpOwoKICBjb25zdCBib3VuZCA9IHNlYW0uYmluZENvbXBvc2VyKGRvY3VtZW50KTsKICBpZiAoIWJvdW5kKSB0aHJvdyBuZXcgRXJyb3IoImNvbXBvc2VyIGJpbmRpbmcgZmFpbGVkIik7CiAgY29uc29sZS5sb2coIlIyMl9DT01QT1NFUl9CT1VORD10cnVlIik7CgogIGNvbnN0IHBsYW5CdXR0b24gPSBjb21wb3NlclBhcmVudC5xdWVyeVNlbGVjdG9yKAogICAgIltkYXRhLWF1cmEtYTIwMC1yMjEtcGxhbl0iCiAgKTsKICBpZiAoIXBsYW5CdXR0b24pIHRocm93IG5ldyBFcnJvcigiUGxhbiBBVVJBIGJ1dHRvbiBtaXNzaW5nIik7CgogIHBsYW5CdXR0b24uY2xpY2soKTsKICBhd2FpdCB3YWl0Rm9yKAogICAgKCkgPT4gewogICAgICBjb25zdCBwID0gc2VhbS5nZXRBY3RpdmVQcmV2aWV3KCk7CiAgICAgIHJldHVybiBwICYmIHAuaW50ZW50X2tpbmQgPT09ICJzdXBlcnZpc2VkX211dGF0aW9uIjsKICAgIH0sCiAgICA1MDAwCiAgKTsKCiAgY29uc3QgcHJldmlldyA9IHNlYW0uZ2V0QWN0aXZlUHJldmlldygpOwogIGNvbnNvbGUubG9nKCJSMjJfUFJFVklFV19LSU5EPSIgKyBwcmV2aWV3LmludGVudF9raW5kKTsKICBjb25zb2xlLmxvZygiUjIyX1BSRVZJRVdfRVhFQ1VUQUJMRT0iICsgcHJldmlldy5leGVjdXRpb25fYWxsb3dlZCk7CiAgY29uc29sZS5sb2coCiAgICAiUjIyX1BMQU5fRElHRVNUX0xFTj0iICsKICAgIFN0cmluZyhwcmV2aWV3LnBsYW5fZGlnZXN0IHx8ICIiKS5sZW5ndGgKICApOwogIGlmIChwcmV2aWV3LmV4ZWN1dGlvbl9hbGxvd2VkICE9PSBmYWxzZSkgewogICAgdGhyb3cgbmV3IEVycm9yKCJtdXRhdGlvbiBwcmV2aWV3IG11c3QgcmVtYWluIG5vbi1leGVjdXRhYmxlIik7CiAgfQoKICBjb25zdCBwcmVwYXJlZCA9IGF3YWl0IHNlYW0ucHJlcGFyZVN1cGVydmlzZWRNdXRhdGlvbigpOwogIGlmIChwcmVwYXJlZC5raW5kICE9PSAiYXBwcm92YWwucmVxdWlyZWQiKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoInByZXBhcmUgZGlkIG5vdCByZXR1cm4gYXBwcm92YWwucmVxdWlyZWQiKTsKICB9CgogIGF3YWl0IHdhaXRGb3IoKCkgPT4gYXBwcm92YWxSZXF1aXJlZCAhPT0gbnVsbCwgNTAwMCk7CgogIGNvbnN0IHByZXNlbnRhdGlvbiA9IHNlYW0uZ2V0QXBwcm92YWxQcmVzZW50YXRpb24oKTsKICBpZiAoIXByZXNlbnRhdGlvbikgewogICAgdGhyb3cgbmV3IEVycm9yKCJhcHByb3ZhbCBwcmVzZW50YXRpb24gdW5hdmFpbGFibGUiKTsKICB9CiAgaWYgKHByZXNlbnRhdGlvbi5yZXZlcnNpYmxlICE9PSB0cnVlKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoImFwcHJvdmFsIGlzIG5vdCByZXZlcnNpYmxlIik7CiAgfQogIGlmIChwcmVzZW50YXRpb24ucmVxdWlyZXNfZXhwbGljaXRfY29uZmlybWF0aW9uICE9PSB0cnVlKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoImFwcHJvdmFsIGlzIG5vdCBleHBsaWNpdGx5IGNvbmZpcm1hYmxlIik7CiAgfQogIGlmICgKICAgIHR5cGVvZiBwcmVzZW50YXRpb24ucHJlc2VudGF0aW9uX2RpZ2VzdCAhPT0gInN0cmluZyIgfHwKICAgIHByZXNlbnRhdGlvbi5wcmVzZW50YXRpb25fZGlnZXN0Lmxlbmd0aCAhPT0gNjQKICApIHsKICAgIHRocm93IG5ldyBFcnJvcigicHJlc2VudGF0aW9uIGRpZ2VzdCBpbnZhbGlkIik7CiAgfQoKICBjb25zdCB0YXJnZXQgPSBzZWFtLmdldFJlc29sdmVkVGFyZ2V0KCkgfHwge307CiAgY29uc3QgbWFya2VyTWF0Y2ggPQogICAgU3RyaW5nKHRhcmdldC50aXRsZSB8fCAiIikudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygKICAgICAgU0VMRl9NQVJLRVIudG9Mb3dlckNhc2UoKQogICAgKSAmJgogICAgcHJlc2VudGF0aW9uLnRhcmdldF9od25kID09PSB0YXJnZXQuaHduZCAmJgogICAgcHJlc2VudGF0aW9uLnRhcmdldF90aXRsZSA9PT0gdGFyZ2V0LnRpdGxlOwoKICBjb25zb2xlLmxvZygiUjIyX1RBUkdFVF9IV05EPSIgKyAodGFyZ2V0Lmh3bmQgfHwgIiIpKTsKICBjb25zb2xlLmxvZygiUjIyX1RBUkdFVF9NQVJLRVJfTUFUQ0g9IiArIG1hcmtlck1hdGNoKTsKICBjb25zb2xlLmxvZygKICAgICJSMjJfQVBQUk9WQUxfSUQ9IiArCiAgICAocHJlc2VudGF0aW9uLmFwcHJvdmFsX2lkIHx8ICIiKQogICk7CiAgY29uc29sZS5sb2coCiAgICAiUjIyX01JU1NJT05fSUQ9IiArCiAgICAocHJlc2VudGF0aW9uLm1pc3Npb25faWQgfHwgIiIpCiAgKTsKICBjb25zb2xlLmxvZygKICAgICJSMjJfUFJFU0VOVEFUSU9OX0RJR0VTVD0iICsKICAgIChwcmVzZW50YXRpb24ucHJlc2VudGF0aW9uX2RpZ2VzdCB8fCAiIikKICApOwoKICBpZiAoIW1hcmtlck1hdGNoKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoImFwcHJvdmFsIHRhcmdldCBpcyBub3QgdGhlIGV4YWN0IFIyMiBjb25zb2xlIik7CiAgfQoKICAvLyBUaGUgaHVtYW4gYXBwcm92YWwgd2FzIGNhcHR1cmVkIGJ5IHRoZSBCQVQgYmVmb3JlIHRoaXMgaGFybmVzcyBydW5zLgogIC8vIFRoaXMgY2xpY2sgZXhlcmNpc2VzIHRoZSBSRUFMIGRlcGxveWVkIFIxNyBleHBsaWNpdCBjb25maXJtYXRpb24gcGF0aC4KICBjb25zdCByMTdSb290ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoCiAgICAiYXVyYS1hMjAwLXN1cGVydmlzZWQtcm9vdCIKICApOwogIGlmICghcjE3Um9vdCkgdGhyb3cgbmV3IEVycm9yKCJSMTcgYXBwcm92YWwgcm9vdCBtaXNzaW5nIik7CgogIGNvbnN0IGFwcHJvdmVCdXR0b24gPSByMTdSb290LnF1ZXJ5U2VsZWN0b3IoCiAgICAiW2RhdGEtYXVyYS1hMjAwLWFwcHJvdmVdIgogICk7CiAgY29uc3QgZGlhbG9nID0gcjE3Um9vdC5xdWVyeVNlbGVjdG9yKAogICAgIltkYXRhLWF1cmEtYTIwMC1hcHByb3ZhbF0iCiAgKTsKICBpZiAoIWFwcHJvdmVCdXR0b24gfHwgZGlhbG9nLmhpZGRlbiA9PT0gdHJ1ZSkgewogICAgdGhyb3cgbmV3IEVycm9yKCJSMTcgYXBwcm92YWwgZGlhbG9nL2J1dHRvbiBub3QgYWN0aXZlIik7CiAgfQoKICBhcHByb3ZlQnV0dG9uLmNsaWNrKCk7CgogIGF3YWl0IHdhaXRGb3IoKCkgPT4gYXBwcm92YWxDb21wbGV0ZWQgIT09IG51bGwsIDE1MDAwKTsKICBpZiAoYXBwcm92YWxDb21wbGV0ZWQub2sgIT09IHRydWUpIHsKICAgIHRocm93IG5ldyBFcnJvcigiYXBwcm92YWwuY29tcGxldGVkIHJldHVybmVkIGZhaWx1cmUiKTsKICB9CiAgaWYgKAogICAgKGFwcHJvdmFsQ29tcGxldGVkLnBheWxvYWQgfHwge30pLm1pc3Npb25fc3RhdHVzICE9PSAiY29tcGxldGVkIgogICkgewogICAgdGhyb3cgbmV3IEVycm9yKCJhcHByb3ZlZCBtaXNzaW9uIGRpZCBub3QgY29tcGxldGUiKTsKICB9CgogIGF3YWl0IHdhaXRGb3IoCiAgICAoKSA9PiBzdGF0dXNDb3VudCA+PSAyLAogICAgNTAwMAogICk7CgogIGNvbnN0IGFwcHJvdmFsQ29uZmlybXMgPSByZXF1ZXN0QXVkaXQuZmlsdGVyKAogICAgeCA9PiB4LnR5cGUgPT09ICJhcHByb3ZhbC5jb25maXJtIgogICk7CiAgY29uc29sZS5sb2coCiAgICAiUjIyX0FQUFJPVkFMX0NPTkZJUk1fQ09VTlQ9IiArCiAgICBhcHByb3ZhbENvbmZpcm1zLmxlbmd0aAogICk7CiAgaWYgKGFwcHJvdmFsQ29uZmlybXMubGVuZ3RoICE9PSAxKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoImFwcHJvdmFsLmNvbmZpcm0gd2FzIG5vdCBlbWl0dGVkIGV4YWN0bHkgb25jZSIpOwogIH0KCiAgY29uc3QgY29uZmlybVBheWxvYWQgPSBhcHByb3ZhbENvbmZpcm1zWzBdLnBheWxvYWQgfHwge307CiAgY29uc3QgY29uZmlybUJvdW5kID0KICAgIGNvbmZpcm1QYXlsb2FkLmNvbmZpcm0gPT09IHRydWUgJiYKICAgIGNvbmZpcm1QYXlsb2FkLmFwcHJvdmFsX2lkID09PSBwcmVzZW50YXRpb24uYXBwcm92YWxfaWQgJiYKICAgIGNvbmZpcm1QYXlsb2FkLnByZXNlbnRhdGlvbl9kaWdlc3QgPT09CiAgICAgIHByZXNlbnRhdGlvbi5wcmVzZW50YXRpb25fZGlnZXN0OwoKICBjb25zb2xlLmxvZygiUjIyX0FQUFJPVkFMX0NPTkZJUk1fQk9VTkQ9IiArIGNvbmZpcm1Cb3VuZCk7CiAgaWYgKCFjb25maXJtQm91bmQpIHsKICAgIHRocm93IG5ldyBFcnJvcigiYXBwcm92YWwuY29uZmlybSBpcyBub3QgZXhhY3RseSBwcmVzZW50YXRpb24tYm91bmQiKTsKICB9CgogIGNvbnNvbGUubG9nKAogICAgIlIyMl9BUFBST1ZBTF9DT01QTEVURURfUEhBU0U9IiArCiAgICAoKChhcHByb3ZhbENvbXBsZXRlZC5wYXlsb2FkIHx8IHt9KS5waGFzZSkgfHwgIiIpCiAgKTsKICBjb25zb2xlLmxvZygKICAgICJSMjJfQVBQUk9WQUxfQ09NUExFVEVEX1NUQVRVUz0iICsKICAgICgoKGFwcHJvdmFsQ29tcGxldGVkLnBheWxvYWQgfHwge30pLm1pc3Npb25fc3RhdHVzKSB8fCAiIikKICApOwogIGNvbnNvbGUubG9nKAogICAgIlIyMl9SMTdfRElBTE9HX0hJRERFTl9BRlRFUj0iICsKICAgIChkaWFsb2cuaGlkZGVuID09PSB0cnVlKQogICk7CgogIGNvbnN0IHN0YXR1c05vZGUgPSByMTdSb290LnF1ZXJ5U2VsZWN0b3IoCiAgICAiW2RhdGEtYXVyYS1hMjAwLXN0YXR1c10iCiAgKTsKICBjb25zb2xlLmxvZygKICAgICJSMjJfU1RBVFVTX01PREVfQUZURVI9IiArCiAgICAoc3RhdHVzTm9kZS5kYXRhc2V0Lm1vZGUgfHwgIiIpCiAgKTsKCiAgY29uc29sZS5sb2coIlIyMl9ERVBMT1lFRF9MSVZFX0FQUFJPVkFMX1BBU1M9dHJ1ZSIpOwp9KSgpLmNhdGNoKChlcnIpID0+IHsKICBjb25zb2xlLmVycm9yKGVyciAmJiBlcnIuc3RhY2sgPyBlcnIuc3RhY2sgOiBTdHJpbmcoZXJyKSk7CiAgcHJvY2Vzcy5leGl0Q29kZSA9IDE7Cn0pOwo="

checks = []
real_mutation_performed = False
final_state_restored = False


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
        add(
            name,
            False,
            f"wrong exception {type(exc).__name__}: {exc}",
        )
    else:
        add(name, False, "no exception")


user32 = ctypes.windll.user32


def window_title(hwnd: int) -> str:
    length = int(user32.GetWindowTextLengthW(int(hwnd)))
    buf = ctypes.create_unicode_buffer(max(length + 2, 2))
    user32.GetWindowTextW(int(hwnd), buf, len(buf))
    return buf.value


def window_snapshot(hwnd: int) -> dict:
    return {
        "exists": bool(user32.IsWindow(int(hwnd))),
        "title": window_title(int(hwnd)),
        "iconic": bool(user32.IsIconic(int(hwnd))),
        "zoomed": bool(user32.IsZoomed(int(hwnd))),
        "foreground": int(user32.GetForegroundWindow()) == int(hwnd),
    }


marker = str(
    os.environ.get("AURA_A200_R22_CONSOLE_MARKER") or ""
).strip()
run_token = str(
    os.environ.get("AURA_A200_R22_RUN_TOKEN") or ""
).strip()
human_approved = (
    os.environ.get("AURA_A200_R22_USER_APPROVED") == "YES"
)

add(
    "R22 marker",
    A200_R22_MARKER
    == "AURA_A200_R22_CONTROLLED_LIVE_UI_APPROVAL_SELF_WINDOW_RESTORE_V1",
)
add("R22 self-window only", LIVE_SELF_WINDOW_ONLY is True)
add(
    "R22 explicit human approval mandatory",
    EXPLICIT_HUMAN_APPROVAL_REQUIRED is True,
)
add(
    "R22 deployed R17 confirmation mandatory",
    EXPLICIT_R17_UI_CONFIRMATION_REQUIRED is True,
)
add(
    "R22 single reversible mutation required",
    SINGLE_REVERSIBLE_MUTATION_REQUIRED is True,
)
add("R22 live capability exact", LIVE_CAPABILITY == "pc.minimize_window")
add(
    "R22 automatic exact restore mandatory",
    AUTOMATIC_EXACT_RESTORE_REQUIRED is True,
)
add("R22 approval one-use mandatory", APPROVAL_ONE_USE_REQUIRED is True)
add(
    "R22 canonical receipts mandatory",
    CANONICAL_RECEIPTS_REQUIRED is True,
)
add(
    "R22 MissionEngine completion mandatory",
    MISSIONENGINE_COMPLETION_REQUIRED is True,
)
add(
    "R22 crash journal clear mandatory",
    CRASH_JOURNAL_CLEAR_REQUIRED is True,
)
add(
    "R22 direct NL execution disabled",
    DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED is False,
)
add("R22 auto approval disabled", AUTO_APPROVAL_ENABLED is False)
add("R22 auto cancel disabled", AUTO_CANCEL_ENABLED is False)
add("R22 autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add(
    "R22 autonomous multi-mutation disabled",
    AUTONOMOUS_MULTI_MUTATION_ENABLED is False,
)
add("R22 destructive disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("R22 close disabled", CLOSE_WINDOW_ENABLED is False)
add("R22 terminate disabled", TERMINATE_PROCESS_ENABLED is False)
add("R22 runtime shell disabled", SHELL_EXECUTION_ENABLED is False)
add("R22 console marker present", bool(marker), marker)
add("R22 run token present", bool(run_token), run_token)
add("R22 explicit human approval received", human_approved is True)
assert_r22_safety_contract()
add("R22 safety contract assertion", True)

if not human_approved:
    raise R22AcceptanceDenied("human approval missing")

foreground_before = int(user32.GetForegroundWindow())
add("R22 foreground HWND exists", foreground_before > 0, foreground_before)
snapshot_before = window_snapshot(foreground_before)
add("R22 foreground title exact marker", snapshot_before["title"] == marker, snapshot_before["title"])
add("R22 target initially exists", snapshot_before["exists"] is True)
add("R22 target initially not minimized", snapshot_before["iconic"] is False)
add("R22 target initially foreground", snapshot_before["foreground"] is True)

if snapshot_before["title"] != marker:
    raise R22AcceptanceDenied(
        "foreground window is not the uniquely titled R22 console"
    )

state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r22_live_"))
lifecycle = None
intent_host = None
mission_id = ""
approval_id = ""
presentation_digest = ""
target_hwnd = 0

try:
    token = TOKEN_FILE.read_text(encoding="ascii").strip()

    lifecycle = A200UiHostLifecycle(
        state_root=state_root / "runtime",
        token=token,
        host="127.0.0.1",
        port=18765,
        owner_id="r22-live-" + run_token,
    )
    lifecycle.start()

    intent_host = A200IntentPreviewHost(
        token=token,
        host="127.0.0.1",
        port=18766,
        lock_file=state_root / "intent.lock",
    )
    intent_host.start()

    receipts_before = len(
        lifecycle._transport.runtime.receipts.list_receipts()
    )
    add("R22 acceptance starts with zero receipts", receipts_before == 0, receipts_before)

    node = shutil.which("node")
    add("Node available for R22 deployed live journey", bool(node), node or "MISSING")
    if not node:
        raise RuntimeError("Node required for R22 deployed live journey")

    harness = state_root / "r22_live_approval.js"
    harness.write_bytes(base64.b64decode(NODE_HARNESS_B64))

    print(
        "[INFO] R22 will now minimize THIS uniquely titled console once.",
        flush=True,
    )
    print(
        "[INFO] The deployed R17 approval button path is used, then W132 exact restore is mandatory.",
        flush=True,
    )

    cp = subprocess.run(
        [
            node,
            str(harness),
            str(R17),
            str(R18),
            str(R20),
            str(R21),
            marker,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=35,
    )
    for line in (cp.stdout or "").splitlines():
        print("  node: " + line)

    add("R22 deployed live journey Node PASS", cp.returncode == 0, f"exit={cp.returncode}")
    add("R22 deployed composer bound", "R22_COMPOSER_BOUND=true" in cp.stdout)
    add("R22 supervised preview reached", "R22_PREVIEW_KIND=supervised_mutation" in cp.stdout)
    add("R22 preview remains non-executable", "R22_PREVIEW_EXECUTABLE=false" in cp.stdout)
    add("R22 preview digest SHA256", "R22_PLAN_DIGEST_LEN=64" in cp.stdout)
    add("R22 target marker exact", "R22_TARGET_MARKER_MATCH=true" in cp.stdout)
    add("R22 approval.confirm emitted exactly once", "R22_APPROVAL_CONFIRM_COUNT=1" in cp.stdout)
    add("R22 approval.confirm exact binding", "R22_APPROVAL_CONFIRM_BOUND=true" in cp.stdout)
    add("R22 approval completed mission", "R22_APPROVAL_COMPLETED_STATUS=completed" in cp.stdout)
    add("R22 R17 approval dialog closed", "R22_R17_DIALOG_HIDDEN_AFTER=true" in cp.stdout)
    add("R22 deployed live approval marker", "R22_DEPLOYED_LIVE_APPROVAL_PASS=true" in cp.stdout)

    def parse_line(name: str) -> str:
        match = re.search(rf"^{re.escape(name)}=(.+)$", cp.stdout, flags=re.MULTILINE)
        return "" if not match else match.group(1).strip()

    mission_id = parse_line("R22_MISSION_ID")
    approval_id = parse_line("R22_APPROVAL_ID")
    presentation_digest = parse_line("R22_PRESENTATION_DIGEST")
    target_text = parse_line("R22_TARGET_HWND")
    try:
        target_hwnd = int(target_text)
    except Exception:
        target_hwnd = 0

    add("R22 mission id parsed", bool(mission_id), mission_id or "MISSING")
    add("R22 approval id parsed", bool(approval_id), approval_id or "MISSING")
    add(
        "R22 presentation digest parsed",
        len(presentation_digest) == 64,
        str(len(presentation_digest)),
    )
    add("R22 target hwnd parsed", target_hwnd > 0, target_hwnd)
    add("R22 target is exact original foreground", target_hwnd == foreground_before, f"{target_hwnd} vs {foreground_before}")

    mission = lifecycle._transport.runtime.engine.get_mission(mission_id)
    add("R22 MissionEngine mission completed", str(mission.status) == "completed", str(mission.status))
    add("R22 mission has five tasks", len(mission.tasks) == 5, len(mission.tasks))
    add(
        "R22 all five tasks succeeded",
        all(str(task.status) == "succeeded" for task in mission.tasks.values()),
        {task.key: str(task.status) for task in mission.tasks.values()},
    )

    observe_before = task_by_key(mission, "observe_before")
    minimize_task = task_by_key(mission, "minimize_once")
    observe_mutated = task_by_key(mission, "observe_mutated")
    restore_task = task_by_key(mission, "restore_exact")
    observe_final = task_by_key(mission, "observe_final")

    add(
        "R22 observe_before saw target foreground",
        foreground_hwnd(observe_before.result) == target_hwnd,
        foreground_hwnd(observe_before.result),
    )
    add(
        "R22 observe_mutated saw target leave foreground",
        foreground_hwnd(observe_mutated.result) != target_hwnd,
        foreground_hwnd(observe_mutated.result),
    )
    add(
        "R22 observe_final saw target foreground restored",
        foreground_hwnd(observe_final.result) == target_hwnd,
        foreground_hwnd(observe_final.result),
    )

    mutation_result = minimize_task.result if isinstance(minimize_task.result, dict) else {}
    restore_result = restore_task.result if isinstance(restore_task.result, dict) else {}
    mutation_receipt_id = str(mutation_result.get("receipt_id") or "")
    restore_receipt_id = str(restore_result.get("receipt_id") or "")

    add("R22 mutation canonical receipt present", bool(mutation_receipt_id), mutation_receipt_id)
    add("R22 restore canonical receipt present", bool(restore_receipt_id), restore_receipt_id)
    add("R22 mutation/restore receipts differ", mutation_receipt_id != restore_receipt_id)

    mutation_receipt = lifecycle._transport.runtime.receipts.get_receipt(mutation_receipt_id)
    restore_receipt = lifecycle._transport.runtime.receipts.get_receipt(restore_receipt_id)
    add("R22 mutation receipt succeeded", mutation_receipt.status == "succeeded", mutation_receipt.status)
    add("R22 restore receipt succeeded", restore_receipt.status == "succeeded", restore_receipt.status)

    mission_receipt_ids = []
    for task in mission.tasks.values():
        result = task.result if isinstance(task.result, dict) else {}
        rid = str(result.get("receipt_id") or "")
        if rid:
            mission_receipt_ids.append(rid)

    add("R22 five mission tasks own five receipts", len(mission_receipt_ids) == 5, mission_receipt_ids)
    add("R22 five mission receipt ids unique", len(set(mission_receipt_ids)) == 5)
    add(
        "R22 all mission receipts succeeded",
        all(
            lifecycle._transport.runtime.receipts.get_receipt(rid).status
            == "succeeded"
            for rid in mission_receipt_ids
        ),
    )

    receipts_after = len(
        lifecycle._transport.runtime.receipts.list_receipts()
    )
    add(
        "R22 journey creates exactly six canonical receipts",
        receipts_after == receipts_before + 6,
        f"{receipts_before}->{receipts_after}",
    )

    real_mutation_performed = (
        mutation_receipt.status == "succeeded"
        and foreground_hwnd(observe_mutated.result) != target_hwnd
    )
    print(
        f"R22_REAL_MUTATION_PERFORMED = {real_mutation_performed}",
        flush=True,
    )
    add("R22 real reversible mutation proved", real_mutation_performed is True)

    challenge = lifecycle._transport.ingress.approval_store.get(approval_id)
    add("R22 approval challenge still queryable", challenge is not None)
    if challenge is not None:
        add("R22 approval challenge consumed", challenge.state == "consumed", challenge.state)
        add("R22 approval challenge session exact", challenge.session_id == lifecycle._transport.runtime.session_id)

    add(
        "R22 crash recovery journal clear",
        lifecycle._transport.runtime.crash_journal.get_pending(mission_id) is None,
    )

    receipts_before_replay = len(
        lifecycle._transport.runtime.receipts.list_receipts()
    )

    must_raise(
        "R22 consumed approval cannot be replayed",
        UiApprovalPresentationError,
        lambda: lifecycle._transport.bridge.handle(
            {
                "type": "approval.confirm",
                "approval_id": approval_id,
                "presentation_digest": presentation_digest,
                "confirm": True,
            }
        ),
    )

    add(
        "R22 replay creates no receipt",
        len(lifecycle._transport.runtime.receipts.list_receipts())
        == receipts_before_replay,
    )

    # Give W132/foreground restoration a short deterministic settle window.
    final_snapshot = None
    for _ in range(20):
        final_snapshot = window_snapshot(target_hwnd)
        if (
            final_snapshot["exists"]
            and final_snapshot["title"] == marker
            and final_snapshot["iconic"] == snapshot_before["iconic"]
            and final_snapshot["zoomed"] == snapshot_before["zoomed"]
            and final_snapshot["foreground"]
        ):
            break
        time.sleep(0.1)

    add("R22 final target still exists", final_snapshot["exists"] is True)
    add("R22 final title exact", final_snapshot["title"] == marker, final_snapshot["title"])
    add(
        "R22 final minimized state exact",
        final_snapshot["iconic"] == snapshot_before["iconic"],
        f"{snapshot_before['iconic']}->{final_snapshot['iconic']}",
    )
    add(
        "R22 final maximized state exact",
        final_snapshot["zoomed"] == snapshot_before["zoomed"],
        f"{snapshot_before['zoomed']}->{final_snapshot['zoomed']}",
    )
    add("R22 exact foreground restored", final_snapshot["foreground"] is True)

    final_state_restored = all(
        [
            final_snapshot["exists"],
            final_snapshot["title"] == marker,
            final_snapshot["iconic"] == snapshot_before["iconic"],
            final_snapshot["zoomed"] == snapshot_before["zoomed"],
            final_snapshot["foreground"],
        ]
    )
    print(
        f"R22_FINAL_STATE_RESTORED = {final_state_restored}",
        flush=True,
    )

finally:
    if intent_host is not None:
        intent_host.close()
    if lifecycle is not None:
        lifecycle.close()
    shutil.rmtree(state_root, ignore_errors=True)

src = (
    ROOT / "runtime" / "aura_deployed_live_approval_acceptance_v200.py"
).read_text(encoding="utf-8-sig", errors="replace")
add("R22 guard source contains no subprocess", "import subprocess" not in src and "from subprocess" not in src)
add("R22 guard source contains no shell API", all(token not in src for token in ("os.system(", "os.popen(", "ctypes.", "child_process")))
add("R22 guard source contains no close capability", "pc.close_window" not in src)
add("R22 guard source contains no terminate capability", "pc.terminate_process" not in src)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R22_REAL_MUTATION_PERFORMED = {real_mutation_performed}")
print(f"R22_FINAL_STATE_RESTORED = {final_state_restored}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if not real_mutation_performed:
    raise SystemExit("R22 required one real reversible mutation")
if not final_state_restored:
    raise SystemExit("R22 exact final state was not restored")
print("[PASS] A200-R22 deployed explicit UI approval + one real reversible self-window mutation + exact restore")
