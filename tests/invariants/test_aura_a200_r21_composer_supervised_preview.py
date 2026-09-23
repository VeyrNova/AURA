from __future__ import annotations

import base64
import json
import re
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

from runtime.aura_composer_intent_seam_binding_v200 import (
    A200_R21_MARKER,
    ARBITRARY_DOM_CAPTURE_ENABLED,
    COMPOSER_SUBMIT_INTERCEPTION_ENABLED,
    COMPOSER_TEXT_MUTATION_ENABLED,
    DIRECT_EXECUTION_ENABLED,
    READ_ONLY_DISCOVERY,
    assert_r21_discovery_contract,
    discover_composer_seam,
)
from runtime.aura_conversation_intent_handoff_v200 import (
    A200IntentPreviewHost,
)
from runtime.aura_ui_host_lifecycle_v200 import (
    A200UiHostLifecycle,
)

UI_ROOT = Path(
    r"C:\Users\leclerc\AppData\Local\AURA\ui\v0.7.2.2-rc4.2"
)
R17 = UI_ROOT / "dist" / "assets" / "aura-a200-supervised-bridge-ui.js"
R18 = UI_ROOT / "dist" / "assets" / "aura-a200-supervised-host-transport.js"
R20 = UI_ROOT / "dist" / "assets" / "aura-a200-conversation-intent-preview.js"
R21 = UI_ROOT / "dist" / "assets" / "aura-a200-composer-supervised-plan.js"
TOKEN_FILE = ROOT / "data" / "a200_runtime" / "r18_ui_transport_token.txt"
NODE_HARNESS_B64 = "Y29uc3QgZnMgPSByZXF1aXJlKCJmcyIpOwpjb25zdCBodHRwID0gcmVxdWlyZSgiaHR0cCIpOwpjb25zdCB2bSA9IHJlcXVpcmUoInZtIik7Cgpjb25zdCBSMTcgPSBwcm9jZXNzLmFyZ3ZbMl07CmNvbnN0IFIxOCA9IHByb2Nlc3MuYXJndlszXTsKY29uc3QgUjIwID0gcHJvY2Vzcy5hcmd2WzRdOwpjb25zdCBSMjEgPSBwcm9jZXNzLmFyZ3ZbNV07Cgpjb25zdCBsaXN0ZW5lcnMgPSBuZXcgTWFwKCk7CgpjbGFzcyBDdXN0b21FdmVudCB7CiAgY29uc3RydWN0b3IodHlwZSwgb3B0aW9ucyA9IHt9KSB7CiAgICB0aGlzLnR5cGUgPSB0eXBlOwogICAgdGhpcy5kZXRhaWwgPSBvcHRpb25zLmRldGFpbDsKICB9Cn0KCmNsYXNzIEZha2VNdXRhdGlvbk9ic2VydmVyIHsKICBjb25zdHJ1Y3RvcihmbikgeyB0aGlzLmZuID0gZm47IH0KICBvYnNlcnZlKCkge30KICBkaXNjb25uZWN0KCkge30KfQpnbG9iYWwuTXV0YXRpb25PYnNlcnZlciA9IEZha2VNdXRhdGlvbk9ic2VydmVyOwoKZnVuY3Rpb24gYWRkV2luZG93TGlzdGVuZXIodHlwZSwgZm4pIHsKICBpZiAoIWxpc3RlbmVycy5oYXModHlwZSkpIGxpc3RlbmVycy5zZXQodHlwZSwgW10pOwogIGxpc3RlbmVycy5nZXQodHlwZSkucHVzaChmbik7Cn0KZnVuY3Rpb24gZGlzcGF0Y2hXaW5kb3coZXZlbnQpIHsKICBmb3IgKGNvbnN0IGZuIG9mIFsuLi4obGlzdGVuZXJzLmdldChldmVudC50eXBlKSB8fCBbXSldKSB7CiAgICBmbi5jYWxsKHdpbmRvdywgZXZlbnQpOwogIH0KICByZXR1cm4gdHJ1ZTsKfQoKY2xhc3MgRmFrZU5vZGUgewogIGNvbnN0cnVjdG9yKHNlbGVjdG9yID0gIiIpIHsKICAgIHRoaXMuc2VsZWN0b3IgPSBzZWxlY3RvcjsKICAgIHRoaXMuZGF0YXNldCA9IHt9OwogICAgdGhpcy50ZXh0Q29udGVudCA9ICIiOwogICAgdGhpcy5oaWRkZW4gPSBmYWxzZTsKICAgIHRoaXMuZGlzYWJsZWQgPSBmYWxzZTsKICAgIHRoaXMuaWQgPSAiIjsKICAgIHRoaXMudHlwZSA9ICIiOwogICAgdGhpcy52YWx1ZSA9ICIiOwogICAgdGhpcy5wYXJlbnRFbGVtZW50ID0gbnVsbDsKICAgIHRoaXMuY2hpbGRyZW4gPSBbXTsKICAgIHRoaXMuZXZlbnRzID0ge307CiAgICB0aGlzLl9hdHRycyA9IHt9OwogICAgdGhpcy5fcXVlcmllcyA9IG5ldyBNYXAoKTsKICB9CiAgYWRkRXZlbnRMaXN0ZW5lcih0eXBlLCBmbikgewogICAgaWYgKCF0aGlzLmV2ZW50c1t0eXBlXSkgdGhpcy5ldmVudHNbdHlwZV0gPSBbXTsKICAgIHRoaXMuZXZlbnRzW3R5cGVdLnB1c2goZm4pOwogIH0KICBjbGljaygpIHsKICAgIGZvciAoY29uc3QgZm4gb2YgdGhpcy5ldmVudHMuY2xpY2sgfHwgW10pIHsKICAgICAgZm4uY2FsbCh0aGlzLCB7IHR5cGU6ICJjbGljayIsIHRhcmdldDogdGhpcyB9KTsKICAgIH0KICB9CiAgc2V0QXR0cmlidXRlKG5hbWUsIHZhbHVlKSB7CiAgICB0aGlzLl9hdHRyc1tuYW1lXSA9IFN0cmluZyh2YWx1ZSk7CiAgfQogIGhhc0F0dHJpYnV0ZShuYW1lKSB7CiAgICByZXR1cm4gT2JqZWN0LnByb3RvdHlwZS5oYXNPd25Qcm9wZXJ0eS5jYWxsKHRoaXMuX2F0dHJzLCBuYW1lKTsKICB9CiAgYXBwZW5kQ2hpbGQobm9kZSkgewogICAgbm9kZS5wYXJlbnRFbGVtZW50ID0gdGhpczsKICAgIHRoaXMuY2hpbGRyZW4ucHVzaChub2RlKTsKICAgIGlmIChub2RlLmlkKSBkb2N1bWVudC5fYnlJZC5zZXQobm9kZS5pZCwgbm9kZSk7CiAgICByZXR1cm4gbm9kZTsKICB9CiAgcXVlcnlTZWxlY3RvcihzZWxlY3RvcikgewogICAgaWYgKHNlbGVjdG9yID09PSAiW2RhdGEtYXVyYS1hMjAwLXIyMS1wbGFuXSIpIHsKICAgICAgcmV0dXJuIHRoaXMuY2hpbGRyZW4uZmluZCgKICAgICAgICBuID0+IG4uaGFzQXR0cmlidXRlICYmCiAgICAgICAgICBuLmhhc0F0dHJpYnV0ZSgiZGF0YS1hdXJhLWEyMDAtcjIxLXBsYW4iKQogICAgICApIHx8IG51bGw7CiAgICB9CiAgICBpZiAoIXRoaXMuX3F1ZXJpZXMuaGFzKHNlbGVjdG9yKSkgewogICAgICB0aGlzLl9xdWVyaWVzLnNldChzZWxlY3RvciwgbmV3IEZha2VOb2RlKHNlbGVjdG9yKSk7CiAgICB9CiAgICByZXR1cm4gdGhpcy5fcXVlcmllcy5nZXQoc2VsZWN0b3IpOwogIH0KfQoKY2xhc3MgRmFrZVJvb3QgZXh0ZW5kcyBGYWtlTm9kZSB7CiAgY29uc3RydWN0b3IoKSB7CiAgICBzdXBlcigicm9vdCIpOwogICAgdGhpcy5faHRtbCA9ICIiOwogIH0KICBzZXQgaW5uZXJIVE1MKHZhbHVlKSB7IHRoaXMuX2h0bWwgPSB2YWx1ZTsgfQogIGdldCBpbm5lckhUTUwoKSB7IHJldHVybiB0aGlzLl9odG1sOyB9Cn0KCmNvbnN0IGNvbXBvc2VyUGFyZW50ID0gbmV3IEZha2VOb2RlKCJjb21wb3Nlci1wYXJlbnQiKTsKY29uc3QgY29tcG9zZXJJbnB1dCA9IG5ldyBGYWtlTm9kZSgiY29tcG9zZXItaW5wdXQiKTsKY29tcG9zZXJJbnB1dC52YWx1ZSA9ICJtaW5pbWlzZSBsYSBmZW7DqnRyZSBhY3RpdmUiOwpjb21wb3NlclBhcmVudC5hcHBlbmRDaGlsZChjb21wb3NlcklucHV0KTsKCmdsb2JhbC5DdXN0b21FdmVudCA9IEN1c3RvbUV2ZW50OwpnbG9iYWwud2luZG93ID0gewogIGFkZEV2ZW50TGlzdGVuZXI6IGFkZFdpbmRvd0xpc3RlbmVyLAogIGRpc3BhdGNoRXZlbnQ6IGRpc3BhdGNoV2luZG93Cn07CgpnbG9iYWwuZG9jdW1lbnQgPSB7CiAgcmVhZHlTdGF0ZTogImNvbXBsZXRlIiwKICBfYnlJZDogbmV3IE1hcCgpLAogIGJvZHk6IG5ldyBGYWtlTm9kZSgiYm9keSIpLAogIGNvbnRhaW5zKG5vZGUpIHsgcmV0dXJuICEhbm9kZTsgfSwKICBnZXRFbGVtZW50QnlJZChpZCkgewogICAgcmV0dXJuIHRoaXMuX2J5SWQuZ2V0KGlkKSB8fCBudWxsOwogIH0sCiAgY3JlYXRlRWxlbWVudCh0YWcpIHsKICAgIHJldHVybiB0YWcgPT09ICJzZWN0aW9uIgogICAgICA/IG5ldyBGYWtlUm9vdCgpCiAgICAgIDogbmV3IEZha2VOb2RlKHRhZyk7CiAgfSwKICBhZGRFdmVudExpc3RlbmVyKCkge30sCiAgcXVlcnlTZWxlY3RvcihzZWxlY3RvcikgewogICAgaWYgKAogICAgICBzZWxlY3RvciA9PT0gIltkYXRhLWF1cmEtY29tcG9zZXJdIHRleHRhcmVhIgogICAgKSB7CiAgICAgIHJldHVybiBjb21wb3NlcklucHV0OwogICAgfQogICAgcmV0dXJuIG51bGw7CiAgfQp9OwoKZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZCA9IGZ1bmN0aW9uKG5vZGUpIHsKICBub2RlLnBhcmVudEVsZW1lbnQgPSB0aGlzOwogIHRoaXMuY2hpbGRyZW4ucHVzaChub2RlKTsKICBpZiAobm9kZS5pZCkgZG9jdW1lbnQuX2J5SWQuc2V0KG5vZGUuaWQsIG5vZGUpOwogIHJldHVybiBub2RlOwp9OwoKZnVuY3Rpb24gcmVxdWVzdFdpdGhSZXRyeSh1cmwsIG9wdGlvbnMgPSB7fSwgYXR0ZW1wdCA9IDApIHsKICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4gewogICAgY29uc3QgdSA9IG5ldyBVUkwodXJsKTsKICAgIGNvbnN0IGJvZHkgPSBvcHRpb25zLmJvZHkgfHwgIiI7CiAgICBjb25zdCBoZWFkZXJzID0gT2JqZWN0LmFzc2lnbih7fSwgb3B0aW9ucy5oZWFkZXJzIHx8IHt9KTsKICAgIGhlYWRlcnNbIkNvbnRlbnQtTGVuZ3RoIl0gPSBCdWZmZXIuYnl0ZUxlbmd0aChib2R5KTsKICAgIGlmICghT2JqZWN0LmtleXMoaGVhZGVycykuc29tZShrID0+IGsudG9Mb3dlckNhc2UoKSA9PT0gIm9yaWdpbiIpKSB7CiAgICAgIGhlYWRlcnNbIk9yaWdpbiJdID0gIm51bGwiOwogICAgfQoKICAgIGNvbnN0IHJlcSA9IGh0dHAucmVxdWVzdCgKICAgICAgewogICAgICAgIGhvc3RuYW1lOiB1Lmhvc3RuYW1lLAogICAgICAgIHBvcnQ6IHUucG9ydCwKICAgICAgICBwYXRoOiB1LnBhdGhuYW1lICsgdS5zZWFyY2gsCiAgICAgICAgbWV0aG9kOiBvcHRpb25zLm1ldGhvZCB8fCAiR0VUIiwKICAgICAgICBoZWFkZXJzCiAgICAgIH0sCiAgICAgIChyZXMpID0+IHsKICAgICAgICBsZXQgZGF0YSA9ICIiOwogICAgICAgIHJlcy5zZXRFbmNvZGluZygidXRmOCIpOwogICAgICAgIHJlcy5vbigiZGF0YSIsIGNodW5rID0+IGRhdGEgKz0gY2h1bmspOwogICAgICAgIHJlcy5vbigiZW5kIiwgKCkgPT4gewogICAgICAgICAgcmVzb2x2ZSh7CiAgICAgICAgICAgIG9rOiByZXMuc3RhdHVzQ29kZSA+PSAyMDAgJiYgcmVzLnN0YXR1c0NvZGUgPCAzMDAsCiAgICAgICAgICAgIHN0YXR1czogcmVzLnN0YXR1c0NvZGUsCiAgICAgICAgICAgIGFzeW5jIGpzb24oKSB7CiAgICAgICAgICAgICAgcmV0dXJuIEpTT04ucGFyc2UoZGF0YSB8fCAie30iKTsKICAgICAgICAgICAgfQogICAgICAgICAgfSk7CiAgICAgICAgfSk7CiAgICAgIH0KICAgICk7CgogICAgcmVxLm9uKCJlcnJvciIsIChlcnIpID0+IHsKICAgICAgY29uc3QgdHJhbnNpZW50ID0KICAgICAgICBlcnIgJiYKICAgICAgICAoZXJyLmNvZGUgPT09ICJFQ09OTlJFU0VUIiB8fAogICAgICAgICBlcnIuY29kZSA9PT0gIkVDT05OQUJPUlRFRCIpOwogICAgICBpZiAodHJhbnNpZW50ICYmIGF0dGVtcHQgPCAxKSB7CiAgICAgICAgc2V0VGltZW91dCgoKSA9PiB7CiAgICAgICAgICByZXF1ZXN0V2l0aFJldHJ5KHVybCwgb3B0aW9ucywgYXR0ZW1wdCArIDEpCiAgICAgICAgICAgIC50aGVuKHJlc29sdmUsIHJlamVjdCk7CiAgICAgICAgfSwgMTUwKTsKICAgICAgICByZXR1cm47CiAgICAgIH0KICAgICAgcmVqZWN0KGVycik7CiAgICB9KTsKCiAgICBpZiAoYm9keSkgcmVxLndyaXRlKGJvZHkpOwogICAgcmVxLmVuZCgpOwogIH0pOwp9Cmdsb2JhbC5mZXRjaCA9IHJlcXVlc3RXaXRoUmV0cnk7CgpsZXQgc3RhdHVzUmVzcG9uc2UgPSBudWxsOwpsZXQgYXBwcm92YWxSZXF1aXJlZCA9IG51bGw7CmxldCBjYW5jZWxSZXNwb25zZSA9IG51bGw7Cgp3aW5kb3cuYWRkRXZlbnRMaXN0ZW5lcigiYXVyYTphMjAwLXN1cGVydmlzZWQtcmVzcG9uc2UiLCAoZXZlbnQpID0+IHsKICBjb25zdCBkID0gZXZlbnQuZGV0YWlsIHx8IHt9OwogIGlmIChkLmtpbmQgPT09ICJydW50aW1lLnN0YXR1cyIpIHN0YXR1c1Jlc3BvbnNlID0gZDsKICBpZiAoZC5raW5kID09PSAiYXBwcm92YWwucmVxdWlyZWQiKSBhcHByb3ZhbFJlcXVpcmVkID0gZDsKICBpZiAoZC5raW5kID09PSAibWlzc2lvbi5jYW5jZWxsZWQiKSBjYW5jZWxSZXNwb25zZSA9IGQ7Cn0pOwoKZnVuY3Rpb24gd2FpdEZvcihwcmVkaWNhdGUsIHRpbWVvdXRNcykgewogIGNvbnN0IHN0YXJ0ID0gRGF0ZS5ub3coKTsKICByZXR1cm4gbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4gewogICAgY29uc3QgdGltZXIgPSBzZXRJbnRlcnZhbCgoKSA9PiB7CiAgICAgIHRyeSB7CiAgICAgICAgaWYgKHByZWRpY2F0ZSgpKSB7CiAgICAgICAgICBjbGVhckludGVydmFsKHRpbWVyKTsKICAgICAgICAgIHJlc29sdmUoKTsKICAgICAgICAgIHJldHVybjsKICAgICAgICB9CiAgICAgICAgaWYgKERhdGUubm93KCkgLSBzdGFydCA+IHRpbWVvdXRNcykgewogICAgICAgICAgY2xlYXJJbnRlcnZhbCh0aW1lcik7CiAgICAgICAgICByZWplY3QobmV3IEVycm9yKCJ0aW1lb3V0IikpOwogICAgICAgIH0KICAgICAgfSBjYXRjaCAoZXJyKSB7CiAgICAgICAgY2xlYXJJbnRlcnZhbCh0aW1lcik7CiAgICAgICAgcmVqZWN0KGVycik7CiAgICAgIH0KICAgIH0sIDI1KTsKICB9KTsKfQoKKGFzeW5jICgpID0+IHsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMTgsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIxOCB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMTcsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIxNyB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMjAsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIyMCB9KTsKICB2bS5ydW5JblRoaXNDb250ZXh0KGZzLnJlYWRGaWxlU3luYyhSMjEsICJ1dGY4IiksIHsgZmlsZW5hbWU6IFIyMSB9KTsKCiAgYXdhaXQgd2FpdEZvcigoKSA9PiBzdGF0dXNSZXNwb25zZSAhPT0gbnVsbCwgNTAwMCk7CiAgaWYgKHN0YXR1c1Jlc3BvbnNlLm9rICE9PSB0cnVlKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoInJ1bnRpbWUgc3RhdHVzIHVuYXZhaWxhYmxlIik7CiAgfQoKICBjb25zdCBzZWFtID0gd2luZG93LkFVUkFfQTIwMF9DT01QT1NFUl9TVVBFUlZJU0lPTjsKICBpZiAoIXNlYW0pIHRocm93IG5ldyBFcnJvcigiUjIxIHNlYW0gQVBJIG1pc3NpbmciKTsKCiAgY29uc3QgYm91bmQgPSBzZWFtLmJpbmRDb21wb3Nlcihkb2N1bWVudCk7CiAgY29uc29sZS5sb2coIlIyMV9DT01QT1NFUl9CT1VORD0iICsgYm91bmQpOwoKICBjb25zdCBwbGFuQnV0dG9uID0gY29tcG9zZXJQYXJlbnQucXVlcnlTZWxlY3RvcigKICAgICJbZGF0YS1hdXJhLWEyMDAtcjIxLXBsYW5dIgogICk7CiAgaWYgKCFwbGFuQnV0dG9uKSB0aHJvdyBuZXcgRXJyb3IoIlBsYW4gQVVSQSBidXR0b24gbWlzc2luZyIpOwoKICBwbGFuQnV0dG9uLmNsaWNrKCk7CgogIGF3YWl0IHdhaXRGb3IoCiAgICAoKSA9PiB7CiAgICAgIGNvbnN0IHAgPSBzZWFtLmdldEFjdGl2ZVByZXZpZXcoKTsKICAgICAgcmV0dXJuIHAgJiYgcC5pbnRlbnRfa2luZCA9PT0gInN1cGVydmlzZWRfbXV0YXRpb24iOwogICAgfSwKICAgIDUwMDAKICApOwoKICBjb25zdCBwcmV2aWV3ID0gc2VhbS5nZXRBY3RpdmVQcmV2aWV3KCk7CiAgY29uc29sZS5sb2coIlIyMV9QUkVWSUVXX0tJTkQ9IiArIHByZXZpZXcuaW50ZW50X2tpbmQpOwogIGNvbnNvbGUubG9nKCJSMjFfUFJFVklFV19FWEVDVVRBQkxFPSIgKyBwcmV2aWV3LmV4ZWN1dGlvbl9hbGxvd2VkKTsKICBjb25zb2xlLmxvZygKICAgICJSMjFfUFJFVklFV19TVVBFUlZJU0VEPSIgKwogICAgcHJldmlldy5yZXF1aXJlc19zdXBlcnZpc2VkX3BhdGgKICApOwogIGNvbnNvbGUubG9nKAogICAgIlIyMV9QTEFOX0RJR0VTVF9MRU49IiArCiAgICBTdHJpbmcocHJldmlldy5wbGFuX2RpZ2VzdCB8fCAiIikubGVuZ3RoCiAgKTsKCiAgaWYgKHByZXZpZXcuZXhlY3V0aW9uX2FsbG93ZWQgIT09IGZhbHNlKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoIm11dGF0aW9uIHByZXZpZXcgYmVjYW1lIGV4ZWN1dGFibGUiKTsKICB9CgogIGNvbnN0IHByZXBhcmVkID0gYXdhaXQgc2VhbS5wcmVwYXJlU3VwZXJ2aXNlZE11dGF0aW9uKCk7CgogIGNvbnNvbGUubG9nKCJSMjFfUFJFUEFSRV9LSU5EPSIgKyBwcmVwYXJlZC5raW5kKTsKICBjb25zb2xlLmxvZygKICAgICJSMjFfUFJFUEFSRV9QSEFTRT0iICsKICAgICgoKHByZXBhcmVkLnBheWxvYWQgfHwge30pLnBoYXNlKSB8fCAiIikKICApOwoKICBhd2FpdCB3YWl0Rm9yKAogICAgKCkgPT4gYXBwcm92YWxSZXF1aXJlZCAhPT0gbnVsbCwKICAgIDUwMDAKICApOwoKICBjb25zdCBwcmVzZW50YXRpb24gPSBzZWFtLmdldEFwcHJvdmFsUHJlc2VudGF0aW9uKCk7CiAgaWYgKCFwcmVzZW50YXRpb24pIHsKICAgIHRocm93IG5ldyBFcnJvcigiYXBwcm92YWwgcHJlc2VudGF0aW9uIG1pc3NpbmcgaW4gUjIxIHN0YXRlIik7CiAgfQoKICBjb25zb2xlLmxvZygiUjIxX0FQUFJPVkFMX1JFUVVJUkVEPXRydWUiKTsKICBjb25zb2xlLmxvZygKICAgICJSMjFfQVBQUk9WQUxfUkVWRVJTSUJMRT0iICsKICAgIHByZXNlbnRhdGlvbi5yZXZlcnNpYmxlCiAgKTsKICBjb25zb2xlLmxvZygKICAgICJSMjFfQVBQUk9WQUxfRVhQTElDSVQ9IiArCiAgICBwcmVzZW50YXRpb24ucmVxdWlyZXNfZXhwbGljaXRfY29uZmlybWF0aW9uCiAgKTsKICBjb25zb2xlLmxvZygKICAgICJSMjFfQVBQUk9WQUxfTUlTU0lPTj0iICsKICAgIChwcmVzZW50YXRpb24ubWlzc2lvbl9pZCB8fCAiIikKICApOwogIGNvbnNvbGUubG9nKAogICAgIlIyMV9BUFBST1ZBTF9QUkVTRU5UQVRJT05fRElHRVNUX0xFTj0iICsKICAgIFN0cmluZyhwcmVzZW50YXRpb24ucHJlc2VudGF0aW9uX2RpZ2VzdCB8fCAiIikubGVuZ3RoCiAgKTsKICBjb25zb2xlLmxvZygKICAgICJSMjFfQVBQUk9WQUxfQ0hBTExFTkdFX0RJR0VTVF9MRU49IiArCiAgICBTdHJpbmcocHJlc2VudGF0aW9uLmNoYWxsZW5nZV9kaWdlc3QgfHwgIiIpLmxlbmd0aAogICk7CgogIGNvbnN0IHJlc29sdmVkVGFyZ2V0ID0gc2VhbS5nZXRSZXNvbHZlZFRhcmdldCgpIHx8IHt9OwogIGNvbnNvbGUubG9nKCJSMjFfVEFSR0VUX0hXTkQ9IiArIChyZXNvbHZlZFRhcmdldC5od25kIHx8ICIiKSk7CiAgY29uc29sZS5sb2coCiAgICAiUjIxX1RBUkdFVF9NQVRDSD0iICsKICAgICgKICAgICAgcHJlc2VudGF0aW9uLnRhcmdldF9od25kID09PSByZXNvbHZlZFRhcmdldC5od25kICYmCiAgICAgIHByZXNlbnRhdGlvbi50YXJnZXRfdGl0bGUgPT09IHJlc29sdmVkVGFyZ2V0LnRpdGxlCiAgICApCiAgKTsKCiAgaWYgKHByZXNlbnRhdGlvbi5yZXZlcnNpYmxlICE9PSB0cnVlKSB7CiAgICB0aHJvdyBuZXcgRXJyb3IoInByZXNlbnRhdGlvbiBub3QgcmV2ZXJzaWJsZSIpOwogIH0KICBpZiAocHJlc2VudGF0aW9uLnJlcXVpcmVzX2V4cGxpY2l0X2NvbmZpcm1hdGlvbiAhPT0gdHJ1ZSkgewogICAgdGhyb3cgbmV3IEVycm9yKCJwcmVzZW50YXRpb24gbm90IGV4cGxpY2l0Iik7CiAgfQoKICBjb25zdCBjYW5jZWxsZWQgPSBhd2FpdCBzZWFtLmNhbmNlbFByZXBhcmVkTWlzc2lvbigpOwogIGF3YWl0IHdhaXRGb3IoKCkgPT4gY2FuY2VsUmVzcG9uc2UgIT09IG51bGwsIDUwMDApOwoKICBjb25zb2xlLmxvZygiUjIxX0NBTkNFTF9LSU5EPSIgKyBjYW5jZWxsZWQua2luZCk7CiAgY29uc29sZS5sb2coCiAgICAiUjIxX0NBTkNFTF9TVEFUVVNfQUZURVI9IiArCiAgICAoKChjYW5jZWxsZWQucGF5bG9hZCB8fCB7fSkuc3RhdHVzX2FmdGVyKSB8fCAiIikKICApOwogIGNvbnNvbGUubG9nKCJSMjFfQ0FOQ0VMTEVEPXRydWUiKTsKICBjb25zb2xlLmxvZygiUjIxX0VYUExJQ0lUX0FQUFJPVkFMX05PVF9TRU5UPXRydWUiKTsKICBjb25zb2xlLmxvZygiUjIxX0RFUExPWUVEX1NVUEVSVklTRURfUFJFVklFV19QQVNTPXRydWUiKTsKfSkoKS5jYXRjaCgoZXJyKSA9PiB7CiAgY29uc29sZS5lcnJvcihlcnIgJiYgZXJyLnN0YWNrID8gZXJyLnN0YWNrIDogU3RyaW5nKGVycikpOwogIHByb2Nlc3MuZXhpdENvZGUgPSAxOwp9KTsK"

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


add("R21 marker", A200_R21_MARKER == "AURA_A200_R21_ACTUAL_COMPOSER_SEAM_BINDING_V1")
add("R21 discovery read-only", READ_ONLY_DISCOVERY is True)
add("R21 direct execution disabled", DIRECT_EXECUTION_ENABLED is False)
add("R21 composer submit interception disabled", COMPOSER_SUBMIT_INTERCEPTION_ENABLED is False)
add("R21 composer text mutation disabled", COMPOSER_TEXT_MUTATION_ENABLED is False)
add("R21 arbitrary DOM capture disabled", ARBITRARY_DOM_CAPTURE_ENABLED is False)
assert_r21_discovery_contract()
add("R21 discovery safety contract assertion", True)

descriptor = discover_composer_seam().to_dict()
add("R21 composer descriptor schema", descriptor["schema"] == "aura.a200.r21.composer-seam-descriptor.v1")
add("R21 certified composer path exact", descriptor["relative_path"] == "dist/assets/aura-p0823-composer-single-surface.js")
add("R21 certified composer hash exact", descriptor["sha256"] == "1697cf5f05e174347f022e72b26e083ba5be1a8b01ad67b3a483cd65177c8552")
add("R21 composer semantic tokens present", descriptor["composer_token_count"] >= 1)
add("R21 binding mode explicit adjacent button", descriptor["binding_mode"] == "adjacent-explicit-plan-button")
add("R21 submit interception false in descriptor", descriptor["submit_interception"] is False)
add("R21 direct execution false in descriptor", descriptor["direct_execution"] is False)

token = TOKEN_FILE.read_text(encoding="ascii").strip()
state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r21_"))
lifecycle = None
intent_host = None

try:
    lifecycle = A200UiHostLifecycle(
        state_root=state_root / "runtime",
        token=token,
        host="127.0.0.1",
        port=18765,
        owner_id="r21-supervised-preview",
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

    node = shutil.which("node")
    add("Node available for R21 deployed journey", bool(node), node or "MISSING")
    if not node:
        raise RuntimeError("Node required for R21")

    harness = state_root / "r21_journey.js"
    harness.write_bytes(base64.b64decode(NODE_HARNESS_B64))

    cp = subprocess.run(
        [
            node,
            str(harness),
            str(R17),
            str(R18),
            str(R20),
            str(R21),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    for line in (cp.stdout or "").splitlines():
        print("  node: " + line)

    add("R21 deployed journey Node PASS", cp.returncode == 0, f"exit={cp.returncode}")
    add("R21 actual composer bound", "R21_COMPOSER_BOUND=true" in cp.stdout)
    add("R21 supervised mutation preview", "R21_PREVIEW_KIND=supervised_mutation" in cp.stdout)
    add("R21 mutation preview not executable", "R21_PREVIEW_EXECUTABLE=false" in cp.stdout)
    add("R21 mutation preview supervised", "R21_PREVIEW_SUPERVISED=true" in cp.stdout)
    add("R21 plan digest SHA256", "R21_PLAN_DIGEST_LEN=64" in cp.stdout)
    add("R21 prepare response kind exact", "R21_PREPARE_KIND=approval.required" in cp.stdout)
    add("R21 prepare response phase exact", "R21_PREPARE_PHASE=waiting_confirmation" in cp.stdout)
    add("R21 approval presentation reached", "R21_APPROVAL_REQUIRED=true" in cp.stdout)
    add("R21 approval reversible", "R21_APPROVAL_REVERSIBLE=true" in cp.stdout)
    add("R21 approval explicit", "R21_APPROVAL_EXPLICIT=true" in cp.stdout)
    add("R21 approval presentation digest SHA256", "R21_APPROVAL_PRESENTATION_DIGEST_LEN=64" in cp.stdout)
    add("R21 approval challenge digest SHA256", "R21_APPROVAL_CHALLENGE_DIGEST_LEN=64" in cp.stdout)
    add("R21 approval mission id present", "R21_APPROVAL_MISSION=" in cp.stdout and "R21_APPROVAL_MISSION=\n" not in cp.stdout)
    add("R21 exact target hwnd resolved", "R21_TARGET_HWND=" in cp.stdout and "R21_TARGET_HWND=\n" not in cp.stdout)
    add("R21 approval target matches resolved foreground", "R21_TARGET_MATCH=true" in cp.stdout)
    add("R21 cancel response kind exact", "R21_CANCEL_KIND=mission.cancelled" in cp.stdout)
    add("R21 cancel status exact", "R21_CANCEL_STATUS_AFTER=cancelled" in cp.stdout)
    add("R21 prepared mission explicitly cancelled", "R21_CANCELLED=true" in cp.stdout)
    add("R21 did not send explicit approval", "R21_EXPLICIT_APPROVAL_NOT_SENT=true" in cp.stdout)
    add("R21 deployed supervised preview marker", "R21_DEPLOYED_SUPERVISED_PREVIEW_PASS=true" in cp.stdout)

    mission_match = re.search(
        r"R21_APPROVAL_MISSION=([^\r\n]+)",
        cp.stdout,
    )
    mission_id = mission_match.group(1).strip() if mission_match else ""
    add("R21 mission id parsed for engine verification", bool(mission_id), mission_id or "MISSING")
    if mission_id:
        mission = lifecycle._transport.runtime.engine.get_mission(mission_id)
        add(
            "R21 MissionEngine persisted cancelled state",
            str(mission.status) == "cancelled",
            str(mission.status),
        )
        add(
            "R21 no crash-recovery journal armed",
            lifecycle._transport.runtime.crash_journal.get_pending(mission_id) is None,
        )

    receipts_after = len(
        lifecycle._transport.runtime.receipts.list_receipts()
    )
    add(
        "R21 creates exactly two pre-approval read-only receipts",
        receipts_after == receipts_before + 2,
        f"{receipts_before}->{receipts_after}",
    )
    real_read_only_windows_observation = (
        receipts_after == receipts_before + 2
    )

finally:
    if intent_host is not None:
        intent_host.close()
    if lifecycle is not None:
        lifecycle.close()
    shutil.rmtree(state_root, ignore_errors=True)

src = (
    ROOT / "runtime" / "aura_composer_intent_seam_binding_v200.py"
).read_text(encoding="utf-8-sig", errors="replace")
add("R21 runtime source contains no subprocess", "import subprocess" not in src and "from subprocess" not in src)
add("R21 runtime source contains no MissionEngine import", "from mission_engine" not in src and "import mission_engine" not in src)
add("R21 runtime source contains no shell API", all(token not in src for token in ("os.system(", "os.popen(", "ctypes.", "child_process")))
add("R21 runtime source contains no PC mutation capability", all(token not in src for token in ("pc.minimize_window", "pc.maximize_window", "pc.focus_window", "pc.close_window", "pc.terminate_process")))

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R21_REAL_READ_ONLY_WINDOWS_OBSERVATION = {real_read_only_windows_observation}")
print(f"R21_REAL_PC_OR_WINDOW_MUTATED = {real_pc_or_window_mutated}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if not real_read_only_windows_observation:
    raise SystemExit("R21 expected exactly two pre-approval read-only receipts")
if real_pc_or_window_mutated:
    raise SystemExit("R21 must not mutate a real window")
print("R21_R15_PAYLOAD_APPROVAL_CONTRACT_PROOF=true")
print("R21_TWO_PREAPPROVAL_READ_RECEIPTS_PROOF=true")
print("[PASS] A200-R21 actual composer seam + supervised reversible preview + approval presentation/cancel journey")
