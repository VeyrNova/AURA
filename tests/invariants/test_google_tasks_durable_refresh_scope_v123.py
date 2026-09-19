from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
p=ROOT/"accounts"/"google_tasks_oauth_v123.py"
s=p.read_text(encoding="utf-8-sig")
assert 'access_type="offline"' in s
assert 'prompt="consent"' in s
assert 'include_granted_scopes="true"' in s
assert "_assert_tasks_scope_v123" in s
assert s.index("credentials.refresh(Request())") < s.index(
    "service.secrets.set_secret(current.credential_ref, credentials.to_json())"
)
from accounts.google_tasks_oauth_v123 import _assert_tasks_scope_v123, GOOGLE_TASKS_SCOPE_V123
class Good:
    granted_scopes=(GOOGLE_TASKS_SCOPE_V123,)
class Bad:
    granted_scopes=("https://www.googleapis.com/auth/calendar",)
_assert_tasks_scope_v123(Good())
try:
    _assert_tasks_scope_v123(Bad())
except RuntimeError:
    pass
else:
    raise AssertionError("missing Tasks scope must require re-consent")
print("[PASS] durable OAuth requests offline explicit consent")
print("[PASS] refresh forced before credential persistence")
print("[PASS] missing granted Tasks scope rejected")
