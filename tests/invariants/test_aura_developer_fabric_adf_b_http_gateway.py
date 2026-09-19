from __future__ import annotations

from pathlib import Path
import json
import os
import sys
import threading
import urllib.error
import urllib.request

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_fabric_http_gateway import (
    GatewayConfig,
    build_test_service,
    create_server,
)
from runtime.aura_fabric_protocols import (
    PROTOCOL_OPENAI_RESPONSES,
    normalize_request,
)

def get_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

def post_json(url: str, payload: dict, headers: dict | None = None):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.status, r.headers, r.read().decode("utf-8")

service = build_test_service(include_failure_route=True, retries_per_model=3)
config = GatewayConfig(host="127.0.0.1", port=0, retries_per_model=3)
server = create_server(service=service, config=config, host="127.0.0.1", port=0)
thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
thread.start()
host, port = server.server_address[:2]
base = f"http://{host}:{port}"

try:
    status, health = get_json(base + "/health")
    assert status == 200
    assert health["status"] == "ok"
    assert health["ready"] is True
    assert health["models_total"] == 2

    status, ready = get_json(base + "/ready")
    assert status == 200 and ready["ready"] is True

    status, models = get_json(base + "/v1/models")
    assert status == 200
    ids = {m["id"] for m in models["data"]}
    assert {"aura-echo", "aura-fail"} <= ids

    # Non-streaming OpenAI Responses-compatible request.
    status, headers, body = post_json(base + "/v1/responses", {
        "model": "aura-echo",
        "input": "hello ADF-B",
        "tools": [{"type": "function", "name": "demo"}],
        "reasoning": {"effort": "medium"},
        "stream": False,
    })
    assert status == 200
    data = json.loads(body)
    assert data["object"] == "response"
    assert data["model"] == "aura-echo"
    assert "hello ADF-B" in data["output"][0]["content"][0]["text"]
    assert data["aura_route"]["tools_preserved"] is True
    assert data["aura_route"]["reasoning_preserved"] is True

    # OpenAI Responses SSE.
    status, headers, body = post_json(base + "/v1/responses", {
        "model": "aura-echo",
        "input": "stream responses",
        "stream": True,
    })
    assert status == 200
    assert headers.get_content_type() == "text/event-stream"
    assert "event: response.created" in body
    assert "event: response.output_text.delta" in body
    assert "event: response.completed" in body

    # Chat Completions SSE + terminal [DONE].
    status, headers, body = post_json(base + "/v1/chat/completions", {
        "model": "aura-echo",
        "messages": [{"role": "user", "content": "stream chat"}],
        "stream": True,
    })
    assert status == 200
    assert "chat.completion.chunk" in body
    assert "data: [DONE]" in body

    # Anthropic Messages-compatible SSE.
    status, headers, body = post_json(
        base + "/v1/messages",
        {
            "model": "aura-echo",
            "max_tokens": 128,
            "messages": [{"role": "user", "content": "stream anthropic"}],
            "stream": True,
        },
        headers={"anthropic-version": "2023-06-01"},
    )
    assert status == 200
    assert "event: message_start" in body
    assert "event: content_block_delta" in body
    assert "event: message_stop" in body

    # Same-turn failover: 3 retries on first route, then next configured route.
    status, headers, body = post_json(base + "/v1/responses", {
        "model": "aura-resilient-test",
        "input": "survive provider outage",
        "stream": False,
    })
    assert status == 200
    data = json.loads(body)
    assert data["aura_route"]["failover_used"] is True
    assert data["aura_route"]["routed_model"] == "aura-echo/echo-v1"
    attempts = data["aura_route"]["attempts"]
    assert len([a for a in attempts if a["route"] == "aura-fail/fail-v1" and not a["ok"]]) == 3
    assert attempts[-1]["ok"] is True

    # Health is live after routing; failed model circuit is open.
    status, health2 = get_json(base + "/aura/v1/health")
    fail_health = next(m for m in health2["models"] if m["route_slug"] == "aura-fail/fail-v1")
    assert fail_health["consecutive_failures"] >= 3
    assert fail_health["circuit_open"] is True
    assert health2["failovers_total"] >= 1

    # Explicit internal adapter probe endpoint.
    status, headers, body = post_json(base + "/aura/v1/health/probe", {})
    assert status == 200
    probe = json.loads(body)
    assert len(probe["providers"]) == 2

    # Canonical schema preserves image-bearing content structurally.
    canonical = normalize_request(PROTOCOL_OPENAI_RESPONSES, {
        "model": "aura-echo",
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "inspect image"},
                {"type": "input_image", "image_url": "data:image/png;base64,AAAA"},
            ],
        }],
        "stream": False,
    })
    assert canonical.has_images is True

    # Non-loopback bind is denied by default.
    try:
        create_server(service=build_test_service(), config=GatewayConfig(), host="0.0.0.0", port=0)
    except PermissionError:
        pass
    else:
        raise AssertionError("non-loopback bind must be denied by default")

    print("[PASS] ADF-B HTTP Protocol Gateway + Streaming + Model Catalog + Live Health")
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
