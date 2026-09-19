from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_decision_trace_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

for forbidden in (
    "requests.",
    "httpx.",
    "subprocess.",
    "socket.",
    "nvidia-smi",
    "torch.cuda",
    "psutil",
    "prepare_for_llm(",
    "load_model(",
    "unload_model(",
    "generate(",
    "generate_stream(",
    "sqlite",
    "write_text(",
    "write_bytes(",
):
    assert forbidden not in text, forbidden

from runtime.aura_decision_trace_v3 import DecisionTraceV3

trace = DecisionTraceV3(
    correlation_id="turn-123",
    task_type="chat",
    mode="automatic",
    privacy="default",
    voice_output=True,
    metadata={
        "conversation_id": "abc",
        "api_key": "should-not-survive",
        "prompt": "raw prompt should be redacted",
    },
)

first = trace.add_event(
    stage="eligibility",
    outcome="filtered",
    selected_provider="groq",
    selected_model="m1",
    reason_codes=["EXISTING_ROUTE_PRESERVED"],
    rejected=[
        {
            "provider": "gemini",
            "reason_codes": ["PROVIDER_UNAVAILABLE"],
            "secret": "hide-me",
        }
    ],
    latency_ms=3.2,
    metadata={"user_text": "do not retain this", "candidate_count": 3},
)
assert first.index == 0
assert first.stage == "eligibility"
assert first.latency_ms == 3.2
assert first.metadata["user_text"] == "<redacted>"
assert first.rejected[0]["secret"] == "<redacted>"

second = trace.add_event(
    stage="model_policy",
    outcome="selected",
    selected_provider="groq",
    selected_model="m1",
    reason_codes=["EXISTING_ROUTE_PRESERVED"],
)
assert second.index == 1

snap_running = trace.snapshot()
assert snap_running.status == "running"
assert len(snap_running.events) == 2
assert snap_running.request_facts["metadata"]["api_key"] == "<redacted>"
assert snap_running.request_facts["metadata"]["prompt"] == "<redacted>"

done = trace.complete(
    status="completed",
    selected_provider="groq",
    selected_model="m1",
    finish_reason="stop",
    fallback_count=1,
    error_chain=[{"provider": "gemini", "error": "timeout", "authorization": "hide"}],
)
assert done.status == "completed"
assert done.summary["fallback_count"] == 1
assert done.summary["error_chain"][0]["authorization"] == "<redacted>"

try:
    trace.add_event(stage="gateway", outcome="late")
    raise AssertionError("append after completion must fail")
except RuntimeError:
    pass

try:
    DecisionTraceV3().add_event(stage="unknown", outcome="x")
    raise AssertionError("unknown stage must fail")
except ValueError:
    pass

# Trace must not expose raw user prompt fields as a constructor argument.
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DecisionTraceV3")
init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
arg_names = [a.arg for a in init.args.args + init.args.kwonlyargs]
assert "user_text" not in arg_names
assert "prompt" not in arg_names
assert "messages" not in arg_names

print("PASS AURA v3 DecisionTraceV3 invariant")
