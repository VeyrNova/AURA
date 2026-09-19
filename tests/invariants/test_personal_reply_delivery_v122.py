from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.aura_core import AuraCore
from runtime.personal_integrations import (
    PersonalIntegrationDispatcher,
    _build_synthetic_runtime_context_v121_fallback,
    register_browser_provider_v096,
)

CORE = ROOT / "core" / "aura_core.py"
MAIN = ROOT / "ui" / "main_window.py"

core_source = CORE.read_text(encoding="utf-8-sig")
main_source = MAIN.read_text(encoding="utf-8-sig")

assert core_source.count("AURA_V122_PERSONAL_REPLY_DELIVERY_BEGIN") == 1
assert core_source.count("AURA_V122_PERSONAL_REPLY_DELIVERY_END") == 1
assert "self.handle_aura_response(_aura_pi_text)" in core_source

tree = ast.parse(core_source, filename=str(CORE))
aura = next(
    n for n in tree.body
    if isinstance(n, ast.ClassDef) and n.name == "AuraCore"
)
try_fn = next(
    n for n in aura.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    and n.name == "try_handle_intent"
)
handle_fn = next(
    n for n in aura.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    and n.name == "handle_aura_response"
)

def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return (left + "." if left else "") + node.attr
    return ""

# The old string-return branch must be gone specifically from try_handle_intent.
old_returns = []
for n in ast.walk(try_fn):
    if isinstance(n, ast.Return):
        v = n.value
        if (
            isinstance(v, ast.Attribute)
            and isinstance(v.value, ast.Name)
            and v.value.id == "_aura_pi_reply"
            and v.attr == "text"
        ):
            old_returns.append(n)
assert not old_returns

# Actual standard response delivery emits the shared AURA event.
handle_calls = [
    dotted(n.func)
    for n in ast.walk(handle_fn)
    if isinstance(n, ast.Call)
]
assert any(name.endswith("event_bus.aura_message.emit") for name in handle_calls)

# UI already consumes the same event for both visual display and voice.
assert "event_bus.aura_message.connect(self._on_aura_message_display)" in main_source
assert "event_bus.aura_message.connect(self._on_aura_message_for_voice)" in main_source

class Security:
    def authorize(self, action, params, user_confirmed=False):
        return "ALLOW"

security = Security()
context = _build_synthetic_runtime_context_v121_fallback(
    security_engine=security,
    timezone_name="Europe/Paris",
)

class BrowserStub:
    def search(self, *args, **kwargs):
        raise AssertionError("browser search must not execute")
    def read(self, *args, **kwargs):
        raise AssertionError("browser read must not execute")

browser = BrowserStub()
if context.registry.get_provider("browser.provider") is None:
    register_browser_provider_v096(
        context.registry,
        search_adapter=browser.search,
        read_adapter=browser.read,
    )

class IntentTrap:
    def __init__(self):
        self.calls = 0
    def detect(self, text):
        self.calls += 1
        return None, {}

class LocalAction:
    def resolve(self, text, explicit_intent=None):
        class P:
            handled = False
            intent = ""
        return P()

class Memory:
    def can_answer_personal_question(self, text):
        return False

class FakeCore:
    def __init__(self, dispatcher):
        self._personal_integration_dispatcher = dispatcher
        self._personal_integration_runtime_context = context
        self._productivity_mission_engine_v097 = None
        self.security_engine = security
        self.intent_manager = IntentTrap()
        self.local_action_context = LocalAction()
        self.memory_manager = Memory()
        self.deliveries = 0
        self.delivery_nonempty = False

    def handle_aura_response(self, text):
        self.deliveries += 1
        self.delivery_nonempty = bool(str(text or "").strip())

cases = (
    "Aura, affiche mes derniers mails",
    "Aura, quels sont mes prochains rendez-vous ?",
    "Aura, affiche mes contacts",
    "Aura, liste mes fichiers Drive",
)

for phrase in cases:
    dispatcher = PersonalIntegrationDispatcher(context=context)
    core = FakeCore(dispatcher)
    result = AuraCore.try_handle_intent(core, phrase, allow_grounding=False)
    assert result is True
    assert core.deliveries == 1
    assert core.delivery_nonempty is True
    assert core.intent_manager.calls == 0

print("[PASS] v1.2.2 personal reply delivery AST invariant")
print("[PASS] handled personal replies return bool True")
print("[PASS] personal reply text is delivered exactly once")
print("[PASS] standard aura_message UI + TTS subscribers remain wired")
print("[PASS] deterministic invariant uses synthetic fallback only")
