import unittest

from security.validators import SecurityValidationError, validate_service_url


class ValidatorTests(unittest.TestCase):
    def test_localhost_http_is_allowed(self):
        self.assertEqual(
            validate_service_url("http://localhost:11434/"),
            "http://localhost:11434",
        )

    def test_loopback_ip_is_allowed(self):
        self.assertEqual(
            validate_service_url("http://127.0.0.1:11434"),
            "http://127.0.0.1:11434",
        )

    def test_remote_endpoint_is_blocked_by_default(self):
        with self.assertRaises(SecurityValidationError):
            validate_service_url("https://8.8.8.8:11434")

    def test_remote_http_is_blocked_even_when_remote_enabled(self):
        with self.assertRaises(SecurityValidationError):
            validate_service_url("http://8.8.8.8:11434", allow_remote=True)


    def test_hostname_requiring_dns_is_not_treated_as_local(self):
        with self.assertRaises(SecurityValidationError):
            validate_service_url("http://localhost.localdomain:11434")

    def test_custom_path_is_forbidden(self):
        with self.assertRaises(SecurityValidationError):
            validate_service_url("http://localhost:11434/custom")

    def test_url_credentials_are_forbidden(self):
        with self.assertRaises(SecurityValidationError):
            validate_service_url("http://user:pass@localhost:11434")


if __name__ == "__main__":
    unittest.main()
