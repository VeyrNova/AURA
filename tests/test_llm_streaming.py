import json
import unittest
from unittest.mock import patch

from ai.llm_manager import OllamaProvider


class FakeResponse:
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=True):
        del decode_unicode
        rows = [
            {"message": {"content": "Bon"}, "done": False},
            {"message": {"content": "soir"}, "done": False},
            {"message": {"content": ""}, "done": True},
        ]
        for row in rows:
            yield json.dumps(row)


class LLMStreamingTests(unittest.TestCase):
    def test_streaming_yields_partial_content(self):
        provider = OllamaProvider("http://localhost:11434", "test-model")
        with patch.object(provider.session, "post", return_value=FakeResponse()):
            chunks = list(provider.generate_stream([{"role": "user", "content": "hello"}]))
        self.assertEqual(chunks, ["Bon", "soir"])


if __name__ == "__main__":
    unittest.main()
