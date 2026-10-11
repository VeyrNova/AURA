from __future__ import annotations

import json
import socket
import unittest
from urllib.error import HTTPError, URLError

from aura_native.agent.provider import GeminiRuntimeProvider, ProviderFailure


KEY = "PCC4B_GEMINI_KEY_SENTINEL"


class Response:
    def __init__(self, chunks):
        self.chunks = tuple(chunks)

    def __iter__(self):
        return iter(self.chunks)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def sse(text="ok"):
    return (f'data: {{"candidates":[{{"content":{{"parts":[{{"text":"{text}"}}]}}}}]}}\n').encode()


class GeminiStreamDiagnosticsTests(unittest.TestCase):
    def provider(self, opener):
        return GeminiRuntimeProvider(model="gemini-3.8-flash", api_key=KEY, opener=opener)

    def test_mixed_provider_history_is_valid_gemini_payload(self):
        messages = (
            {"role": "system", "content": "AURA system"},
            {"role": "user", "content": "Ollama user"},
            {"role": "assistant", "content": "Ollama answer"},
            {"role": "user", "content": "Gemini user"},
            {"role": "assistant", "content": "Gemini answer"},
            {"role": "user", "content": "Ollama user"},
            {"role": "assistant", "content": "Ollama answer"},
            {"role": "user", "content": "cancelled user without answer"},
            {"role": "user", "content": "new user"},
            {"role": "tool", "content": '{"internal": true}'},
        )
        payload = GeminiRuntimeProvider._payload(messages)
        self.assertEqual([item["role"] for item in payload["contents"]], ["user", "model", "user", "model", "user", "model", "user"])
        self.assertEqual(payload["contents"][-1]["parts"][0]["text"], "cancelled user without answer\n\nnew user")
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "AURA system")
        self.assertNotIn("internal", json.dumps(payload))
        json.dumps(payload)

    def test_sse_accepts_keepalive_multiple_events_and_split_first_event(self):
        first = b'data: {"candidates":[{"content":{"parts":[{"text":"A"}]}}]}\n'
        second = b'data: {"candidates":[{"content":{"parts":[{"text":"B"}]},"finishReason":"STOP"}]}\n'
        split = first[:25], first[25:]
        provider = self.provider(lambda *_args, **_kwargs: Response((b": keepalive\n", *split, second)))
        chunks = list(provider.generate_stream(({"role": "user", "content": "safe"},)))
        self.assertEqual([item.text for item in chunks], ["A", "B", ""])
        self.assertTrue(chunks[-1].done)

    def test_malformed_sse_after_http_200_is_invalid_response(self):
        provider = self.provider(lambda *_args, **_kwargs: Response((b"data: {not-json}\n",)))
        with self.assertRaises(ProviderFailure) as caught:
            list(provider.generate_stream(({"role": "user", "content": "safe"},)))
        self.assertEqual((caught.exception.code, caught.exception.stage), ("invalid_response", "sse"))

    def test_http_statuses_are_specific(self):
        expected = {
            400: "invalid_response", 401: "authentication_failed", 403: "permission_denied",
            404: "model_not_found", 408: "timeout", 429: "rate_limited",
            500: "provider_unavailable", 502: "provider_unavailable",
            503: "provider_unavailable", 504: "provider_unavailable",
        }
        for status, code in expected.items():
            with self.subTest(status=status):
                def fail(*_args, _status=status, **_kwargs):
                    raise HTTPError("https://generativelanguage.googleapis.com/", _status, "failure", {}, None)
                with self.assertRaises(ProviderFailure) as caught:
                    list(self.provider(fail).generate_stream(({"role": "user", "content": "safe"},)))
                self.assertEqual((caught.exception.code, caught.exception.http_status, caught.exception.stage), (code, status, "http_response"))

    def test_timeout_connection_reset_and_dns_are_transport_specific(self):
        for exception, expected in (
            (TimeoutError("slow"), ("timeout", "connect")),
            (socket.timeout("slow"), ("timeout", "connect")),
            (URLError("dns"), ("network_error", "connect")),
            (ConnectionResetError("reset"), ("network_error", "transport")),
        ):
            with self.subTest(exception=type(exception).__name__):
                def fail(*_args, _exception=exception, **_kwargs):
                    raise _exception
                with self.assertRaises(ProviderFailure) as caught:
                    list(self.provider(fail).generate_stream(({"role": "user", "content": "safe"},)))
                self.assertEqual((caught.exception.code, caught.exception.stage), expected)

    def test_delayed_first_token_is_not_an_empty_response_failure(self):
        provider = self.provider(lambda *_args, **_kwargs: Response((b": thinking\n", b"\n", sse("after-think"))))
        chunks = list(provider.generate_stream(({"role": "user", "content": "safe"},)))
        self.assertEqual(chunks[0].text, "after-think")
        self.assertTrue(chunks[-1].done)


if __name__ == "__main__":
    unittest.main()
