"""Regression tests for the native Ollama NDJSON boundary (no network)."""
import json
import unittest

from aura_native.agent.provider import OllamaProvider
from aura_native.config.agent_provider import AgentProviderSettings


class _Response:
    def __init__(self, lines): self._lines = lines
    def __enter__(self): return self
    def __exit__(self, *unused): return False
    def __iter__(self): return iter(self._lines)


class OllamaStreamNdjsonTests(unittest.TestCase):
    def test_terminal_empty_or_whitespace_ndjson_record_finishes_stream(self):
        captured = []
        def opener(req, timeout):
            captured.append((json.loads(req.data.decode("utf-8")), timeout))
            return _Response((
                b'{"model":"fake-model","message":{"role":"assistant","content":"Bon"},"done":false}\n',
                b'{"model":"fake-model","message":{"content":"jour"},"done":false}\n',
                b'{"model":"fake-model","message":{"content":"   "},"done":true,"done_reason":"stop"}\n',
            ))

        settings = AgentProviderSettings("ollama", "fake-model", "http://unused.invalid", 3.0)
        chunks = list(OllamaProvider(settings, opener=opener).generate_stream(({"role":"user","content":"Bonjour"},)))

        self.assertEqual([chunk.text for chunk in chunks], ["Bon", "jour", "   "])
        self.assertFalse(chunks[0].done)
        self.assertTrue(chunks[-1].done)
        self.assertEqual(chunks[-1].finish_reason, "stop")
        self.assertEqual(captured[0][0], {"model":"fake-model", "messages":[{"role":"user","content":"Bonjour"}], "stream":True, "think":False})
