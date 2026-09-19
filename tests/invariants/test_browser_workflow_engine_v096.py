from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from integrations.browser import BrowserProvider, BrowserProviderResult
from runtime.browser_workflows import BrowserWorkflowEngine

PROVIDER = ROOT / "integrations" / "browser" / "provider.py"
ENGINE = ROOT / "runtime" / "browser_workflows.py"

EXPECTED_PROVIDER = "fee06ec1a9651687aacd93669114003d03618fa2ee85c171632abdeb232cdaf8"
EXPECTED_ENGINE = "cb92861f65a719810c77fb50c8640af8d691b9d289ac83bfc229e602355700d1"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert AURA_VERSION == "0.9.5"
assert sha(PROVIDER) == EXPECTED_PROVIDER
assert sha(ENGINE) == EXPECTED_ENGINE

def fake_search(query):
    return [{"title": "Synthetic", "url": "https://example.test/result", "query": query}]

def fake_read(url):
    return {
        "final_url": url,
        "content": "<html><body>synthetic fixture</body></html>",
        "status": 200,
    }

provider = BrowserProvider(
    search_adapter=fake_search,
    read_adapter=fake_read,
)
engine = BrowserWorkflowEngine(provider)

success = engine.execute(
    [
        {"capability": "browser.search", "args": {"query": "AURA"}},
        {"capability": "browser.read", "args": {"url": "https://example.test/page"}},
    ]
)
assert success.status == "SUCCESS"
assert success.complete is True
assert success.steps_completed == 2
assert len(success.evidence) == 2
assert all(item.get("source_url") for item in success.evidence)

waiting = engine.execute(
    [
        {"capability": "browser.read", "args": {"url": "https://example.test/form"}},
        {"capability": "browser.submit", "args": {"selector": "form"}},
    ]
)
assert waiting.status == "WAITING_CONFIRMATION"
assert waiting.complete is False
assert waiting.steps_completed == 1
assert waiting.pending_step["capability"] == "browser.submit"
assert waiting.pending_step["confirmation_required"] is True

denied = engine.execute(
    [{"capability": "browser.captcha_bypass", "args": {}}]
)
assert denied.status == "DENIED_OUT_OF_SCOPE"
assert denied.complete is False

too_many = engine.execute(
    [
        {"capability": "browser.read", "args": {"url": "https://example.test/" + str(i)}}
        for i in range(9)
    ]
)
assert too_many.status == "INVALID_WORKFLOW"
assert too_many.error == "max_8_steps"

empty = engine.execute([])
assert empty.status == "INVALID_WORKFLOW"
assert empty.error == "steps_required"

class NoEvidenceProvider:
    def execute(self, capability, **kwargs):
        return BrowserProviderResult(
            ok=True,
            status="SUCCESS",
            capability=capability,
            data={"ok": True},
            evidence=None,
        )

no_evidence = BrowserWorkflowEngine(NoEvidenceProvider()).execute(
    [{"capability": "browser.read", "args": {"url": "https://example.test"}}]
)
assert no_evidence.status == "EVIDENCE_REQUIRED"
assert no_evidence.complete is False
assert no_evidence.error == "successful_step_without_evidence"

print("[PASS] BrowserWorkflowEngine v0.9.6 backend skeleton")
print("[PASS] Read-only workflow requires evidence for every successful step")
print("[PASS] State-changing workflow pauses before execution")
print("[PASS] CAPTCHA bypass denied")
print("[PASS] Missing evidence fails closed")
print("[PASS] Maximum initial steps = 8")
