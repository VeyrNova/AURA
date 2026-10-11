from __future__ import annotations

import threading
import unittest
from urllib.error import HTTPError

from aura_native.agent.provider import GeminiRuntimeProvider, ProviderFailure


class Response:
    def __init__(self, lines): self.lines = tuple(lines)
    def __iter__(self): return iter(self.lines)
    def __enter__(self): return self
    def __exit__(self, *_): return False


def ok(text="ok"):
    return Response((f'data: {{"candidates":[{{"content":{{"parts":[{{"text":"{text}"}}]}}}}]}}\n'.encode(),))


def http(code, headers=None):
    return HTTPError("https://generativelanguage.googleapis.com/", code, "failure", headers or {}, None)


class GeminiRetryTests(unittest.TestCase):
    messages = ({"role": "user", "content": "safe"},)

    def test_503_then_success_and_bounded_sequence(self):
        calls = []
        def open_(*_a, **_k):
            calls.append(1)
            if len(calls) == 1: raise http(503)
            return ok("answer")
        p = GeminiRuntimeProvider(model="gemini-3.8-flash", api_key="secret", opener=open_, base_delay=0, jitter=0)
        self.assertEqual("answer", "".join(c.text for c in p.generate_stream(self.messages) if c.text))
        self.assertEqual(2, len(calls))

    def test_persistent_503_stops_at_max_attempts(self):
        calls = []
        def fail(*_a, **_k): calls.append(1); raise http(503)
        p = GeminiRuntimeProvider(model="gemini-3.8-flash", api_key="secret", opener=fail, base_delay=0)
        with self.assertRaises(ProviderFailure) as caught: list(p.generate_stream(self.messages))
        self.assertEqual((caught.exception.code, caught.exception.http_status), ("provider_unavailable", 503))
        self.assertEqual(3, len(calls))

    def test_cancelled_backoff_does_not_issue_second_request(self):
        event = threading.Event(); calls = []
        def fail(*_a, **_k): calls.append(1); raise http(503)
        p = GeminiRuntimeProvider(model="gemini-3.8-flash", api_key="secret", opener=fail, base_delay=.2, jitter=0)
        threading.Timer(.02, event.set).start()
        self.assertEqual([], list(p.generate_stream(self.messages, cancel_event=event)))
        self.assertEqual(1, len(calls))

    def test_first_delta_then_transport_failure_is_not_retried(self):
        calls = []
        class Broken(Response):
            def __iter__(self):
                yield b'data: {"candidates":[{"content":{"parts":[{"text":"first"}]}}]}\n'
                raise ConnectionResetError("reset")
        def open_(*_a, **_k): calls.append(1); return Broken(())
        p = GeminiRuntimeProvider(model="gemini-3.8-flash", api_key="secret", opener=open_, base_delay=0)
        with self.assertRaises(ProviderFailure) as caught: list(p.generate_stream(self.messages))
        self.assertEqual("network_error", caught.exception.code)
        self.assertEqual(1, len(calls))

    def test_non_retryable_statuses_are_single_attempt(self):
        for status in (400, 401, 403, 404):
            calls = []
            def fail(*_a, _status=status, **_k): calls.append(1); raise http(_status)
            p = GeminiRuntimeProvider(model="gemini-3.8-flash", api_key="secret", opener=fail, base_delay=0)
            with self.subTest(status=status), self.assertRaises(ProviderFailure): list(p.generate_stream(self.messages))
            self.assertEqual(1, len(calls))

    def test_retry_after_is_capped_and_rate_limit_retries(self):
        calls = []
        def open_(*_a, **_k):
            calls.append(1)
            if len(calls) == 1: raise http(429, {"Retry-After": "9999"})
            return ok()
        p = GeminiRuntimeProvider(model="gemini-3.8-flash", api_key="secret", opener=open_, max_delay=0, jitter=0)
        self.assertTrue(list(p.generate_stream(self.messages)))
        self.assertEqual(2, len(calls))


if __name__ == "__main__": unittest.main()
