from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from integrations.browser import BrowserProvider

PROVIDER = ROOT / "integrations" / "browser" / "provider.py"
ENGINE = ROOT / "runtime" / "browser_workflows.py"

EXPECTED_PROVIDER = "fee06ec1a9651687aacd93669114003d03618fa2ee85c171632abdeb232cdaf8"
EXPECTED_ENGINE = "cb92861f65a719810c77fb50c8640af8d691b9d289ac83bfc229e602355700d1"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert AURA_VERSION == "0.9.5"
assert sha(PROVIDER) == EXPECTED_PROVIDER
assert sha(ENGINE) == EXPECTED_ENGINE

calls = {"search": 0, "read": 0}

def fake_search(query):
    calls["search"] += 1
    return [{"title": "Synthetic", "url": "https://example.test/result", "query": query}]

def fake_read(url):
    calls["read"] += 1
    return {
        "final_url": url,
        "content": "<html><body>synthetic fixture</body></html>",
        "status": 200,
    }

provider = BrowserProvider(
    search_adapter=fake_search,
    read_adapter=fake_read,
)

assert set(provider.capabilities()) == {
    "browser.open",
    "browser.navigate",
    "browser.read",
    "browser.extract",
    "browser.search",
    "browser.click",
    "browser.fill",
    "browser.submit",
    "browser.download",
    "browser.workflow",
}

search = provider.execute("browser.search", query="aura")
assert search.ok is True
assert search.status == "SUCCESS"
assert search.evidence
assert search.evidence["state_changed"] is False
assert search.state_changed is False

read = provider.execute("browser.read", url="https://example.test/page")
assert read.ok is True
assert read.status == "SUCCESS"
assert read.evidence
assert read.evidence["source_url"] == "https://example.test/page"
assert read.evidence["final_url"] == "https://example.test/page"
assert read.evidence["optional_content_sha256"]
assert read.state_changed is False

bad = provider.execute("browser.open", url="file:///etc/passwd")
assert bad.ok is False
assert bad.status == "INVALID_REQUEST"
assert bad.error == "valid_http_url_required"

for capability in (
    "browser.click",
    "browser.fill",
    "browser.submit",
    "browser.download",
):
    result = provider.execute(capability)
    assert result.ok is False
    assert result.status == "CONFIRMATION_REQUIRED"
    assert result.confirmation_required is True
    assert result.state_changed is False

for capability in (
    "browser.pay",
    "browser.purchase",
    "browser.transfer",
    "browser.credentials",
    "browser.captcha_bypass",
    "browser.antibot_bypass",
):
    result = provider.execute(capability)
    assert result.ok is False
    assert result.status == "DENIED_OUT_OF_SCOPE"

workflow = provider.execute("browser.workflow")
assert workflow.ok is False
assert workflow.status == "USE_WORKFLOW_ENGINE"

assert calls == {"search": 1, "read": 1}

print("[PASS] BrowserProvider v0.9.6 backend skeleton")
print("[PASS] Read-only actions return evidence")
print("[PASS] State-changing actions return CONFIRMATION_REQUIRED without side effect")
print("[PASS] Out-of-scope actions fail closed")
print("[PASS] No real network used by invariant")
