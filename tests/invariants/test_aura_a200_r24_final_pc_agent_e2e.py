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

from runtime.aura_final_pc_agent_e2e_acceptance_v200 import (
    A200_R24_MARKER,
    APPROVAL_ONE_USE_REQUIRED,
    AUTO_APPROVAL_ENABLED,
    AUTO_CANCEL_ENABLED,
    AUTONOMOUS_MULTI_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    CLOSE_WINDOW_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED,
    EXACT_W132_RESTORE_REQUIRED,
    EXPECTED_RECEIPT_COUNT,
    EXPLICIT_HUMAN_APPROVAL_REQUIRED,
    EXPLICIT_R17_CONFIRM_REQUIRED,
    FINAL_RUNTIME_READY_REQUIRED,
    LIVE_CAPABILITY,
    MISSIONENGINE_EVIDENCE_REQUIRED,
    MISSION_TASK_COUNT_REQUIRED,
    NO_PENDING_RECOVERY_REQUIRED,
    PLAN_PREVIEW_MUST_BE_NON_EXECUTABLE,
    SELF_WINDOW_ONLY,
    SHELL_EXECUTION_ENABLED,
    SINGLE_LIVE_MUTATION_MAX,
    TERMINATE_PROCESS_ENABLED,
    assert_r24_safety_contract,
    foreground_hwnd_from_task,
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
NODE_HARNESS_B64 = "Y29uc3QgZnMgPSByZXF1aXJlKCJmcyIpOwpjb25zdCBodHRwID0gcmVxdWlyZSgiaHR0cCIpOwpjb25zdCB2bSA9IHJlcXVpcmUoInZtIik7Cgpjb25zdCBSMTcgPSBwcm9jZXNzLmFyZ3ZbMl07CmNvbnN0IFIxOCA9IHByb2Nlc3MuYXJndlszXTsKY29uc3QgUjIwID0gcHJvY2Vzcy5hcmd2WzRdOwpjb25zdCBSMjEgPSBwcm9jZXNzLmFyZ3ZbNV07CmNvbnN0IFNFTEZfTUFSS0VSID0gcHJvY2Vzcy5hcmd2WzZdIHx8ICIiOwoKY29uc3QgbGlzdGVuZXJzID0gbmV3IE1hcCgpOwpjb25zdCByZXF1ZXN0QXVkaXQgPSBbXTsKCmNsYXNzIEN1c3RvbUV2ZW50IHsKICBjb25zdHJ1Y3Rvcih0eXBlLCBvcHRpb25zID0ge30pIHsKICAgIHRoaXMudHlwZSA9IHR5cGU7CiAgICB0aGlzLmRldGFpbCA9IG9wdGlvbnMuZGV0YWlsOwogIH0KfQoKY2xhc3MgRmFrZU11dGF0aW9uT2JzZXJ2ZXIgewogIGNvbnN0cnVjdG9yKGZuKSB7IHRoaXMuZm4gPSBmbjsgfQogIG9ic2VydmUoKSB7fQogIGRpc2Nvbm5lY3QoKSB7fQp9Cmdsb2JhbC5NdXRhdGlvbk9ic2VydmVyID0gRmFrZU11dGF0aW9uT2JzZXJ2ZXI7CgpmdW5jdGlvbiBhZGRXaW5kb3dMaXN0ZW5lcih0eXBlLCBmbikgewogIGlmICghbGlzdGVuZXJzLmhhcyh0eXBlKSkgbGlzdGVuZXJzLnNldCh0eXBlLCBbXSk7CiAgbGlzdGVuZXJzLmdldCh0eXBlKS5wdXNoKGZuKTsKfQoKZnVuY3Rpb24gZGlzcGF0Y2hXaW5kb3coZXZlbnQpIHsKICBpZiAoZXZlbnQudHlwZSA9PT0gImF1cmE6YTIwMC1zdXBlcnZpc2VkLXJlcXVlc3QiKSB7CiAgICByZXF1ZXN0QXVkaXQucHVzaChKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KGV2ZW50LmRldGFpbCB8fCB7fSkpKTsKICB9CiAgZm9yIChjb25zdCBmbiBvZiBbLi4uKGxpc3RlbmVycy5nZXQoZXZlbnQudHlwZSkgfHwgW10pXSkgewogICAgZm4uY2FsbCh3aW5kb3csIGV2ZW50KTsKICB9CiAgcmV0dXJuIHRydWU7Cn0KCmNsYXNzIEZha2VOb2RlIHsKICBjb25zdHJ1Y3RvcihzZWxlY3RvciA9ICIiKSB7CiAgICB0aGlzLnNlbGVjdG9yID0gc2VsZWN0b3I7CiAgICB0aGlzLmRhdGFzZXQgPSB7fTsKICAgIHRoaXMudGV4dENvbnRlbnQgPSAiIjsKICAgIHRoaXMuaGlkZGVuID0gZmFsc2U7CiAgICB0aGlzLmRpc2FibGVkID0gZmFsc2U7CiAgICB0aGlzLmlkID0gIiI7CiAgICB0aGlzLnR5cGUgPSAiIjsKICAgIHRoaXMudmFsdWUgPSAiIjsKICAgIHRoaXMucGFyZW50RWxlbWVudCA9IG51bGw7CiAgICB0aGlzLmNoaWxkcmVuID0gW107CiAgICB0aGlzLmV2ZW50cyA9IHt9OwogICAgdGhpcy5fYXR0cnMgPSB7fTsKICAgIHRoaXMuX3F1ZXJpZXMgPSBuZXcgTWFwKCk7CiAgfQogIGFkZEV2ZW50TGlzdGVuZXIodHlwZSwgZm4pIHsKICAgIGlmICghdGhpcy5ldmVudHNbdHlwZV0pIHRoaXMuZXZlbnRzW3R5cGVdID0gW107CiAgICB0aGlzLmV2ZW50c1t0eXBlXS5wdXNoKGZuKTsKICB9CiAgY2xpY2soKSB7CiAgICBmb3IgKGNvbnN0IGZuIG9mIHRoaXMuZXZlbnRzLmNsaWNrIHx8IFtdKSB7CiAgICAgIGZuLmNhbGwodGhpcywgeyB0eXBlOiAiY2xpY2siLCB0YXJnZXQ6IHRoaXMgfSk7CiAgICB9CiAgfQogIHNldEF0dHJpYnV0ZShuYW1lLCB2YWx1ZSkgewogICAgdGhpcy5fYXR0cnNbbmFtZV0gPSBTdHJpbmcodmFsdWUpOwogIH0KICBoYXNBdHRyaWJ1dGUobmFtZSkgewogICAgcmV0dXJuIE9iamVjdC5wcm90b3R5cGUuaGFzT3duUHJvcGVydHkuY2FsbCh0aGlzLl9hdHRycywgbmFtZSk7CiAgfQogIGFwcGVuZENoaWxkKG5vZGUpIHsKICAgIG5vZGUucGFyZW50RWxlbWVudCA9IHRoaXM7CiAgICB0aGlzLmNoaWxkcmVuLnB1c2gobm9kZSk7CiAgICBpZiAobm9kZS5pZCkgZG9jdW1lbnQuX2J5SWQuc2V0KG5vZGUuaWQsIG5vZGUpOwogICAgcmV0dXJuIG5vZGU7CiAgfQogIHF1ZXJ5U2VsZWN0b3Ioc2VsZWN0b3IpIHsKICAgIGlmIChzZWxlY3RvciA9PT0gIltkYXRhLWF1cmEtYTIwMC1yMjEtcGxhbl0iKSB7CiAgICAgIHJldHVybiB0aGlzLmNoaWxkcmVuLmZpbmQoCiAgICAgICAgbiA9PiBuLmhhc0F0dHJpYnV0ZSAmJgogICAgICAgICAgbi5oYXNBdHRyaWJ1dGUoImRhdGEtYXVyYS1hMjAwLXIyMS1wbGFuIikKICAgICAgKSB8fCBudWxsOwogICAgfQogICAgaWYgKCF0aGlzLl9xdWVyaWVzLmhhcyhzZWxlY3RvcikpIHsKICAgICAgdGhpcy5fcXVlcmllcy5zZXQoc2VsZWN0b3IsIG5ldyBGYWtlTm9kZShzZWxlY3RvcikpOwogICAgfQogICAgcmV0dXJuIHRoaXMuX3F1ZXJpZXMuZ2V0KHNlbGVjdG9yKTsKICB9Cn0KCmNsYXNzIEZha2VSb290IGV4dGVuZHMgRmFrZU5vZGUgewogIGNvbnN0cnVjdG9yKCkgewogICAgc3VwZXIoInJvb3QiKTsKICAgIHRoaXMuX2h0bWwgPSAiIjsKICB9CiAgc2V0IGlubmVySFRNTCh2YWx1ZSkgeyB0aGlzLl9odG1sID0gdmFsdWU7IH0KICBnZXQgaW5uZXJIVE1MKCkgeyByZXR1cm4gdGhpcy5faHRtbDsgfQp9Cgpjb25zdCBjb21wb3NlclBhcmVudCA9IG5ldyBGYWtlTm9kZSgiY29tcG9zZXItcGFyZW50Iik7CmNvbnN0IGNvbXBvc2VySW5wdXQgPSBuZXcgRmFrZU5vZGUoImNvbXBvc2VyLWlucHV0Iik7CmNvbXBvc2VyUGFyZW50LmFwcGVuZENoaWxkKGNvbXBvc2VySW5wdXQpOwoKZ2xvYmFsLkN1c3RvbUV2ZW50ID0gQ3VzdG9tRXZlbnQ7Cmdsb2JhbC53aW5kb3cgPSB7CiAgYWRkRXZlbnRMaXN0ZW5lcjogYWRkV2luZG93TGlzdGVuZXIsCiAgZGlzcGF0Y2hFdmVudDogZGlzcGF0Y2hXaW5kb3cKfTsKCmdsb2JhbC5kb2N1bWVudCA9IHsKICByZWFkeVN0YXRlOiAiY29tcGxldGUiLAogIF9ieUlkOiBuZXcgTWFwKCksCiAgYm9keTogbmV3IEZha2VOb2RlKCJib2R5IiksCiAgY29udGFpbnMobm9kZSkgeyByZXR1cm4gISFub2RlOyB9LAogIGdldEVsZW1lbnRCeUlkKGlkKSB7CiAgICByZXR1cm4gdGhpcy5fYnlJZC5nZXQoaWQpIHx8IG51bGw7CiAgfSwKICBjcmVhdGVFbGVtZW50KHRhZykgewogICAgcmV0dXJuIHRhZyA9PT0gInNlY3Rpb24iID8gbmV3IEZha2VSb290KCkgOiBuZXcgRmFrZU5vZGUodGFnKTsKICB9LAogIGFkZEV2ZW50TGlzdGVuZXIoKSB7fSwKICBxdWVyeVNlbGVjdG9yKHNlbGVjdG9yKSB7CiAgICBpZiAoc2VsZWN0b3IgPT09ICJbZGF0YS1hdXJhLWNvbXBvc2VyXSB0ZXh0YXJlYSIpIHsKICAgICAgcmV0dXJuIGNvbXBvc2VySW5wdXQ7CiAgICB9CiAgICByZXR1cm4gbnVsbDsKICB9Cn07Cgpkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkID0gZnVuY3Rpb24obm9kZSkgewogIG5vZGUucGFyZW50RWxlbWVudCA9IHRoaXM7CiAgdGhpcy5jaGlsZHJlbi5wdXNoKG5vZGUpOwogIGlmIChub2RlLmlkKSBkb2N1bWVudC5fYnlJZC5zZXQobm9kZS5pZCwgbm9kZSk7CiAgcmV0dXJuIG5vZGU7Cn07CgpmdW5jdGlvbiBmZXRjaFdpdGhPbmVSZXRyeSh1cmwsIG9wdGlvbnMgPSB7fSwgYXR0ZW1wdCA9IDApIHsKICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4gewogICAgY29uc3QgdSA9IG5ldyBVUkwodXJsKTsKICAgIGNvbnN0IGJvZHkgPSBvcHRpb25zLmJvZHkgfHwgIiI7CiAgICBjb25zdCBoZWFkZXJzID0gT2JqZWN0LmFzc2lnbih7fSwgb3B0aW9ucy5oZWFkZXJzIHx8IHt9KTsKICAgIGhlYWRlcnNbIkNvbnRlbnQtTGVuZ3RoIl0gPSBCdWZmZXIuYnl0ZUxlbmd0aChib2R5KTsKICAgIGlmICghT2JqZWN0LmtleXMoaGVhZGVycykuc29tZShrID0+IGsudG9Mb3dlckNhc2UoKSA9PT0gIm9yaWdpbiIpKSB7CiAgICAgIGhlYWRlcnNbIk9yaWdpbiJdID0gIm51bGwiOwogICAgfQoKICAgIGNvbnN0IHJlcSA9IGh0dHAucmVxdWVzdCgKICAgICAgewogICAgICAgIGhvc3RuYW1lOiB1Lmhvc3RuYW1lLAogICAgICAgIHBvcnQ6IHUucG9ydCwKICAgICAgICBwYXRoOiB1LnBhdGhuYW1lICsgdS5zZWFyY2gsCiAgICAgICAgbWV0aG9kOiBvcHRpb25zLm1ldGhvZCB8fCAiR0VUIiwKICAgICAgICBoZWFkZXJzCiAgICAgIH0sCiAgICAgIChyZXMpID0+IHsKICAgICAgICBsZXQgZGF0YSA9ICIiOwogICAgICAgIHJlcy5zZXRFbmNvZGluZygidXRmOCIpOwogICAgICAgIHJlcy5vbigiZGF0YSIsIGNodW5rID0+IGRhdGEgKz0gY2h1bmspOwogICAgICAgIHJlcy5vbigiZW5kIiwgKCkgPT4gewogICAgICAgICAgcmVzb2x2ZSh7CiAgICAgICAgICAgIG9rOiByZXMuc3RhdHVzQ29kZSA+PSAyMDAgJiYgcmVzLnN0YXR1c0NvZGUgPCAzMDAsCiAgICAgICAgICAgIHN0YXR1czogcmVzLnN0YXR1c0NvZGUsCiAgICAgICAgICAgIGFzeW5jIGpzb24oKSB7CiAgICAgICAgICAgICAgcmV0dXJuIEpTT04ucGFyc2UoZGF0YSB8fCAie30iKTsKICAgICAgICAgICAgfQogICAgICAgICAgfSk7CiAgICAgICAgfSk7CiAgICAgIH0KICAgICk7CgogICAgcmVxLm9uKCJlcnJvciIsIChlcnIpID0+IHsKICAgICAgY29uc3QgdHJhbnNpZW50ID0KICAgICAgICBlcnIgJiYKICAgICAgICAoZXJyLmNvZGUgPT09ICJFQ09OTlJFU0VUIiB8fAogICAgICAgICBlcnIuY29kZSA9PT0gIkVDT05OQUJPUlRFRCIpOwogICAgICBpZiAodHJhbnNpZW50ICYmIGF0dGVtcHQgPCAxKSB7CiAgICAgICAgc2V0VGltZW91dCgoKSA9PiB7CiAgICAgICAgICBmZXRjaFdpdGhPbmVSZXRyeSh1cmwsIG9wdGlvbnMsIGF0dGVtcHQgKyAxKQogICAgICAgICAgICAudGhlbihyZXNvbHZlLCByZWplY3QpOwogICAgICAgIH0sIDE1MCk7CiAgICAgICAgcmV0dXJuOwogICAgICB9CiAgICAgIHJlamVjdChlcnIpOwogICAgfSk7CgogICAgaWYgKGJvZHkpIHJlcS53cml0ZShib2R5KTsKICAgIHJlcS5lbmQoKTsKICB9KTsKfQpnbG9iYWwuZmV0Y2ggPSBmZXRjaFdpdGhPbmVSZXRyeTsKCmxldCBzdGF0dXNSZXNwb25zZXMgPSBbXTsKbGV0IHJlYWRSZXNwb25zZXMgPSBbXTsKbGV0IGFwcHJvdmFsUmVxdWlyZWQgPSBudWxsOwpsZXQgYXBwcm92YWxDb21wbGV0ZWQgPSBudWxsOwoKd2luZG93LmFkZEV2ZW50TGlzdGVuZXIoImF1cmE6YTIwMC1zdXBlcnZpc2VkLXJlc3BvbnNlIiwgKGV2ZW50KSA9PiB7CiAgY29uc3QgZCA9IGV2ZW50LmRldGFpbCB8fCB7fTsKICBpZiAoZC5raW5kID09PSAicnVudGltZS5zdGF0dXMiKSBzdGF0dXNSZXNwb25zZXMucHVzaChkKTsKICBpZiAoZC5raW5kID09PSAicGMucmVhZF9mb3JlZ3JvdW5kIikgcmVhZFJlc3BvbnNlcy5wdXNoKGQpOwogIGlmIChkLmtpbmQgPT09ICJhcHByb3ZhbC5yZXF1aXJlZCIpIGFwcHJvdmFsUmVxdWlyZWQgPSBkOwogIGlmIChkLmtpbmQgPT09ICJhcHByb3ZhbC5jb21wbGV0ZWQiKSBhcHByb3ZhbENvbXBsZXRlZCA9IGQ7Cn0pOwoKZnVuY3Rpb24gd2FpdEZvcihwcmVkaWNhdGUsIHRpbWVvdXRNcykgewogIGNvbnN0IHN0YXJ0ID0gRGF0ZS5ub3coKTsKICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4gewogICAgY29uc3QgdGltZXIgPSBzZXRJbnRlcnZhbCgoKSA9PiB7CiAgICAgIHRyeSB7CiAgICAgICAgaWYgKHByZWRpY2F0ZSgpKSB7CiAgICAgICAgICBjbGVhckludGVydmFsKHRpbWVyKTsKICAgICAgICAgIHJlc29sdmUoKTsKICAgICAgICAgIHJldHVybjsKICAgICAgICB9CiAgICAgICAgaWYgKERhdGUubm93KCkgLSBzdGFydCA+IHRpbWVvdXRNcykgewogICAgICAgICAgY2xlYXJJbnRlcnZhbCh0aW1lcik7CiAgICAgICAgICByZWplY3QobmV3IEVycm9yKCJ0aW1lb3V0IikpOwogICAgICAgIH0KICAgICAgfSBjYXRjaCAoZXJyKSB7CiAgICAgICAgY2xlYXJJbnRlcnZhbCh0aW1lcik7CiAgICAgICAgcmVqZWN0KGVycik7CiAgICAgIH0KICAgIH0sIDI1KTsKICB9KTsKfQoKZnVuY3Rpb24gbmVzdGVkSHduZCh2YWx1ZSkgewogIGNvbnN0IHNlZW4gPSBuZXcgU2V0KCk7CiAgZnVuY3Rpb24gdmlzaXQobm9kZSkgewogICAgaWYgKCFub2RlIHx8IHR5cGVvZiBub2RlICE9PSAib2JqZWN0IikgcmV0dXJuIDA7CiAgICBpZiAoc2Vlbi5oYXMobm9kZSkpIHJldHVybiAwOwogICAgc2Vlbi5hZGQobm9kZSk7CiAgICBpZiAoTnVtYmVyLmlzSW50ZWdlcihub2RlLmh3bmQpICYmIG5vZGUuaHduZCA+IDApIHsKICAgICAgcmV0dXJuIG5vZGUuaHduZDsKICAgIH0KICAgIGZvciAoY29uc3QgY2hpbGQgb2YgT2JqZWN0LnZhbHVlcyhub2RlKSkgewogICAgICBjb25zdCBmb3VuZCA9IHZpc2l0KGNoaWxkKTsKICAgICAgaWYgKGZvdW5kKSByZXR1cm4gZm91bmQ7CiAgICB9CiAgICByZXR1cm4gMDsKICB9CiAgcmV0dXJuIHZpc2l0KHZhbHVlKTsKfQoKKGFzeW5jICgpID0+IHsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMTgsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIxOCB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMTcsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIxNyB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMjAsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIyMCB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMjEsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIyMSB9KTsKCiAgYXdhaXQgd2FpdEZvcigoKSA9PiBzdGF0dXNSZXNwb25zZXMubGVuZ3RoID49IDEsIDUwMDApOwogIGlmIChzdGF0dXNSZXNwb25zZXNbMF0ub2sgIT09IHRydWUpIHsKICAgIHRocm93IG5ldyBFcnJvcigiaW5pdGlhbCBydW50aW1lLnN0YXR1cyBmYWlsZWQiKTsKICB9CiAgY29uc29sZS5sb2coIlIyNF9JTklUSUFMX1NUQVRVU19SRUFEWT10cnVlIik7CgogIGNvbnN0IGludGVudEFwaSA9IHdpbmRvdy5BVVJBX0EyMDBfSU5URU5UX0hBTkRPRkY7CiAgY29uc3Qgc2VhbSA9IHdpbmRvdy5BVVJBX0EyMDBfQ09NUE9TRVJfU1VQRVJWSVNJT047CiAgaWYgKCFpbnRlbnRBcGkgfHwgIXNlYW0pIHsKICAgIHRocm93IG5ldyBFcnJvcigiUjIwL1IyMSBkZXBsb3llZCBBUElzIHVuYXZhaWxhYmxlIik7CiAgfQoKICAvLyAxKSBVc2VyIHJlYWQtb25seSBpbnRlbnQgYmVmb3JlIHRoZSBtaXNzaW9uLgogIGNvbnN0IHByZVByZXZpZXcgPSBhd2FpdCBpbnRlbnRBcGkucHJldmlldygKICAgICJxdWVsbGUgZmVuw6p0cmUgZXN0IGFjdGl2ZSA/IgogICk7CiAgaWYgKAogICAgcHJlUHJldmlldy5pbnRlbnRfa2luZCAhPT0gInJlYWRfZm9yZWdyb3VuZCIgfHwKICAgIHByZVByZXZpZXcuZXhlY3V0aW9uX2FsbG93ZWQgIT09IHRydWUKICApIHsKICAgIHRocm93IG5ldyBFcnJvcigicHJlLW1pc3Npb24gcmVhZCBwcmV2aWV3IGludmFsaWQiKTsKICB9CiAgY29uc3QgcHJlUmVhZENvdW50ID0gcmVhZFJlc3BvbnNlcy5sZW5ndGg7CiAgaW50ZW50QXBpLmV4ZWN1dGVBY3RpdmVSZWFkT25seSgpOwogIGF3YWl0IHdhaXRGb3IoKCkgPT4gcmVhZFJlc3BvbnNlcy5sZW5ndGggPiBwcmVSZWFkQ291bnQsIDUwMDApOwogIGNvbnN0IHByZVJlYWQgPSByZWFkUmVzcG9uc2VzW3JlYWRSZXNwb25zZXMubGVuZ3RoIC0gMV07CiAgaWYgKHByZVJlYWQub2sgIT09IHRydWUpIHRocm93IG5ldyBFcnJvcigicHJlLW1pc3Npb24gcmVhZCBmYWlsZWQiKTsKICBjb25zdCBwcmVId25kID0gbmVzdGVkSHduZChwcmVSZWFkKTsKICBjb25zb2xlLmxvZygiUjI0X1BSRV9SRUFEX0hXTkQ9IiArIHByZUh3bmQpOwogIGNvbnNvbGUubG9nKAogICAgIlIyNF9QUkVfUkVBRF9SRUNFSVBUPSIgKwogICAgKCgocHJlUmVhZC5wYXlsb2FkIHx8IHt9KS5yZWNlaXB0X2lkKSB8fCAiIikKICApOwoKICAvLyAyKSBVc2VyIGFza3MgZm9yIGEgc3VwZXJ2aXNlZCByZXZlcnNpYmxlIG11dGF0aW9uIHRocm91Z2ggdGhlIHJlYWwKICAvLyBkZXBsb3llZCBjb21wb3NlciBzZWFtLgogIGNvbXBvc2VySW5wdXQudmFsdWUgPSAibWluaW1pc2UgbGEgZmVuw6p0cmUgYWN0aXZlIjsKICBjb25zdCBib3VuZCA9IHNlYW0uYmluZENvbXBvc2VyKGRvY3VtZW50KTsKICBpZiAoIWJvdW5kKSB0aHJvdyBuZXcgRXJyb3IoImNvbXBvc2VyIGJpbmQgZmFpbGVkIik7CiAgY29uc29sZS5sb2coIlIyNF9DT01QT1NFUl9CT1VORD10cnVlIik7CgogIGNvbnN0IHBsYW5CdXR0b24gPSBjb21wb3NlclBhcmVudC5xdWVyeVNlbGVjdG9yKAogICAgIltkYXRhLWF1cmEtYTIwMC1yMjEtcGxhbl0iCiAgKTsKICBpZiAoIXBsYW5CdXR0b24pIHRocm93IG5ldyBFcnJvcigiUGxhbiBBVVJBIGJ1dHRvbiBtaXNzaW5nIik7CiAgcGxhbkJ1dHRvbi5jbGljaygpOwoKICBhd2FpdCB3YWl0Rm9yKAogICAgKCkgPT4gewogICAgICBjb25zdCBwID0gc2VhbS5nZXRBY3RpdmVQcmV2aWV3KCk7CiAgICAgIHJldHVybiBwICYmIHAuaW50ZW50X2tpbmQgPT09ICJzdXBlcnZpc2VkX211dGF0aW9uIjsKICAgIH0sCiAgICA1MDAwCiAgKTsKICBjb25zdCBtdXRhdGlvblByZXZpZXcgPSBzZWFtLmdldEFjdGl2ZVByZXZpZXcoKTsKICBjb25zb2xlLmxvZygKICAgICJSMjRfTVVUQVRJT05fUFJFVklFV19FWEVDVVRBQkxFPSIgKwogICAgbXV0YXRpb25QcmV2aWV3LmV4ZWN1dGlvbl9hbGxvd2VkCiAgKTsKICBjb25zb2xlLmxvZygKICAgICJSMjRfTVVUQVRJT05fUExBTl9ESUdFU1RfTEVOPSIgKwogICAgU3RyaW5nKG11dGF0aW9uUHJldmlldy5wbGFuX2RpZ2VzdCB8fCAiIikubGVuZ3RoCiAgKTsKICBpZiAobXV0YXRpb25QcmV2aWV3LmV4ZWN1dGlvbl9hbGxvd2VkICE9PSBmYWxzZSkgewogICAgdGhyb3cgbmV3IEVycm9yKCJtdXRhdGlvbiBwcmV2aWV3IG11c3QgYmUgbm9uLWV4ZWN1dGFibGUiKTsKICB9CgogIGNvbnN0IHByZXBhcmVkID0gYXdhaXQgc2VhbS5wcmVwYXJlU3VwZXJ2aXNlZE11dGF0aW9uKCk7CiAgaWYgKAogICAgcHJlcGFyZWQua2luZCAhPT0gImFwcHJvdmFsLnJlcXVpcmVkIiB8fAogICAgKHByZXBhcmVkLnBheWxvYWQgfHwge30pLnBoYXNlICE9PSAid2FpdGluZ19jb25maXJtYXRpb24iCiAgKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoIm1pc3Npb24gZGlkIG5vdCByZWFjaCBhcHByb3ZhbC5yZXF1aXJlZCIpOwogIH0KICBhd2FpdCB3YWl0Rm9yKCgpID0+IGFwcHJvdmFsUmVxdWlyZWQgIT09IG51bGwsIDUwMDApOwoKICBjb25zdCBwcmVzZW50YXRpb24gPSBzZWFtLmdldEFwcHJvdmFsUHJlc2VudGF0aW9uKCk7CiAgY29uc3QgdGFyZ2V0ID0gc2VhbS5nZXRSZXNvbHZlZFRhcmdldCgpIHx8IHt9OwogIGlmICghcHJlc2VudGF0aW9uKSB0aHJvdyBuZXcgRXJyb3IoImFwcHJvdmFsIHByZXNlbnRhdGlvbiBtaXNzaW5nIik7CgogIGNvbnN0IHRhcmdldEV4YWN0ID0KICAgIHRhcmdldC5od25kID09PSBwcmVId25kICYmCiAgICBwcmVzZW50YXRpb24udGFyZ2V0X2h3bmQgPT09IHByZUh3bmQgJiYKICAgIHByZXNlbnRhdGlvbi50YXJnZXRfdGl0bGUgPT09IHRhcmdldC50aXRsZSAmJgogICAgU3RyaW5nKHRhcmdldC50aXRsZSB8fCAiIikudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygKICAgICAgU0VMRl9NQVJLRVIudG9Mb3dlckNhc2UoKQogICAgKTsKICBjb25zb2xlLmxvZygiUjI0X1RBUkdFVF9FWEFDVD0iICsgdGFyZ2V0RXhhY3QpOwogIGlmICghdGFyZ2V0RXhhY3QpIHRocm93IG5ldyBFcnJvcigicmVzb2x2ZWQgdGFyZ2V0IGRyaWZ0ZWQiKTsKCiAgY29uc29sZS5sb2coIlIyNF9NSVNTSU9OX0lEPSIgKyAocHJlc2VudGF0aW9uLm1pc3Npb25faWQgfHwgIiIpKTsKICBjb25zb2xlLmxvZygiUjI0X0FQUFJPVkFMX0lEPSIgKyAocHJlc2VudGF0aW9uLmFwcHJvdmFsX2lkIHx8ICIiKSk7CiAgY29uc29sZS5sb2coCiAgICAiUjI0X1BSRVNFTlRBVElPTl9ESUdFU1Q9IiArCiAgICAocHJlc2VudGF0aW9uLnByZXNlbnRhdGlvbl9kaWdlc3QgfHwgIiIpCiAgKTsKCiAgLy8gMykgT25lIHJlYWwgaHVtYW4tYXBwcm92ZWQgUjE3IGNvbmZpcm1hdGlvbi4KICBjb25zdCByMTdSb290ID0gZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoCiAgICAiYXVyYS1hMjAwLXN1cGVydmlzZWQtcm9vdCIKICApOwogIGNvbnN0IGFwcHJvdmVCdXR0b24gPSByMTdSb290LnF1ZXJ5U2VsZWN0b3IoCiAgICAiW2RhdGEtYXVyYS1hMjAwLWFwcHJvdmVdIgogICk7CiAgY29uc3QgZGlhbG9nID0gcjE3Um9vdC5xdWVyeVNlbGVjdG9yKAogICAgIltkYXRhLWF1cmEtYTIwMC1hcHByb3ZhbF0iCiAgKTsKICBpZiAoIWFwcHJvdmVCdXR0b24gfHwgZGlhbG9nLmhpZGRlbiA9PT0gdHJ1ZSkgewogICAgdGhyb3cgbmV3IEVycm9yKCJSMTcgYXBwcm92YWwgc3VyZmFjZSBub3QgYWN0aXZlIik7CiAgfQoKICBhcHByb3ZlQnV0dG9uLmNsaWNrKCk7CgogIGF3YWl0IHdhaXRGb3IoKCkgPT4gYXBwcm92YWxDb21wbGV0ZWQgIT09IG51bGwsIDE1MDAwKTsKICBpZiAoYXBwcm92YWxDb21wbGV0ZWQub2sgIT09IHRydWUpIHsKICAgIHRocm93IG5ldyBFcnJvcigiYXBwcm92YWwuY29tcGxldGVkIGZhaWxlZCIpOwogIH0KICBpZiAoCiAgICAoYXBwcm92YWxDb21wbGV0ZWQucGF5bG9hZCB8fCB7fSkubWlzc2lvbl9zdGF0dXMgIT09ICJjb21wbGV0ZWQiCiAgKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoIm1pc3Npb24gbm90IGNvbXBsZXRlZCBhZnRlciBhcHByb3ZhbCIpOwogIH0KCiAgLy8gNCkgRmluYWwgdXNlciByZWFkLW9ubHkgaW50ZW50IGFmdGVyIHRoZSBhdXRvbm9tb3VzIG1pc3Npb24vcmVzdG9yZS4KICBjb25zdCBwb3N0UHJldmlldyA9IGF3YWl0IGludGVudEFwaS5wcmV2aWV3KAogICAgInF1ZWxsZSBmZW7DqnRyZSBlc3QgYWN0aXZlID8iCiAgKTsKICBpZiAoCiAgICBwb3N0UHJldmlldy5pbnRlbnRfa2luZCAhPT0gInJlYWRfZm9yZWdyb3VuZCIgfHwKICAgIHBvc3RQcmV2aWV3LmV4ZWN1dGlvbl9hbGxvd2VkICE9PSB0cnVlCiAgKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoInBvc3QtbWlzc2lvbiByZWFkIHByZXZpZXcgaW52YWxpZCIpOwogIH0KICBjb25zdCBwb3N0UmVhZENvdW50ID0gcmVhZFJlc3BvbnNlcy5sZW5ndGg7CiAgaW50ZW50QXBpLmV4ZWN1dGVBY3RpdmVSZWFkT25seSgpOwogIGF3YWl0IHdhaXRGb3IoKCkgPT4gcmVhZFJlc3BvbnNlcy5sZW5ndGggPiBwb3N0UmVhZENvdW50LCA1MDAwKTsKICBjb25zdCBwb3N0UmVhZCA9IHJlYWRSZXNwb25zZXNbcmVhZFJlc3BvbnNlcy5sZW5ndGggLSAxXTsKICBpZiAocG9zdFJlYWQub2sgIT09IHRydWUpIHRocm93IG5ldyBFcnJvcigicG9zdC1taXNzaW9uIHJlYWQgZmFpbGVkIik7CiAgY29uc3QgcG9zdEh3bmQgPSBuZXN0ZWRId25kKHBvc3RSZWFkKTsKICBjb25zb2xlLmxvZygiUjI0X1BPU1RfUkVBRF9IV05EPSIgKyBwb3N0SHduZCk7CiAgY29uc29sZS5sb2coCiAgICAiUjI0X1BPU1RfUkVBRF9SRUNFSVBUPSIgKwogICAgKCgocG9zdFJlYWQucGF5bG9hZCB8fCB7fSkucmVjZWlwdF9pZCkgfHwgIiIpCiAgKTsKICBjb25zb2xlLmxvZygiUjI0X1BSRV9QT1NUX0hXTkRfTUFUQ0g9IiArIChwcmVId25kID09PSBwb3N0SHduZCkpOwoKICBjb25zdCBjb25maXJtUmVxdWVzdHMgPSByZXF1ZXN0QXVkaXQuZmlsdGVyKAogICAgeCA9PiB4LnR5cGUgPT09ICJhcHByb3ZhbC5jb25maXJtIgogICk7CiAgY29uc3QgcHJlcGFyZVJlcXVlc3RzID0gcmVxdWVzdEF1ZGl0LmZpbHRlcigKICAgIHggPT4geC50eXBlID09PSAicGMucHJlcGFyZV9taW5pbWl6ZV93aW5kb3ciCiAgKTsKICBjb25zdCBmb3JlZ3JvdW5kUmVxdWVzdHMgPSByZXF1ZXN0QXVkaXQuZmlsdGVyKAogICAgeCA9PiB4LnR5cGUgPT09ICJwYy5yZWFkX2ZvcmVncm91bmQiCiAgKTsKCiAgY29uc29sZS5sb2coCiAgICAiUjI0X0FQUFJPVkFMX0NPTkZJUk1fQ09VTlQ9IiArCiAgICBjb25maXJtUmVxdWVzdHMubGVuZ3RoCiAgKTsKICBjb25zb2xlLmxvZygKICAgICJSMjRfUFJFUEFSRV9SRVFVRVNUX0NPVU5UPSIgKwogICAgcHJlcGFyZVJlcXVlc3RzLmxlbmd0aAogICk7CiAgY29uc29sZS5sb2coCiAgICAiUjI0X1VJX0ZPUkVHUk9VTkRfUkVRVUVTVF9DT1VOVD0iICsKICAgIGZvcmVncm91bmRSZXF1ZXN0cy5sZW5ndGgKICApOwoKICBpZiAoY29uZmlybVJlcXVlc3RzLmxlbmd0aCAhPT0gMSkgewogICAgdGhyb3cgbmV3IEVycm9yKCJhcHByb3ZhbC5jb25maXJtIGNvdW50IG5vdCBvbmUiKTsKICB9CiAgaWYgKHByZXBhcmVSZXF1ZXN0cy5sZW5ndGggIT09IDEpIHsKICAgIHRocm93IG5ldyBFcnJvcigicHJlcGFyZSBtdXRhdGlvbiBjb3VudCBub3Qgb25lIik7CiAgfQogIGlmIChmb3JlZ3JvdW5kUmVxdWVzdHMubGVuZ3RoICE9PSAzKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoImV4cGVjdGVkIHByZS1yZWFkICsgdGFyZ2V0LXJlYWQgKyBwb3N0LXJlYWQiKTsKICB9CgogIGF3YWl0IHdhaXRGb3IoCiAgICAoKSA9PiBzdGF0dXNSZXNwb25zZXMubGVuZ3RoID49IDIsCiAgICA1MDAwCiAgKTsKICBjb25zdCBmaW5hbFN0YXR1cyA9IHN0YXR1c1Jlc3BvbnNlc1tzdGF0dXNSZXNwb25zZXMubGVuZ3RoIC0gMV07CiAgY29uc3QgZmluYWxQYXlsb2FkID0gZmluYWxTdGF0dXMucGF5bG9hZCB8fCB7fTsKICBjb25zdCByZWFkeSA9CiAgICBmaW5hbFN0YXR1cy5vayA9PT0gdHJ1ZSAmJgogICAgZmluYWxQYXlsb2FkLnJlYWRfb25seV9yZWFkeSA9PT0gdHJ1ZSAmJgogICAgZmluYWxQYXlsb2FkLm11dGF0aW9uX3JlYWR5ID09PSB0cnVlICYmCiAgICBBcnJheS5pc0FycmF5KGZpbmFsUGF5bG9hZC5wZW5kaW5nX2FwcHJvdmFscykgJiYKICAgIGZpbmFsUGF5bG9hZC5wZW5kaW5nX2FwcHJvdmFscy5sZW5ndGggPT09IDAgJiYKICAgIEFycmF5LmlzQXJyYXkoZmluYWxQYXlsb2FkLnN0YXJ0dXBfZmFpbHVyZXMpICYmCiAgICBmaW5hbFBheWxvYWQuc3RhcnR1cF9mYWlsdXJlcy5sZW5ndGggPT09IDAgJiYKICAgIEFycmF5LmlzQXJyYXkoZmluYWxQYXlsb2FkLnN0YXJ0dXBfc3VwZXJ2aXNpb25fcmVxdWlyZWQpICYmCiAgICBmaW5hbFBheWxvYWQuc3RhcnR1cF9zdXBlcnZpc2lvbl9yZXF1aXJlZC5sZW5ndGggPT09IDA7CgogIGNvbnNvbGUubG9nKCJSMjRfRklOQUxfUlVOVElNRV9SRUFEWT0iICsgcmVhZHkpOwogIGNvbnNvbGUubG9nKAogICAgIlIyNF9SMTdfRElBTE9HX0hJRERFTl9BRlRFUj0iICsKICAgIChkaWFsb2cuaGlkZGVuID09PSB0cnVlKQogICk7CiAgY29uc29sZS5sb2coIlIyNF9GSU5BTF9FMkVfUEFTUz10cnVlIik7Cn0pKCkuY2F0Y2goKGVycikgPT4gewogIGNvbnNvbGUuZXJyb3IoZXJyICYmIGVyci5zdGFjayA/IGVyci5zdGFjayA6IFN0cmluZyhlcnIpKTsKICBwcm9jZXNzLmV4aXRDb2RlID0gMTsKfSk7Cg=="

checks = []
real_mutation_count = 0
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


def title_of(hwnd: int) -> str:
    length = int(user32.GetWindowTextLengthW(int(hwnd)))
    buf = ctypes.create_unicode_buffer(max(length + 2, 2))
    user32.GetWindowTextW(int(hwnd), buf, len(buf))
    return buf.value


def snapshot(hwnd: int) -> dict:
    return {
        "exists": bool(user32.IsWindow(int(hwnd))),
        "title": title_of(int(hwnd)),
        "iconic": bool(user32.IsIconic(int(hwnd))),
        "zoomed": bool(user32.IsZoomed(int(hwnd))),
        "foreground": int(user32.GetForegroundWindow()) == int(hwnd),
    }


marker = str(os.environ.get("AURA_A200_R24_CONSOLE_MARKER") or "").strip()
run_token = str(os.environ.get("AURA_A200_R24_RUN_TOKEN") or "").strip()
human_approved = os.environ.get("AURA_A200_R24_USER_APPROVED") == "YES"

add(
    "R24 marker",
    A200_R24_MARKER
    == "AURA_A200_R24_FINAL_MULTI_STEP_AUTONOMOUS_PC_AGENT_E2E_V1",
)
add("R24 self-window only", SELF_WINDOW_ONLY is True)
add("R24 explicit human approval required", EXPLICIT_HUMAN_APPROVAL_REQUIRED is True)
add("R24 real R17 confirm required", EXPLICIT_R17_CONFIRM_REQUIRED is True)
add("R24 mutation preview non-executable", PLAN_PREVIEW_MUST_BE_NON_EXECUTABLE is True)
add("R24 five-task mission required", MISSION_TASK_COUNT_REQUIRED == 5)
add("R24 eight receipts required", EXPECTED_RECEIPT_COUNT == 8)
add("R24 single live mutation max one", SINGLE_LIVE_MUTATION_MAX == 1)
add("R24 capability minimize only", LIVE_CAPABILITY == "pc.minimize_window")
add("R24 exact W132 restore required", EXACT_W132_RESTORE_REQUIRED is True)
add("R24 MissionEngine evidence required", MISSIONENGINE_EVIDENCE_REQUIRED is True)
add("R24 final runtime ready required", FINAL_RUNTIME_READY_REQUIRED is True)
add("R24 approval one-use required", APPROVAL_ONE_USE_REQUIRED is True)
add("R24 no pending recovery required", NO_PENDING_RECOVERY_REQUIRED is True)
add("R24 direct NL execution disabled", DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED is False)
add("R24 auto approval disabled", AUTO_APPROVAL_ENABLED is False)
add("R24 auto cancel disabled", AUTO_CANCEL_ENABLED is False)
add("R24 autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("R24 autonomous multi-mutation disabled", AUTONOMOUS_MULTI_MUTATION_ENABLED is False)
add("R24 destructive disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("R24 close disabled", CLOSE_WINDOW_ENABLED is False)
add("R24 terminate disabled", TERMINATE_PROCESS_ENABLED is False)
add("R24 runtime shell disabled", SHELL_EXECUTION_ENABLED is False)
add("R24 marker env present", bool(marker), marker)
add("R24 run token env present", bool(run_token), run_token)
add("R24 human approval received", human_approved is True)
assert_r24_safety_contract()
add("R24 safety contract assertion", True)

if not human_approved:
    raise RuntimeError("R24 human approval missing")

target_hwnd = int(user32.GetForegroundWindow())
before = snapshot(target_hwnd)
add("R24 target HWND exists", target_hwnd > 0, target_hwnd)
add("R24 target title exact marker", before["title"] == marker, before["title"])
add("R24 target initially foreground", before["foreground"] is True)
add("R24 target initially not minimized", before["iconic"] is False)

if before["title"] != marker:
    raise RuntimeError("R24 exact foreground console check failed")

state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r24_final_e2e_"))
lifecycle = None
intent_host = None
mission_id = ""
approval_id = ""
presentation_digest = ""

try:
    token = TOKEN_FILE.read_text(encoding="ascii").strip()

    lifecycle = A200UiHostLifecycle(
        state_root=state_root / "runtime",
        token=token,
        host="127.0.0.1",
        port=18765,
        owner_id="r24-final-e2e-" + run_token,
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
    add("R24 starts with zero receipts", receipts_before == 0, receipts_before)

    node = shutil.which("node")
    add("Node available for R24 final E2E", bool(node), node or "MISSING")
    if not node:
        raise RuntimeError("Node required for R24")

    harness = state_root / "r24_final_e2e.js"
    harness.write_bytes(base64.b64decode(NODE_HARNESS_B64))

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
        timeout=40,
    )
    for line in (cp.stdout or "").splitlines():
        print("  node: " + line)

    add("R24 deployed final E2E Node PASS", cp.returncode == 0, f"exit={cp.returncode}")
    add("R24 initial runtime ready", "R24_INITIAL_STATUS_READY=true" in cp.stdout)
    add("R24 composer bound", "R24_COMPOSER_BOUND=true" in cp.stdout)
    add("R24 mutation preview remained non-executable", "R24_MUTATION_PREVIEW_EXECUTABLE=false" in cp.stdout)
    add("R24 plan digest SHA256", "R24_MUTATION_PLAN_DIGEST_LEN=64" in cp.stdout)
    add("R24 exact target stable from pre-read through approval", "R24_TARGET_EXACT=true" in cp.stdout)
    add("R24 approval.confirm emitted once", "R24_APPROVAL_CONFIRM_COUNT=1" in cp.stdout)
    add("R24 prepare request emitted once", "R24_PREPARE_REQUEST_COUNT=1" in cp.stdout)
    add("R24 UI foreground request count exact three", "R24_UI_FOREGROUND_REQUEST_COUNT=3" in cp.stdout)
    add("R24 pre/post foreground HWND match", "R24_PRE_POST_HWND_MATCH=true" in cp.stdout)
    add("R24 final runtime ready", "R24_FINAL_RUNTIME_READY=true" in cp.stdout)
    add("R24 R17 dialog closed", "R24_R17_DIALOG_HIDDEN_AFTER=true" in cp.stdout)
    add("R24 deployed E2E marker", "R24_FINAL_E2E_PASS=true" in cp.stdout)

    def parse(name: str) -> str:
        m = re.search(rf"^{re.escape(name)}=(.+)$", cp.stdout, flags=re.MULTILINE)
        return "" if not m else m.group(1).strip()

    mission_id = parse("R24_MISSION_ID")
    approval_id = parse("R24_APPROVAL_ID")
    presentation_digest = parse("R24_PRESENTATION_DIGEST")
    pre_read_receipt = parse("R24_PRE_READ_RECEIPT")
    post_read_receipt = parse("R24_POST_READ_RECEIPT")
    pre_hwnd = int(parse("R24_PRE_READ_HWND") or "0")
    post_hwnd = int(parse("R24_POST_READ_HWND") or "0")

    add("R24 mission id parsed", bool(mission_id), mission_id or "MISSING")
    add("R24 approval id parsed", bool(approval_id), approval_id or "MISSING")
    add("R24 presentation digest parsed", len(presentation_digest) == 64, len(presentation_digest))
    add("R24 pre-read receipt parsed", bool(pre_read_receipt), pre_read_receipt or "MISSING")
    add("R24 post-read receipt parsed", bool(post_read_receipt), post_read_receipt or "MISSING")
    add("R24 pre-read HWND exact target", pre_hwnd == target_hwnd, f"{pre_hwnd} vs {target_hwnd}")
    add("R24 post-read HWND exact target", post_hwnd == target_hwnd, f"{post_hwnd} vs {target_hwnd}")

    mission = lifecycle._transport.runtime.engine.get_mission(mission_id)
    add("R24 MissionEngine mission completed", mission.status == "completed", mission.status)
    add("R24 MissionEngine has five tasks", len(mission.tasks) == 5, len(mission.tasks))
    add(
        "R24 all mission tasks succeeded",
        all(task.status == "succeeded" for task in mission.tasks.values()),
        {task.key: task.status for task in mission.tasks.values()},
    )
    add(
        "R24 every mission task has evidence",
        all(bool(task.evidence_ids) for task in mission.tasks.values()),
        {task.key: list(task.evidence_ids) for task in mission.tasks.values()},
    )

    observe_before = task_by_key(mission, "observe_before")
    minimize_task = task_by_key(mission, "minimize_once")
    observe_mutated = task_by_key(mission, "observe_mutated")
    restore_task = task_by_key(mission, "restore_exact")
    observe_final = task_by_key(mission, "observe_final")

    add(
        "R24 observe_before target foreground",
        foreground_hwnd_from_task(observe_before) == target_hwnd,
        foreground_hwnd_from_task(observe_before),
    )
    add(
        "R24 observe_mutated proves real minimize transition",
        foreground_hwnd_from_task(observe_mutated) != target_hwnd,
        foreground_hwnd_from_task(observe_mutated),
    )
    add(
        "R24 observe_final target foreground restored",
        foreground_hwnd_from_task(observe_final) == target_hwnd,
        foreground_hwnd_from_task(observe_final),
    )

    mission_receipts = []
    for task in mission.tasks.values():
        result = task.result if isinstance(task.result, dict) else {}
        rid = str(result.get("receipt_id") or "")
        if rid:
            mission_receipts.append(rid)

    add("R24 five mission receipts present", len(mission_receipts) == 5, mission_receipts)
    add("R24 five mission receipts unique", len(set(mission_receipts)) == 5)
    add(
        "R24 five mission receipts succeeded",
        all(
            lifecycle._transport.runtime.receipts.get_receipt(rid).status
            == "succeeded"
            for rid in mission_receipts
        ),
    )

    minimize_result = minimize_task.result if isinstance(minimize_task.result, dict) else {}
    restore_result = restore_task.result if isinstance(restore_task.result, dict) else {}
    mutation_receipt_id = str(minimize_result.get("receipt_id") or "")
    restore_receipt_id = str(restore_result.get("receipt_id") or "")
    add("R24 mutation receipt present", bool(mutation_receipt_id), mutation_receipt_id)
    add("R24 restore receipt present", bool(restore_receipt_id), restore_receipt_id)
    add("R24 mutation and restore receipts differ", mutation_receipt_id != restore_receipt_id)

    all_receipts = lifecycle._transport.runtime.receipts.list_receipts()
    add(
        "R24 exactly eight canonical receipts",
        len(all_receipts) == receipts_before + 8,
        f"{receipts_before}->{len(all_receipts)}",
    )
    all_ids = [r.receipt_id for r in all_receipts]
    add("R24 all eight receipt ids unique", len(all_ids) == len(set(all_ids)))
    add(
        "R24 all eight receipts succeeded",
        all(r.status == "succeeded" for r in all_receipts),
        [r.status for r in all_receipts],
    )
    add("R24 pre/post read receipts differ", pre_read_receipt != post_read_receipt)
    add("R24 pre-read receipt canonical", pre_read_receipt in all_ids)
    add("R24 post-read receipt canonical", post_read_receipt in all_ids)

    real_mutation_count = 1 if (
        lifecycle._transport.runtime.receipts.get_receipt(mutation_receipt_id).status
        == "succeeded"
        and foreground_hwnd_from_task(observe_mutated) != target_hwnd
    ) else 0
    add("R24 exactly one real live mutation proved", real_mutation_count == 1, real_mutation_count)

    challenge = lifecycle._transport.ingress.approval_store.get(approval_id)
    add("R24 approval durable", challenge is not None)
    add(
        "R24 approval consumed one-use",
        challenge is not None and challenge.state == "consumed",
        None if challenge is None else challenge.state,
    )

    before_replay = len(
        lifecycle._transport.runtime.receipts.list_receipts()
    )
    must_raise(
        "R24 consumed approval replay rejected",
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
        "R24 replay creates no receipt",
        len(lifecycle._transport.runtime.receipts.list_receipts())
        == before_replay,
    )

    add(
        "R24 no pending crash journal",
        lifecycle._transport.runtime.crash_journal.get_pending(mission_id) is None,
    )
    add(
        "R24 no running idempotency intents",
        lifecycle._transport.runtime.intent_ledger.count(state="running") == 0,
    )

    settled = None
    for _ in range(30):
        settled = snapshot(target_hwnd)
        if (
            settled["exists"]
            and settled["title"] == marker
            and settled["iconic"] == before["iconic"]
            and settled["zoomed"] == before["zoomed"]
            and settled["foreground"]
        ):
            break
        time.sleep(0.1)

    add("R24 final target exists", settled["exists"] is True)
    add("R24 final title exact", settled["title"] == marker, settled["title"])
    add("R24 final minimized state exact", settled["iconic"] == before["iconic"])
    add("R24 final maximized state exact", settled["zoomed"] == before["zoomed"])
    add("R24 final foreground exact", settled["foreground"] is True)

    final_state_restored = all(
        [
            settled["exists"],
            settled["title"] == marker,
            settled["iconic"] == before["iconic"],
            settled["zoomed"] == before["zoomed"],
            settled["foreground"],
        ]
    )

    print(f"R24_REAL_MUTATION_COUNT = {real_mutation_count}", flush=True)
    print(f"R24_FINAL_STATE_RESTORED = {final_state_restored}", flush=True)

finally:
    if intent_host is not None:
        intent_host.close()
    if lifecycle is not None:
        lifecycle.close()
    shutil.rmtree(state_root, ignore_errors=True)

src = (
    ROOT / "runtime" / "aura_final_pc_agent_e2e_acceptance_v200.py"
).read_text(encoding="utf-8-sig", errors="replace")
add("R24 guard source contains no subprocess", "import subprocess" not in src and "from subprocess" not in src)
add("R24 guard source contains no shell API", all(token not in src for token in ("os.system(", "os.popen(", "ctypes.", "child_process")))
add("R24 guard source contains no close capability", "pc.close_window" not in src)
add("R24 guard source contains no terminate capability", "pc.terminate_process" not in src)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R24_REAL_MUTATION_COUNT = {real_mutation_count}")
print(f"R24_FINAL_STATE_RESTORED = {final_state_restored}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if real_mutation_count != 1:
    raise SystemExit("R24 expected exactly one live mutation")
if not final_state_restored:
    raise SystemExit("R24 exact final state was not restored")
print("[PASS] A200-R24 final multi-step supervised autonomous PC agent end-to-end acceptance")
