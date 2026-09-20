from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import json
import time
import uuid

PROTOCOL_ANTHROPIC = "anthropic_messages"
PROTOCOL_OPENAI_RESPONSES = "openai_responses"
PROTOCOL_OPENAI_CHAT = "openai_chat"
PROTOCOL_AURA_NATIVE = "aura_native"

SUPPORTED_PROTOCOLS = (
    PROTOCOL_ANTHROPIC,
    PROTOCOL_OPENAI_RESPONSES,
    PROTOCOL_OPENAI_CHAT,
    PROTOCOL_AURA_NATIVE,
)

@dataclass(frozen=True)
class CanonicalMessage:
    role: str
    content: Any
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[dict[str, Any], ...] = ()

@dataclass(frozen=True)
class CanonicalRequest:
    request_id: str
    protocol: str
    model: str
    messages: tuple[CanonicalMessage, ...]
    system: Any = None
    tools: tuple[dict[str, Any], ...] = ()
    tool_choice: Any = None
    stream: bool = False
    max_output_tokens: int | None = None
    temperature: float | None = None
    reasoning: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_images(self) -> bool:
        def scan(value: Any) -> bool:
            if isinstance(value, dict):
                t = str(value.get("type", "")).lower()
                if "image" in t:
                    return True
                return any(scan(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return any(scan(v) for v in value)
            return False
        return scan([m.content for m in self.messages])

    @property
    def prompt_text(self) -> str:
        parts: list[str] = []
        if isinstance(self.system, str) and self.system.strip():
            parts.append(self.system.strip())
        for msg in self.messages:
            text = extract_text(msg.content)
            if text:
                parts.append(text)
        return "\n".join(parts)

@dataclass(frozen=True)
class CanonicalResponse:
    response_id: str
    request_id: str
    requested_model: str
    routed_model: str
    provider_id: str
    text: str
    finish_reason: str = "stop"
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))

def new_id(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex[:24]

def extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        for key in ("text", "input_text", "output_text"):
            value = content.get(key)
            if isinstance(value, str):
                return value
        return ""
    if isinstance(content, (list, tuple)):
        values = [extract_text(item) for item in content]
        return "\n".join(v for v in values if v)
    return str(content)


def _json_arguments(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "{}"
        try:
            parsed = json.loads(raw)
        except Exception:
            return raw
        return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        value = {}
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"


def _canonical_inbound_tool_call(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    function = raw.get("function") if isinstance(raw.get("function"), dict) else {}
    name = str(raw.get("name") or function.get("name") or "").strip()
    if not name:
        return None
    call_id = str(
        raw.get("call_id")
        or raw.get("id")
        or raw.get("tool_use_id")
        or new_id("call")
    ).strip()
    arguments = raw.get("arguments")
    if arguments is None:
        arguments = raw.get("input")
    if arguments is None:
        arguments = function.get("arguments")
    return {
        "id": call_id,
        "name": name,
        "arguments": _json_arguments(arguments),
    }


def _canonical_tool_definition(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    function = raw.get("function") if isinstance(raw.get("function"), dict) else None
    if function is not None:
        name = str(function.get("name") or "").strip()
        if not name:
            return None
        parameters = function.get("parameters")
        if not isinstance(parameters, dict):
            parameters = {}
        return {
            "type": "function",
            "name": name,
            "description": str(function.get("description") or ""),
            "parameters": dict(parameters),
        }

    raw_type = str(raw.get("type") or "function").strip().casefold()
    if raw_type == "function" and raw.get("name"):
        parameters = raw.get("parameters")
        if not isinstance(parameters, dict):
            parameters = raw.get("input_schema")
        if not isinstance(parameters, dict):
            parameters = {}
        return {
            "type": "function",
            "name": str(raw.get("name") or "").strip(),
            "description": str(raw.get("description") or ""),
            "parameters": dict(parameters),
        }

    if raw.get("name") and isinstance(raw.get("input_schema"), dict):
        return {
            "type": "function",
            "name": str(raw.get("name") or "").strip(),
            "description": str(raw.get("description") or ""),
            "parameters": dict(raw.get("input_schema") or {}),
        }
    return None


def _canonical_tool_choice(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        folded = value.strip().casefold()
        if folded in {"auto", "none", "required"}:
            return folded
        return value
    if not isinstance(value, dict):
        return value

    function = value.get("function") if isinstance(value.get("function"), dict) else None
    if function and function.get("name"):
        return {"type": "function", "name": str(function["name"])}

    kind = str(value.get("type") or "").strip().casefold()
    name = str(value.get("name") or "").strip()
    if kind == "any":
        return "required"
    if kind in {"auto", "none"}:
        return kind
    if kind in {"tool", "function"} and name:
        return {"type": "function", "name": name}
    return dict(value)


def _canonical_tools(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    out = []
    for raw in value:
        item = _canonical_tool_definition(raw)
        if item is not None:
            out.append(item)
    return tuple(out)


def _messages_from_openai_chat(value: Any) -> list[CanonicalMessage]:
    if not isinstance(value, list):
        return []
    out: list[CanonicalMessage] = []
    for item in value:
        if not isinstance(item, dict):
            out.append(CanonicalMessage("user", item))
            continue
        role = str(item.get("role") or "user")
        content = item.get("content", "")
        calls_raw = item.get("tool_calls") or []
        calls = tuple(
            x for x in (_canonical_inbound_tool_call(raw) for raw in calls_raw)
            if x is not None
        ) if isinstance(calls_raw, list) else ()
        out.append(CanonicalMessage(
            role=role,
            content=content,
            name=item.get("name"),
            tool_call_id=item.get("tool_call_id"),
            tool_calls=calls,
        ))
    return out


def _messages_from_openai_responses(value: Any) -> list[CanonicalMessage]:
    if isinstance(value, str):
        return [CanonicalMessage("user", value)]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []

    out: list[CanonicalMessage] = []
    for item in value:
        if not isinstance(item, dict):
            out.append(CanonicalMessage("user", item))
            continue

        item_type = str(item.get("type") or "").strip().casefold()
        if item_type == "function_call":
            call = _canonical_inbound_tool_call(item)
            if call is not None:
                out.append(CanonicalMessage("assistant", "", tool_calls=(call,)))
            continue

        if item_type == "function_call_output":
            out.append(CanonicalMessage(
                "tool",
                item.get("output", ""),
                tool_call_id=str(item.get("call_id") or ""),
            ))
            continue

        role = str(item.get("role") or "user")
        content = item.get("content", item.get("input", ""))
        out.append(CanonicalMessage(
            role=role,
            content=content,
            name=item.get("name"),
            tool_call_id=item.get("tool_call_id"),
        ))
    return out


def _messages_from_anthropic(value: Any) -> list[CanonicalMessage]:
    if not isinstance(value, list):
        return []
    out: list[CanonicalMessage] = []
    for message in value:
        if not isinstance(message, dict):
            out.append(CanonicalMessage("user", message))
            continue

        role = str(message.get("role") or "user")
        content = message.get("content", "")
        if not isinstance(content, list):
            out.append(CanonicalMessage(role, content))
            continue

        text_blocks: list[Any] = []
        tool_calls: list[dict[str, Any]] = []
        pending_tool_results: list[CanonicalMessage] = []

        for block in content:
            if not isinstance(block, dict):
                text_blocks.append(block)
                continue
            kind = str(block.get("type") or "").strip().casefold()

            if kind == "text":
                text_blocks.append({"type": "text", "text": block.get("text", "")})
                continue

            if kind == "tool_use":
                call = _canonical_inbound_tool_call({
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "arguments": block.get("input"),
                })
                if call is not None:
                    tool_calls.append(call)
                continue

            if kind == "tool_result":
                pending_tool_results.append(CanonicalMessage(
                    "tool",
                    block.get("content", ""),
                    tool_call_id=str(block.get("tool_use_id") or ""),
                ))
                continue

            text_blocks.append(block)

        if text_blocks or tool_calls:
            out.append(CanonicalMessage(
                role,
                text_blocks,
                tool_calls=tuple(tool_calls),
            ))
        out.extend(pending_tool_results)
    return out


def _messages_from_openai_input(value: Any) -> list[CanonicalMessage]:
    if isinstance(value, str):
        return [CanonicalMessage("user", value)]
    if isinstance(value, dict):
        value = [value]
    return _messages_from_openai_chat(value)



def normalize_request(protocol: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> CanonicalRequest:
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError(f"Unsupported protocol: {protocol}")
    if not isinstance(payload, dict):
        raise TypeError("Request payload must be a JSON object")
    headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    model = str(payload.get("model") or "").strip()
    if not model:
        raise ValueError("model is required")

    request_id = headers.get("x-request-id") or new_id("req")
    stream = bool(payload.get("stream", False))

    if protocol == PROTOCOL_OPENAI_RESPONSES:
        messages = _messages_from_openai_responses(payload.get("input", ""))
        system = payload.get("instructions")
        max_tokens = payload.get("max_output_tokens")
        reasoning = payload.get("reasoning")
    elif protocol == PROTOCOL_OPENAI_CHAT:
        messages = _messages_from_openai_chat(payload.get("messages", []))
        system_msgs = [m.content for m in messages if m.role in ("system", "developer")]
        system = system_msgs if system_msgs else None
        max_tokens = payload.get("max_completion_tokens", payload.get("max_tokens"))
        reasoning = payload.get("reasoning_effort", payload.get("reasoning"))
    elif protocol == PROTOCOL_ANTHROPIC:
        messages = _messages_from_anthropic(payload.get("messages", []))
        system = payload.get("system")
        max_tokens = payload.get("max_tokens")
        reasoning = payload.get("thinking", payload.get("effort"))
    else:
        messages = _messages_from_openai_chat(payload.get("messages", payload.get("input", [])))
        system = payload.get("system", payload.get("instructions"))
        max_tokens = payload.get("max_output_tokens", payload.get("max_tokens"))
        reasoning = payload.get("reasoning", payload.get("thinking"))

    tools = _canonical_tools(payload.get("tools") or [])
    tool_choice = _canonical_tool_choice(payload.get("tool_choice"))

    return CanonicalRequest(
        request_id=request_id,
        protocol=protocol,
        model=model,
        messages=tuple(messages),
        system=system,
        tools=tools,
        tool_choice=tool_choice,
        stream=stream,
        max_output_tokens=int(max_tokens) if isinstance(max_tokens, (int, float)) and max_tokens > 0 else None,
        temperature=float(payload["temperature"]) if isinstance(payload.get("temperature"), (int, float)) else None,
        reasoning=reasoning,
        metadata=dict(payload.get("metadata") or {}) if isinstance(payload.get("metadata"), dict) else {},
        raw=dict(payload),
    )


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _tool_arguments_json(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "{}"
        try:
            parsed = json.loads(raw)
        except Exception:
            return raw
        return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        value = {}
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"


def _tool_arguments_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    raw = _tool_arguments_json(value)
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _canonical_tool_calls(value: Any) -> tuple[dict[str, str], ...]:
    calls: list[dict[str, str]] = []
    for raw in tuple(value or ()):
        if not isinstance(raw, dict):
            continue
        function = raw.get("function") if isinstance(raw.get("function"), dict) else {}
        name = str(raw.get("name") or function.get("name") or "").strip()
        if not name:
            continue
        call_id = str(raw.get("call_id") or raw.get("id") or new_id("call")).strip()
        arguments = raw.get("arguments", function.get("arguments"))
        args_json = _tool_arguments_json(arguments)
        item_id = str(raw.get("item_id") or raw.get("response_item_id") or "").strip()
        if not item_id:
            suffix = call_id[5:] if call_id.startswith("call_") else call_id
            safe = "".join(ch for ch in suffix if ch.isalnum() or ch in "_-")[:40]
            item_id = "fc_" + (safe or new_id("item")[5:])
        calls.append({
            "call_id": call_id,
            "item_id": item_id,
            "name": name,
            "arguments": args_json,
        })
    return tuple(calls)


def _openai_response_tool_item(call: dict[str, str], *, arguments: str | None = None) -> dict[str, Any]:
    return {
        "id": call["item_id"],
        "call_id": call["call_id"],
        "type": "function_call",
        "status": "completed",
        "name": call["name"],
        "arguments": call["arguments"] if arguments is None else arguments,
    }


def _openai_chat_tool_call(call: dict[str, str]) -> dict[str, Any]:
    return {
        "id": call["call_id"],
        "type": "function",
        "function": {
            "name": call["name"],
            "arguments": call["arguments"],
        },
    }


def _anthropic_tool_use(call: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "tool_use",
        "id": call["call_id"],
        "name": call["name"],
        "input": _tool_arguments_object(call["arguments"]),
    }


def render_response(protocol: str, response: CanonicalResponse) -> dict[str, Any]:
    usage = {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "total_tokens": response.input_tokens + response.output_tokens,
    }
    calls = _canonical_tool_calls(response.tool_calls)

    if protocol == PROTOCOL_OPENAI_RESPONSES:
        output: list[dict[str, Any]] = []
        if response.text:
            output.append({
                "id": new_id("msg"),
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": response.text, "annotations": []}],
            })
        output.extend(_openai_response_tool_item(call) for call in calls)
        return {
            "id": response.response_id,
            "object": "response",
            "created_at": response.created_at,
            "status": "completed",
            "model": response.requested_model,
            "output": output,
            "usage": {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": usage["total_tokens"],
            },
            "aura_route": {
                "provider": response.provider_id,
                "routed_model": response.routed_model,
                **response.metadata,
            },
        }

    if protocol == PROTOCOL_OPENAI_CHAT:
        message: dict[str, Any] = {
            "role": "assistant",
            "content": response.text if response.text else None,
        }
        if calls:
            message["tool_calls"] = [_openai_chat_tool_call(call) for call in calls]
        return {
            "id": response.response_id.replace("resp_", "chatcmpl_"),
            "object": "chat.completion",
            "created": response.created_at,
            "model": response.requested_model,
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if calls else response.finish_reason,
            }],
            "usage": {
                "prompt_tokens": response.input_tokens,
                "completion_tokens": response.output_tokens,
                "total_tokens": usage["total_tokens"],
            },
            "aura_route": {
                "provider": response.provider_id,
                "routed_model": response.routed_model,
                **response.metadata,
            },
        }

    if protocol == PROTOCOL_ANTHROPIC:
        content: list[dict[str, Any]] = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        content.extend(_anthropic_tool_use(call) for call in calls)
        return {
            "id": response.response_id.replace("resp_", "msg_"),
            "type": "message",
            "role": "assistant",
            "model": response.requested_model,
            "content": content,
            "stop_reason": "tool_use" if calls else (
                "end_turn" if response.finish_reason == "stop" else response.finish_reason
            ),
            "stop_sequence": None,
            "usage": {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            },
            "aura_route": {
                "provider": response.provider_id,
                "routed_model": response.routed_model,
                **response.metadata,
            },
        }

    return {
        "schema": "aura.fabric.response.v1",
        "id": response.response_id,
        "request_id": response.request_id,
        "model": response.requested_model,
        "provider": response.provider_id,
        "routed_model": response.routed_model,
        "text": response.text,
        "tool_calls": [dict(call) for call in calls],
        "finish_reason": "tool_calls" if calls else response.finish_reason,
        "usage": usage,
        "metadata": response.metadata,
    }


def _chunks(text: str, size: int = 24) -> Iterable[str]:
    if not text:
        yield ""
        return
    for i in range(0, len(text), size):
        yield text[i:i + size]

def _sse(event: str | None, data: Any) -> bytes:
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    encoded = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for line in str(encoded).splitlines() or [""]:
        lines.append("data: " + line)
    return ("\n".join(lines) + "\n\n").encode("utf-8")


def stream_events(protocol: str, response: CanonicalResponse) -> Iterable[bytes]:
    calls = _canonical_tool_calls(response.tool_calls)

    if protocol == PROTOCOL_OPENAI_RESPONSES:
        shell = {
            "id": response.response_id,
            "object": "response",
            "created_at": response.created_at,
            "status": "in_progress",
            "model": response.requested_model,
            "output": [],
        }
        yield _sse("response.created", {"type": "response.created", "response": shell})
        seq = 1
        output_index = 0

        if response.text:
            item_id = new_id("msg")
            for delta in _chunks(response.text):
                yield _sse("response.output_text.delta", {
                    "type": "response.output_text.delta",
                    "sequence_number": seq,
                    "item_id": item_id,
                    "output_index": output_index,
                    "content_index": 0,
                    "delta": delta,
                })
                seq += 1
            output_index += 1

        for call in calls:
            initial = _openai_response_tool_item(call, arguments="")
            yield _sse("response.output_item.added", {
                "type": "response.output_item.added",
                "sequence_number": seq,
                "response_id": response.response_id,
                "output_index": output_index,
                "item": initial,
            })
            seq += 1
            for delta in _chunks(call["arguments"]):
                yield _sse("response.function_call_arguments.delta", {
                    "type": "response.function_call_arguments.delta",
                    "sequence_number": seq,
                    "response_id": response.response_id,
                    "item_id": call["item_id"],
                    "output_index": output_index,
                    "delta": delta,
                })
                seq += 1
            yield _sse("response.function_call_arguments.done", {
                "type": "response.function_call_arguments.done",
                "sequence_number": seq,
                "response_id": response.response_id,
                "item_id": call["item_id"],
                "output_index": output_index,
                "arguments": call["arguments"],
            })
            seq += 1
            yield _sse("response.output_item.done", {
                "type": "response.output_item.done",
                "sequence_number": seq,
                "response_id": response.response_id,
                "output_index": output_index,
                "item": _openai_response_tool_item(call),
            })
            seq += 1
            output_index += 1

        final = render_response(protocol, response)
        yield _sse("response.completed", {
            "type": "response.completed",
            "sequence_number": seq,
            "response": final,
        })
        return

    if protocol == PROTOCOL_OPENAI_CHAT:
        chat_id = response.response_id.replace("resp_", "chatcmpl_")
        first = True
        for delta in _chunks(response.text):
            role = "assistant" if first else None
            chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": response.created_at,
                "model": response.requested_model,
                "choices": [{
                    "index": 0,
                    "delta": {**({"role": role} if role else {}), "content": delta},
                    "finish_reason": None,
                }],
            }
            yield _sse(None, chunk)
            first = False

        if calls:
            yield _sse(None, {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": response.created_at,
                "model": response.requested_model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        **({"role": "assistant"} if first else {}),
                        "tool_calls": [
                            {"index": i, **_openai_chat_tool_call(call)}
                            for i, call in enumerate(calls)
                        ],
                    },
                    "finish_reason": None,
                }],
            })

        yield _sse(None, {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": response.created_at,
            "model": response.requested_model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "tool_calls" if calls else response.finish_reason,
            }],
        })
        yield _sse(None, "[DONE]")
        return

    if protocol == PROTOCOL_ANTHROPIC:
        msg_id = response.response_id.replace("resp_", "msg_")
        yield _sse("message_start", {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": response.requested_model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": response.input_tokens, "output_tokens": 0},
            },
        })

        index = 0
        if response.text:
            yield _sse("content_block_start", {
                "type": "content_block_start",
                "index": index,
                "content_block": {"type": "text", "text": ""},
            })
            for delta in _chunks(response.text):
                yield _sse("content_block_delta", {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": "text_delta", "text": delta},
                })
            yield _sse("content_block_stop", {
                "type": "content_block_stop",
                "index": index,
            })
            index += 1

        for call in calls:
            yield _sse("content_block_start", {
                "type": "content_block_start",
                "index": index,
                "content_block": {
                    "type": "tool_use",
                    "id": call["call_id"],
                    "name": call["name"],
                    "input": {},
                },
            })
            for delta in _chunks(call["arguments"]):
                yield _sse("content_block_delta", {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": delta,
                    },
                })
            yield _sse("content_block_stop", {
                "type": "content_block_stop",
                "index": index,
            })
            index += 1

        yield _sse("message_delta", {
            "type": "message_delta",
            "delta": {
                "stop_reason": "tool_use" if calls else (
                    "end_turn" if response.finish_reason == "stop" else response.finish_reason
                ),
                "stop_sequence": None,
            },
            "usage": {"output_tokens": response.output_tokens},
        })
        yield _sse("message_stop", {"type": "message_stop"})
        return

    yield _sse("aura.response.start", {
        "type": "aura.response.start",
        "id": response.response_id,
        "model": response.requested_model,
    })
    for delta in _chunks(response.text):
        yield _sse("aura.response.delta", {
            "type": "aura.response.delta",
            "delta": delta,
        })
    if calls:
        yield _sse("aura.tool_calls", {
            "type": "aura.tool_calls",
            "tool_calls": [dict(call) for call in calls],
        })
    yield _sse("aura.response.completed", {
        "type": "aura.response.completed",
        "response": render_response(protocol, response),
    })

