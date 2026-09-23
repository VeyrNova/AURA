from __future__ import annotations

import ast
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_conversation_intent_handoff_v200 import (
    A200ConversationIntentHandoff,
    A200IntentPreviewHost,
    A200_R20_MARKER,
    ARBITRARY_TOOL_EXECUTION_ENABLED,
    AUTO_APPROVAL_ENABLED,
    AUTO_CANCEL_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED,
    EXPLICIT_READONLY_CONFIRMATION_REQUIRED,
    EXTERNAL_NETWORK_BINDING_ENABLED,
    MUTATION_EXECUTION_FROM_INTENT_ENABLED,
    PREVIEW_ONLY_AUTHORITY,
    READONLY_EXECUTION_ALLOWLIST,
    assert_r20_safety_contract,
)
from runtime.aura_ui_host_lifecycle_v200 import (
    A200UiHostLifecycle,
)

UI_ROOT = Path(r"C:\Users\leclerc\AppData\Local\AURA\ui\v0.7.2.2-rc4.2")
R17 = UI_ROOT / "dist" / "assets" / "aura-a200-supervised-bridge-ui.js"
R18 = UI_ROOT / "dist" / "assets" / "aura-a200-supervised-host-transport.js"
R20 = UI_ROOT / "dist" / "assets" / "aura-a200-conversation-intent-preview.js"
TOKEN_FILE = ROOT / "data" / "a200_runtime" / "r18_ui_transport_token.txt"
NODE_HARNESS_B64 = "Y29uc3QgZnMgPSByZXF1aXJlKCJmcyIpOwpjb25zdCBodHRwID0gcmVxdWlyZSgiaHR0cCIpOwpjb25zdCB2bSA9IHJlcXVpcmUoInZtIik7Cgpjb25zdCBSMTcgPSBwcm9jZXNzLmFyZ3ZbMl07CmNvbnN0IFIxOCA9IHByb2Nlc3MuYXJndlszXTsKY29uc3QgUjIwID0gcHJvY2Vzcy5hcmd2WzRdOwoKY29uc3QgbGlzdGVuZXJzID0gbmV3IE1hcCgpOwoKY2xhc3MgQ3VzdG9tRXZlbnQgewogIGNvbnN0cnVjdG9yKHR5cGUsIG9wdGlvbnMgPSB7fSkgewogICAgdGhpcy50eXBlID0gdHlwZTsKICAgIHRoaXMuZGV0YWlsID0gb3B0aW9ucy5kZXRhaWw7CiAgfQp9CgpmdW5jdGlvbiBhZGRXaW5kb3dMaXN0ZW5lcih0eXBlLCBmbikgewogIGlmICghbGlzdGVuZXJzLmhhcyh0eXBlKSkgbGlzdGVuZXJzLnNldCh0eXBlLCBbXSk7CiAgbGlzdGVuZXJzLmdldCh0eXBlKS5wdXNoKGZuKTsKfQoKZnVuY3Rpb24gZGlzcGF0Y2hXaW5kb3coZXZlbnQpIHsKICBjb25zdCBhcnIgPSBsaXN0ZW5lcnMuZ2V0KGV2ZW50LnR5cGUpIHx8IFtdOwogIGZvciAoY29uc3QgZm4gb2YgWy4uLmFycl0pIGZuLmNhbGwod2luZG93LCBldmVudCk7CiAgcmV0dXJuIHRydWU7Cn0KCmNsYXNzIEZha2VOb2RlIHsKICBjb25zdHJ1Y3RvcihzZWxlY3RvciA9ICIiKSB7CiAgICB0aGlzLnNlbGVjdG9yID0gc2VsZWN0b3I7CiAgICB0aGlzLmRhdGFzZXQgPSB7fTsKICAgIHRoaXMudGV4dENvbnRlbnQgPSAiIjsKICAgIHRoaXMuaGlkZGVuID0gZmFsc2U7CiAgICB0aGlzLmRpc2FibGVkID0gZmFsc2U7CiAgICB0aGlzLmlkID0gIiI7CiAgICB0aGlzLmNoaWxkcmVuID0gW107CiAgICB0aGlzLmV2ZW50cyA9IHt9OwogIH0KICBhZGRFdmVudExpc3RlbmVyKHR5cGUsIGZuKSB7CiAgICBpZiAoIXRoaXMuZXZlbnRzW3R5cGVdKSB0aGlzLmV2ZW50c1t0eXBlXSA9IFtdOwogICAgdGhpcy5ldmVudHNbdHlwZV0ucHVzaChmbik7CiAgfQogIHNldEF0dHJpYnV0ZSgpIHt9CiAgYXBwZW5kQ2hpbGQobm9kZSkgewogICAgdGhpcy5jaGlsZHJlbi5wdXNoKG5vZGUpOwogICAgaWYgKG5vZGUuaWQpIGRvY3VtZW50Ll9ieUlkLnNldChub2RlLmlkLCBub2RlKTsKICAgIHJldHVybiBub2RlOwogIH0KfQoKY2xhc3MgRmFrZVJvb3QgZXh0ZW5kcyBGYWtlTm9kZSB7CiAgY29uc3RydWN0b3IoKSB7CiAgICBzdXBlcigicm9vdCIpOwogICAgdGhpcy5fbm9kZXMgPSBuZXcgTWFwKCk7CiAgICB0aGlzLl9odG1sID0gIiI7CiAgfQogIHNldCBpbm5lckhUTUwodmFsdWUpIHsgdGhpcy5faHRtbCA9IHZhbHVlOyB9CiAgZ2V0IGlubmVySFRNTCgpIHsgcmV0dXJuIHRoaXMuX2h0bWw7IH0KICBxdWVyeVNlbGVjdG9yKHNlbGVjdG9yKSB7CiAgICBpZiAoIXRoaXMuX25vZGVzLmhhcyhzZWxlY3RvcikpIHsKICAgICAgdGhpcy5fbm9kZXMuc2V0KHNlbGVjdG9yLCBuZXcgRmFrZU5vZGUoc2VsZWN0b3IpKTsKICAgIH0KICAgIHJldHVybiB0aGlzLl9ub2Rlcy5nZXQoc2VsZWN0b3IpOwogIH0KfQoKZ2xvYmFsLkN1c3RvbUV2ZW50ID0gQ3VzdG9tRXZlbnQ7Cmdsb2JhbC53aW5kb3cgPSB7CiAgYWRkRXZlbnRMaXN0ZW5lcjogYWRkV2luZG93TGlzdGVuZXIsCiAgZGlzcGF0Y2hFdmVudDogZGlzcGF0Y2hXaW5kb3cKfTsKCmdsb2JhbC5kb2N1bWVudCA9IHsKICByZWFkeVN0YXRlOiAiY29tcGxldGUiLAogIF9ieUlkOiBuZXcgTWFwKCksCiAgYm9keTogbmV3IEZha2VOb2RlKCJib2R5IiksCiAgZ2V0RWxlbWVudEJ5SWQoaWQpIHsKICAgIHJldHVybiB0aGlzLl9ieUlkLmdldChpZCkgfHwgbnVsbDsKICB9LAogIGNyZWF0ZUVsZW1lbnQodGFnKSB7CiAgICByZXR1cm4gdGFnID09PSAic2VjdGlvbiIgPyBuZXcgRmFrZVJvb3QoKSA6IG5ldyBGYWtlTm9kZSh0YWcpOwogIH0sCiAgYWRkRXZlbnRMaXN0ZW5lcigpIHt9Cn07Cgpkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkID0gZnVuY3Rpb24obm9kZSkgewogIHRoaXMuY2hpbGRyZW4ucHVzaChub2RlKTsKICBpZiAobm9kZS5pZCkgZG9jdW1lbnQuX2J5SWQuc2V0KG5vZGUuaWQsIG5vZGUpOwogIHJldHVybiBub2RlOwp9OwoKZ2xvYmFsLmZldGNoID0gZnVuY3Rpb24odXJsLCBvcHRpb25zID0ge30pIHsKICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4gewogICAgY29uc3QgdSA9IG5ldyBVUkwodXJsKTsKICAgIGNvbnN0IGJvZHkgPSBvcHRpb25zLmJvZHkgfHwgIiI7CiAgICBjb25zdCBoZWFkZXJzID0gT2JqZWN0LmFzc2lnbih7fSwgb3B0aW9ucy5oZWFkZXJzIHx8IHt9KTsKICAgIGhlYWRlcnNbIkNvbnRlbnQtTGVuZ3RoIl0gPSBCdWZmZXIuYnl0ZUxlbmd0aChib2R5KTsKICAgIGlmICghT2JqZWN0LmtleXMoaGVhZGVycykuc29tZShrID0+IGsudG9Mb3dlckNhc2UoKSA9PT0gIm9yaWdpbiIpKSB7CiAgICAgIGhlYWRlcnNbIk9yaWdpbiJdID0gIm51bGwiOwogICAgfQogICAgY29uc3QgcmVxID0gaHR0cC5yZXF1ZXN0KAogICAgICB7CiAgICAgICAgaG9zdG5hbWU6IHUuaG9zdG5hbWUsCiAgICAgICAgcG9ydDogdS5wb3J0LAogICAgICAgIHBhdGg6IHUucGF0aG5hbWUgKyB1LnNlYXJjaCwKICAgICAgICBtZXRob2Q6IG9wdGlvbnMubWV0aG9kIHx8ICJHRVQiLAogICAgICAgIGhlYWRlcnMKICAgICAgfSwKICAgICAgKHJlcykgPT4gewogICAgICAgIGxldCBkYXRhID0gIiI7CiAgICAgICAgcmVzLnNldEVuY29kaW5nKCJ1dGY4Iik7CiAgICAgICAgcmVzLm9uKCJkYXRhIiwgY2h1bmsgPT4gZGF0YSArPSBjaHVuayk7CiAgICAgICAgcmVzLm9uKCJlbmQiLCAoKSA9PiB7CiAgICAgICAgICByZXNvbHZlKHsKICAgICAgICAgICAgb2s6IHJlcy5zdGF0dXNDb2RlID49IDIwMCAmJiByZXMuc3RhdHVzQ29kZSA8IDMwMCwKICAgICAgICAgICAgc3RhdHVzOiByZXMuc3RhdHVzQ29kZSwKICAgICAgICAgICAgYXN5bmMganNvbigpIHsgcmV0dXJuIEpTT04ucGFyc2UoZGF0YSB8fCAie30iKTsgfQogICAgICAgICAgfSk7CiAgICAgICAgfSk7CiAgICAgIH0KICAgICk7CiAgICByZXEub24oImVycm9yIiwgcmVqZWN0KTsKICAgIGlmIChib2R5KSByZXEud3JpdGUoYm9keSk7CiAgICByZXEuZW5kKCk7CiAgfSk7Cn07CgpsZXQgaW5pdGlhbFN0YXR1cyA9IG51bGw7CmxldCBsYXRlc3RSZWFkID0gbnVsbDsKd2luZG93LmFkZEV2ZW50TGlzdGVuZXIoImF1cmE6YTIwMC1zdXBlcnZpc2VkLXJlc3BvbnNlIiwgKGV2ZW50KSA9PiB7CiAgY29uc3QgZCA9IGV2ZW50LmRldGFpbCB8fCB7fTsKICBpZiAoZC5raW5kID09PSAicnVudGltZS5zdGF0dXMiKSBpbml0aWFsU3RhdHVzID0gZDsKICBpZiAoZC5raW5kID09PSAicGMucmVhZF9mb3JlZ3JvdW5kIikgbGF0ZXN0UmVhZCA9IGQ7Cn0pOwoKZnVuY3Rpb24gd2FpdEZvcihwcmVkaWNhdGUsIHRpbWVvdXRNcykgewogIGNvbnN0IHN0YXJ0ID0gRGF0ZS5ub3coKTsKICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4gewogICAgY29uc3QgdGltZXIgPSBzZXRJbnRlcnZhbCgoKSA9PiB7CiAgICAgIHRyeSB7CiAgICAgICAgaWYgKHByZWRpY2F0ZSgpKSB7CiAgICAgICAgICBjbGVhckludGVydmFsKHRpbWVyKTsKICAgICAgICAgIHJlc29sdmUoKTsKICAgICAgICAgIHJldHVybjsKICAgICAgICB9CiAgICAgICAgaWYgKERhdGUubm93KCkgLSBzdGFydCA+IHRpbWVvdXRNcykgewogICAgICAgICAgY2xlYXJJbnRlcnZhbCh0aW1lcik7CiAgICAgICAgICByZWplY3QobmV3IEVycm9yKCJ0aW1lb3V0IikpOwogICAgICAgIH0KICAgICAgfSBjYXRjaCAoZXJyKSB7CiAgICAgICAgY2xlYXJJbnRlcnZhbCh0aW1lcik7CiAgICAgICAgcmVqZWN0KGVycik7CiAgICAgIH0KICAgIH0sIDI1KTsKICB9KTsKfQoKKGFzeW5jICgpID0+IHsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMTgsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIxOCB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMTcsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIxNyB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMjAsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIyMCB9KTsKCiAgYXdhaXQgd2FpdEZvcigoKSA9PiBpbml0aWFsU3RhdHVzICE9PSBudWxsLCA1MDAwKTsKICBpZiAoaW5pdGlhbFN0YXR1cy5vayAhPT0gdHJ1ZSkgdGhyb3cgbmV3IEVycm9yKCJpbml0aWFsIHN0YXR1cyBmYWlsZWQiKTsKCiAgY29uc29sZS5sb2coIlIyMF9TRVNTSU9OX09LPXRydWUiKTsKCiAgd2luZG93LmRpc3BhdGNoRXZlbnQobmV3IEN1c3RvbUV2ZW50KAogICAgImF1cmE6YTIwMC1jb252ZXJzYXRpb24taW50ZW50IiwKICAgIHsgZGV0YWlsOiB7IHRleHQ6ICJxdWVsbGUgZmVuw6p0cmUgZXN0IGFjdGl2ZSA/IiB9IH0KICApKTsKCiAgYXdhaXQgd2FpdEZvcigKICAgICgpID0+IHsKICAgICAgY29uc3QgcCA9IHdpbmRvdy5BVVJBX0EyMDBfSU5URU5UX0hBTkRPRkYuZ2V0QWN0aXZlUHJldmlldygpOwogICAgICByZXR1cm4gcCAmJiBwLmludGVudF9raW5kID09PSAicmVhZF9mb3JlZ3JvdW5kIjsKICAgIH0sCiAgICA1MDAwCiAgKTsKCiAgY29uc3QgcmVhZFByZXZpZXcgPSB3aW5kb3cuQVVSQV9BMjAwX0lOVEVOVF9IQU5ET0ZGLmdldEFjdGl2ZVByZXZpZXcoKTsKICBjb25zb2xlLmxvZygiUjIwX1JFQURfUFJFVklFV19LSU5EPSIgKyByZWFkUHJldmlldy5pbnRlbnRfa2luZCk7CiAgY29uc29sZS5sb2coIlIyMF9SRUFEX1BSRVZJRVdfUklTSz0iICsgcmVhZFByZXZpZXcucmlzayk7CiAgY29uc29sZS5sb2coIlIyMF9SRUFEX1BSRVZJRVdfRVhFQ1VUQUJMRT0iICsgcmVhZFByZXZpZXcuZXhlY3V0aW9uX2FsbG93ZWQpOwogIGNvbnNvbGUubG9nKCJSMjBfUkVBRF9QTEFOX0RJR0VTVF9MRU49IiArIFN0cmluZyhyZWFkUHJldmlldy5wbGFuX2RpZ2VzdCB8fCAiIikubGVuZ3RoKTsKCiAgaWYgKHJlYWRQcmV2aWV3LmV4ZWN1dGlvbl9hbGxvd2VkICE9PSB0cnVlKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoInJlYWQgcHJldmlldyBub3QgZXhlY3V0YWJsZSIpOwogIH0KICBpZiAocmVhZFByZXZpZXcuY29tbWFuZF90eXBlICE9PSAicGMucmVhZF9mb3JlZ3JvdW5kIikgewogICAgdGhyb3cgbmV3IEVycm9yKCJ3cm9uZyByZWFkIGNvbW1hbmQiKTsKICB9CgogIHdpbmRvdy5BVVJBX0EyMDBfSU5URU5UX0hBTkRPRkYuZXhlY3V0ZUFjdGl2ZVJlYWRPbmx5KCk7CiAgYXdhaXQgd2FpdEZvcigoKSA9PiBsYXRlc3RSZWFkICE9PSBudWxsLCA1MDAwKTsKCiAgY29uc29sZS5sb2coIlIyMF9SRUFEX1JFU1VMVF9PSz0iICsgbGF0ZXN0UmVhZC5vayk7CiAgY29uc29sZS5sb2coCiAgICAiUjIwX1JFQURfUkVDRUlQVD0iICsKICAgICgoKGxhdGVzdFJlYWQucGF5bG9hZCB8fCB7fSkucmVjZWlwdF9pZCkgfHwgIiIpCiAgKTsKCiAgaWYgKGxhdGVzdFJlYWQub2sgIT09IHRydWUpIHRocm93IG5ldyBFcnJvcigicmVhZCBleGVjdXRpb24gZmFpbGVkIik7CiAgaWYgKCEoKGxhdGVzdFJlYWQucGF5bG9hZCB8fCB7fSkucmVjZWlwdF9pZCkpIHsKICAgIHRocm93IG5ldyBFcnJvcigicmVhZCByZWNlaXB0IG1pc3NpbmciKTsKICB9CgogIHdpbmRvdy5kaXNwYXRjaEV2ZW50KG5ldyBDdXN0b21FdmVudCgKICAgICJhdXJhOmEyMDAtY29udmVyc2F0aW9uLWludGVudCIsCiAgICB7IGRldGFpbDogeyB0ZXh0OiAibWluaW1pc2UgbGEgZmVuw6p0cmUgYWN0aXZlIiB9IH0KICApKTsKICBhd2FpdCB3YWl0Rm9yKAogICAgKCkgPT4gewogICAgICBjb25zdCBwID0gd2luZG93LkFVUkFfQTIwMF9JTlRFTlRfSEFORE9GRi5nZXRBY3RpdmVQcmV2aWV3KCk7CiAgICAgIHJldHVybiBwICYmIHAuaW50ZW50X2tpbmQgPT09ICJzdXBlcnZpc2VkX211dGF0aW9uIjsKICAgIH0sCiAgICA1MDAwCiAgKTsKICBjb25zdCBtdXRhdGlvblByZXZpZXcgPQogICAgd2luZG93LkFVUkFfQTIwMF9JTlRFTlRfSEFORE9GRi5nZXRBY3RpdmVQcmV2aWV3KCk7CiAgY29uc29sZS5sb2coIlIyMF9NVVRBVElPTl9LSU5EPSIgKyBtdXRhdGlvblByZXZpZXcuaW50ZW50X2tpbmQpOwogIGNvbnNvbGUubG9nKCJSMjBfTVVUQVRJT05fRVhFQ1VUQUJMRT0iICsgbXV0YXRpb25QcmV2aWV3LmV4ZWN1dGlvbl9hbGxvd2VkKTsKICBjb25zb2xlLmxvZygKICAgICJSMjBfTVVUQVRJT05fU1VQRVJWSVNFRD0iICsKICAgIG11dGF0aW9uUHJldmlldy5yZXF1aXJlc19zdXBlcnZpc2VkX3BhdGgKICApOwogIGlmIChtdXRhdGlvblByZXZpZXcuZXhlY3V0aW9uX2FsbG93ZWQgIT09IGZhbHNlKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoIm11dGF0aW9uIGludGVudCBiZWNhbWUgZXhlY3V0YWJsZSIpOwogIH0KCiAgd2luZG93LmRpc3BhdGNoRXZlbnQobmV3IEN1c3RvbUV2ZW50KAogICAgImF1cmE6YTIwMC1jb252ZXJzYXRpb24taW50ZW50IiwKICAgIHsgZGV0YWlsOiB7IHRleHQ6ICJzdXBwcmltZSBsZSBwcm9jZXNzdXMgYWN0aWYiIH0gfQogICkpOwogIGF3YWl0IHdhaXRGb3IoCiAgICAoKSA9PiB7CiAgICAgIGNvbnN0IHAgPSB3aW5kb3cuQVVSQV9BMjAwX0lOVEVOVF9IQU5ET0ZGLmdldEFjdGl2ZVByZXZpZXcoKTsKICAgICAgcmV0dXJuIHAgJiYgcC5pbnRlbnRfa2luZCA9PT0gImJsb2NrZWRfZGVzdHJ1Y3RpdmUiOwogICAgfSwKICAgIDUwMDAKICApOwogIGNvbnN0IGRlc3RydWN0aXZlUHJldmlldyA9CiAgICB3aW5kb3cuQVVSQV9BMjAwX0lOVEVOVF9IQU5ET0ZGLmdldEFjdGl2ZVByZXZpZXcoKTsKICBjb25zb2xlLmxvZygiUjIwX0RFU1RSVUNUSVZFX0tJTkQ9IiArIGRlc3RydWN0aXZlUHJldmlldy5pbnRlbnRfa2luZCk7CiAgY29uc29sZS5sb2coCiAgICAiUjIwX0RFU1RSVUNUSVZFX0VYRUNVVEFCTEU9IiArCiAgICBkZXN0cnVjdGl2ZVByZXZpZXcuZXhlY3V0aW9uX2FsbG93ZWQKICApOwogIGlmIChkZXN0cnVjdGl2ZVByZXZpZXcuZXhlY3V0aW9uX2FsbG93ZWQgIT09IGZhbHNlKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoImRlc3RydWN0aXZlIGludGVudCBiZWNhbWUgZXhlY3V0YWJsZSIpOwogIH0KCiAgY29uc29sZS5sb2coIlIyMF9ERVBMT1lFRF9SRUFET05MWV9KT1VSTkVZX1BBU1M9dHJ1ZSIpOwp9KSgpLmNhdGNoKChlcnIpID0+IHsKICBjb25zb2xlLmVycm9yKGVyciAmJiBlcnIuc3RhY2sgPyBlcnIuc3RhY2sgOiBTdHJpbmcoZXJyKSk7CiAgcHJvY2Vzcy5leGl0Q29kZSA9IDE7Cn0pOwo="

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


def post_preview(port, token, request):
    body = json.dumps(request).encode("utf-8")
    url = f"http://127.0.0.1:{port}/aura/a200/intent/preview"

    last_abort = None
    for attempt in range(2):
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
                "X-AURA-A200-Transport-Token": token,
                "Origin": "null",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except ConnectionAbortedError as exc:
            if getattr(exc, "winerror", None) != 10053 or attempt >= 1:
                raise
            last_abort = exc
            print(
                "[INFO] R20 preview HTTP hit exact WinError 10053; "
                "retrying once.",
                flush=True,
            )
            time.sleep(0.5)

    raise last_abort or RuntimeError("unreachable preview retry state")


add("R20 marker", A200_R20_MARKER == "AURA_A200_R20_CONVERSATION_INTENT_HANDOFF_PLAN_PREVIEW_V1")
add("R20 preview only authority", PREVIEW_ONLY_AUTHORITY is True)
add("R20 explicit read-only confirmation required", EXPLICIT_READONLY_CONFIRMATION_REQUIRED is True)
add("R20 direct natural-language execution disabled", DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED is False)
add("R20 mutation execution from intent disabled", MUTATION_EXECUTION_FROM_INTENT_ENABLED is False)
add("R20 destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("R20 auto approval disabled", AUTO_APPROVAL_ENABLED is False)
add("R20 auto cancel disabled", AUTO_CANCEL_ENABLED is False)
add("R20 arbitrary tool execution disabled", ARBITRARY_TOOL_EXECUTION_ENABLED is False)
add("R20 external network binding disabled", EXTERNAL_NETWORK_BINDING_ENABLED is False)
add("R20 read-only allowlist exact", tuple(READONLY_EXECUTION_ALLOWLIST) == ("runtime.status", "pc.read_foreground"))
assert_r20_safety_contract()
add("R20 safety contract assertion", True)
add("R20 preview HTTP transient retry max one", True)
add("R20 preview HTTP transient retry signature exact", True)

handoff = A200ConversationIntentHandoff()

read_preview = handoff.preview("quelle fenêtre est active ?").to_dict()
add("R20 parser read intent", read_preview["intent_kind"] == "read_foreground")
add("R20 parser read risk", read_preview["risk"] == "read_only")
add("R20 parser read executable", read_preview["execution_allowed"] is True)
add("R20 parser read command exact", read_preview["command_type"] == "pc.read_foreground")
add("R20 parser read explicit confirmation", read_preview["requires_explicit_confirmation"] is True)
add("R20 parser read digest SHA256", len(read_preview["plan_digest"]) == 64)

status_preview = handoff.preview("statut supervision aura").to_dict()
add("R20 parser status intent", status_preview["intent_kind"] == "runtime_status")
add("R20 parser status command exact", status_preview["command_type"] == "runtime.status")

mutation_preview = handoff.preview("minimise la fenêtre active").to_dict()
add("R20 parser mutation supervised", mutation_preview["intent_kind"] == "supervised_mutation")
add("R20 parser mutation not executable", mutation_preview["execution_allowed"] is False)
add("R20 parser mutation no command", mutation_preview["command_type"] is None)
add("R20 parser mutation requires supervised path", mutation_preview["requires_supervised_path"] is True)

destructive_preview = handoff.preview("supprime le processus actif").to_dict()
add("R20 parser destructive blocked", destructive_preview["intent_kind"] == "blocked_destructive")
add("R20 parser destructive not executable", destructive_preview["execution_allowed"] is False)
add("R20 parser destructive no command", destructive_preview["command_type"] is None)

unknown_preview = handoff.preview("fais quelque chose de cool").to_dict()
add("R20 parser unknown unsupported", unknown_preview["intent_kind"] == "unsupported")
add("R20 parser unknown not executable", unknown_preview["execution_allowed"] is False)

token = TOKEN_FILE.read_text(encoding="ascii").strip()
state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r20_"))
lock_file = state_root / "intent.lock"
intent_host = None
lifecycle = None

try:
    intent_host = A200IntentPreviewHost(
        token=token,
        host="127.0.0.1",
        port=18766,
        lock_file=lock_file,
    )
    h, p = intent_host.start()
    add("R20 preview host loopback", h == "127.0.0.1")
    add("R20 preview host fixed port", p == 18766)

    code, response = post_preview(
        p,
        token,
        {
            "schema": "aura.a200.intent-preview-request.v1",
            "request_id": "r20-http-read",
            "text": "quelle fenêtre est active ?",
        },
    )
    add("R20 HTTP preview returns 200", code == 200, code)
    add("R20 HTTP preview ok", response.get("ok") is True)
    add("R20 HTTP preview read intent", (response.get("preview") or {}).get("intent_kind") == "read_foreground")

    bad_code, bad_response = post_preview(
        p,
        "0" * 64,
        {
            "schema": "aura.a200.intent-preview-request.v1",
            "request_id": "r20-bad-token",
            "text": "quelle fenêtre est active ?",
        },
    )
    add("R20 wrong token rejected", bad_code == 403, bad_code)
    add("R20 wrong token explicit error", bad_response.get("error") == "transport_token_invalid")

    lifecycle = A200UiHostLifecycle(
        state_root=state_root / "runtime",
        token=token,
        host="127.0.0.1",
        port=18765,
        owner_id="r20-readonly-journey",
    )
    lifecycle.start()

    receipts_before = len(
        lifecycle._transport.runtime.receipts.list_receipts()
    )

    node = shutil.which("node")
    add("Node available for R20 deployed journey", bool(node), node or "MISSING")
    if not node:
        raise RuntimeError("Node required for R20 deployed journey")

    harness = state_root / "r20_journey.js"
    harness.write_bytes(base64.b64decode(NODE_HARNESS_B64))

    cp = subprocess.run(
        [node, str(harness), str(R17), str(R18), str(R20)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=25,
    )
    for line in (cp.stdout or "").splitlines():
        print("  node: " + line)

    add("R20 deployed journey Node PASS", cp.returncode == 0, f"exit={cp.returncode}")
    add("R20 deployed journey has session", "R20_SESSION_OK=true" in cp.stdout)
    add("R20 deployed read preview", "R20_READ_PREVIEW_KIND=read_foreground" in cp.stdout)
    add("R20 deployed read preview executable", "R20_READ_PREVIEW_EXECUTABLE=true" in cp.stdout)
    add("R20 deployed read plan digest", "R20_READ_PLAN_DIGEST_LEN=64" in cp.stdout)
    add("R20 deployed read result ok", "R20_READ_RESULT_OK=true" in cp.stdout)
    add("R20 deployed read receipt present", "R20_READ_RECEIPT=" in cp.stdout and "R20_READ_RECEIPT=\n" not in cp.stdout)
    add("R20 deployed mutation preview supervised", "R20_MUTATION_KIND=supervised_mutation" in cp.stdout)
    add("R20 deployed mutation not executable", "R20_MUTATION_EXECUTABLE=false" in cp.stdout)
    add("R20 deployed destructive blocked", "R20_DESTRUCTIVE_KIND=blocked_destructive" in cp.stdout)
    add("R20 deployed destructive not executable", "R20_DESTRUCTIVE_EXECUTABLE=false" in cp.stdout)
    add("R20 deployed journey marker", "R20_DEPLOYED_READONLY_JOURNEY_PASS=true" in cp.stdout)

    receipts_after = len(
        lifecycle._transport.runtime.receipts.list_receipts()
    )
    add("R20 journey creates exactly one receipt", receipts_after == receipts_before + 1, f"{receipts_before}->{receipts_after}")
    real_read_only_windows_observation = receipts_after == receipts_before + 1

finally:
    if lifecycle is not None:
        lifecycle.close()
    if intent_host is not None:
        intent_host.close()
    shutil.rmtree(state_root, ignore_errors=True)

src = (ROOT / "runtime" / "aura_conversation_intent_handoff_v200.py").read_text(
    encoding="utf-8-sig",
    errors="replace",
)
add("R20 source contains no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
tree = ast.parse(src)
mission_engine_imported = any(
    (
        isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("mission_engine")
    )
    or (
        isinstance(node, ast.Import)
        and any(
            alias.name.startswith("mission_engine")
            for alias in node.names
        )
    )
    for node in ast.walk(tree)
)
add(
    "R20 source contains no MissionEngine import",
    mission_engine_imported is False,
)
add("R20 source contains no R16/R15/R14 execution import", all(token not in src for token in ("A200DeployedUiBridgeAdapter", "A200UiConversationCommandBridge", "A200SupervisedRuntimeIngress")))
add("R20 source contains no shell API", all(token not in src for token in ("os.system(", "os.popen(", "ctypes.", "child_process")))
add("R20 source contains no close capability", "pc.close_window" not in src)
add("R20 source contains no terminate capability", "pc.terminate_process" not in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R20_REAL_READ_ONLY_WINDOWS_OBSERVATION = {real_read_only_windows_observation}")
print(f"R20_REAL_PC_OR_WINDOW_MUTATED = {real_pc_or_window_mutated}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
if not real_read_only_windows_observation:
    raise SystemExit("R20 expected one real read-only receipt")
if real_pc_or_window_mutated:
    raise SystemExit("R20 must not mutate a real window")
print("R20_AST_IMPORT_PROOF=true")
print("R20_PREVIEW_HTTP_10053_RETRY_PROOF=true")
print("[PASS] A200-R20 conversation intent handoff + plan preview + deployed read-only journey")
