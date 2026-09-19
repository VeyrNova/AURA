from __future__ import annotations

import json
import unittest

from ai.llm_manager import GeminiProvider


class _Response:
    def __init__(self, *, lines=None, data=None, status=200):
        self._lines = list(lines or [])
        self._data = data
        self.status_code = status
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)

    def json(self):
        return self._data


class _RecoverySession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if ":streamGenerateContent" in url:
            first = {
                "candidates": [{
                    "content": {"parts": [{"text": "Réponse tronquée."}]},
                    "finishReason": "MAX_TOKENS",
                }],
                "usageMetadata": {
                    "promptTokenCount": 7787,
                    "candidatesTokenCount": 5,
                    "thoughtsTokenCount": 515,
                },
            }
            return _Response(lines=["data: " + json.dumps(first)])
        recovered = {
            "candidates": [{
                "content": {"parts": [{"text": "Analyse complète récupérée après le garde-fou MAX_TOKENS."}]},
                "finishReason": "STOP",
            }],
            "usageMetadata": {
                "promptTokenCount": 7787,
                "candidatesTokenCount": 14,
                "thoughtsTokenCount": 20,
            },
        }
        return _Response(data=recovered)

    def delete(self, *_args, **_kwargs):
        return _Response(data={})


class Patch2685GeminiResponseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.provider = GeminiProvider(
            "https://generativelanguage.googleapis.com/v1beta",
            "https://generativelanguage.googleapis.com/upload/v1beta",
            "test-key",
        )

    def test_gemini3_document_payload_uses_low_thinking_and_large_visible_budget(self):
        payload = self.provider._payload(
            [{"role": "user", "content": "Analyse ce document"}],
            model="gemini-3.6-flash",
            num_predict=4096,
            temperature=0.34,
            top_p=0.88,
            thinking_level="low",
        )
        config = payload["generationConfig"]
        self.assertEqual(config["maxOutputTokens"], 4096)
        self.assertEqual(config["thinkingConfig"], {"thinkingLevel": "low"})
        self.assertNotIn("temperature", config)
        self.assertNotIn("topP", config)

    def test_non_gemini3_keeps_sampling_compatibility(self):
        payload = self.provider._payload(
            [{"role": "user", "content": "Bonjour"}],
            model="gemini-2.5-flash",
            num_predict=512,
            temperature=0.4,
            top_p=0.85,
            thinking_level=None,
        )
        config = payload["generationConfig"]
        self.assertEqual(config["maxOutputTokens"], 512)
        self.assertAlmostEqual(config["temperature"], 0.4)
        self.assertAlmostEqual(config["topP"], 0.85)
        self.assertNotIn("thinkingConfig", config)

    def test_tiny_max_tokens_fragment_is_recovered_before_ui_receives_it(self):
        session = _RecoverySession()
        self.provider.session = session
        chunks = list(self.provider.generate_stream(
            [{"role": "user", "content": "Analyse ce document"}],
            model="gemini-3.6-flash",
            num_predict=4096,
            temperature=0.34,
            top_p=0.88,
            thinking_level="low",
        ))
        answer = "".join(chunks)
        self.assertIn("Analyse complète", answer)
        self.assertNotIn("Réponse tronquée", answer)
        self.assertEqual(self.provider.last_metrics.done_reason, "STOP")
        self.assertEqual(len(session.calls), 2)
        retry_config = session.calls[1][1]["json"]["generationConfig"]
        self.assertGreaterEqual(retry_config["maxOutputTokens"], 4096)
        self.assertEqual(retry_config["thinkingConfig"]["thinkingLevel"], "minimal")


if __name__ == "__main__":
    unittest.main()
