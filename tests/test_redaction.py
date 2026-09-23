import unittest

from security.redaction import redact_sensitive_data


class RedactionTests(unittest.TestCase):
    def test_common_secret_patterns_are_redacted(self):
        value = "token=abc123 password=hunter2 Authorization: Bearer qwerty"
        redacted = redact_sensitive_data(value)
        self.assertNotIn("abc123", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("qwerty", redacted)
        self.assertGreaterEqual(redacted.count("<REDACTED>"), 3)


if __name__ == "__main__":
    unittest.main()
