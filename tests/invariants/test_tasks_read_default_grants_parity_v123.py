from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from integrations.registry import IntegrationRegistry
from runtime.integration_permissions_tasks_v123 import ALLOW,DENY,REQUIRE_CONFIRMATION
from security.permissions import DEFAULT_GRANTED_PERMISSIONS,Permission

class MissingGrantsSecurity:
    def authorize(self, action, params, user_confirmed=False):
        return "DENY"

reg=object.__new__(IntegrationRegistry)
reg.security_engine=MissingGrantsSecurity()

assert reg._authorize("tasks.list",{},user_confirmed=False)==ALLOW
assert reg._authorize("tasks.tasklists",{},user_confirmed=False)==ALLOW
assert reg._authorize("tasks.read",{},user_confirmed=False)==ALLOW
for cap in ("tasks.create","tasks.update","tasks.complete","tasks.delete"):
    assert reg._authorize(cap,{},user_confirmed=True)==DENY

class ExplicitGrantSecurity:
    granted_permissions=frozenset(set(DEFAULT_GRANTED_PERMISSIONS)|{Permission.EXTERNAL_NETWORK})
    def authorize(self, action, params, user_confirmed=False):
        return "DENY"

reg2=object.__new__(IntegrationRegistry)
reg2.security_engine=ExplicitGrantSecurity()
assert reg2._authorize("tasks.create",{},user_confirmed=False)==REQUIRE_CONFIRMATION
assert reg2._authorize("tasks.create",{},user_confirmed=True)==ALLOW

source=(ROOT/"integrations"/"registry.py").read_text(encoding="utf-8-sig")
assert source.count("AURA_V123_TASKS_READ_DEFAULT_GRANTS_PARITY_BEGIN")==1
print("[PASS] production missing-grants Tasks READ => ALLOW")
print("[PASS] Tasks mutations remain denied by default")
print("[PASS] explicit mutation grant still requires confirmation")
