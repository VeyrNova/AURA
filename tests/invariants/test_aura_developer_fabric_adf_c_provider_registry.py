from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import os
import sys
import threading
import urllib.request

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_fabric_provider_registry import ProviderRegistry
from runtime.aura_fabric_quota_observatory import QuotaObservatory
from runtime.aura_fabric_http_gateway import GatewayConfig, build_test_service, create_server

REGISTRY_PATH = ROOT / "ci" / "aura_fabric_provider_registry_seed.json"
QUOTA_PATH = ROOT / "ci" / "aura_fabric_free_tier_snapshot_2026_08_30.json"

registry = ProviderRegistry.from_path(REGISTRY_PATH)
quota = QuotaObservatory.from_path(QUOTA_PATH)

assert len(registry.ids()) == 50
assert len(set(registry.ids())) == 50
assert registry.secret_scan()["ok"] is True

seed = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
assert seed["clean_room"] is True
assert seed["external_source_code_reused"] is False
assert seed["source_policy"]["remote_ttl_days"] == 30

snapshot_time = datetime.fromisoformat("2026-08-30T20:10:00+02:00")
public = registry.public_snapshot(now=snapshot_time)
assert public["provider_count"] == 50
assert public["policy_eligible_count"] == 50
assert public["stale_count"] == 0
assert public["local_count"] == 3
assert all("=" not in env for p in public["providers"] for env in p["credential_env_names"])

future = snapshot_time + timedelta(days=31)
stale_public = registry.public_snapshot(now=future)
assert stale_public["stale_count"] == 47
assert stale_public["policy_eligible_count"] == 3
assert all(
    p["policy"]["eligible"] is False
    for p in stale_public["providers"]
    if p["tos_status"] != "local"
)
assert all(
    p["policy"]["eligible"] is True
    for p in stale_public["providers"]
    if p["tos_status"] == "local"
)

quota_now = quota.summary(now=snapshot_time)
assert quota_now["guaranteed_free_tokens_per_month"] == 0
assert quota_now["reference_headline_tokens_per_month"] == 1_300_000_000
assert quota_now["reference_headline_guaranteed"] is False
assert quota_now["reference_headline_independently_verified_by_aura"] is False
assert quota_now["known_token_equivalent_reference_floor_per_month"] == 30_000_000
assert quota_now["convertible_fresh_observations"] == 1
assert quota_now["policy"]["never_convert_requests_or_compute_units_to_tokens"] is True

quota_future = quota.summary(now=snapshot_time + timedelta(days=8))
assert quota_future["known_token_equivalent_reference_floor_per_month"] == 0
assert quota_future["stale_observation_count"] == quota_future["observation_count"]
assert quota_future["reference_headline_stale"] is True

def get_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

service = build_test_service(include_failure_route=False, retries_per_model=2)
config = GatewayConfig(host="127.0.0.1", port=0, retries_per_model=2)
server = create_server(service=service, config=config, host="127.0.0.1", port=0)
thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
thread.start()
host, port = server.server_address[:2]
base = f"http://{host}:{port}"

try:
    status, providers_payload = get_json(base + "/aura/v1/providers")
    assert status == 200
    assert providers_payload["provider_count"] == 50
    assert providers_payload["clean_room"] is True

    status, quotas_payload = get_json(base + "/aura/v1/quotas")
    assert status == 200
    assert quotas_payload["reference_headline_tokens_per_month"] == 1_300_000_000
    assert quotas_payload["reference_headline_guaranteed"] is False

    status, health = get_json(base + "/health")
    assert status == 200 and health["ready"] is True

    print("[PASS] ADF-C 50-provider policy registry + free-tier/quota observatory")
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
