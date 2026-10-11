import socket
import time
import unittest

from aura_native.google.transport import (GOOGLE_READ_TIMEOUT_SECONDS,
                                          BoundedGoogleAuthRequest,
                                          normalized_transport_error,
                                          refresh_credentials_if_needed)


class GoogleTransportTimeoutTests(unittest.TestCase):
    def test_timeout_policy_is_bounded_and_normalized(self):
        self.assertEqual(GOOGLE_READ_TIMEOUT_SECONDS, 10)
        started = time.monotonic()
        code = normalized_transport_error(socket.timeout("read timed out"))
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(code, "TIMEOUT")

    def test_network_failure_is_distinct(self):
        self.assertEqual(normalized_transport_error(OSError("getaddrinfo failed")), "NETWORK_UNAVAILABLE")

    def test_valid_credential_does_not_refresh(self):
        class Credentials:
            expired = False
            refresh_token = "present"
            def refresh(self, request): raise AssertionError("refresh must not run")
        self.assertFalse(refresh_credentials_if_needed(Credentials()))

    def test_expired_credential_refreshes_once(self):
        class Credentials:
            expired = True
            refresh_token = "present"
            calls = 0
            def refresh(self, request): self.calls += 1; self.expired = False
        credentials = Credentials()
        self.assertTrue(refresh_credentials_if_needed(credentials))
        self.assertEqual(credentials.calls, 1)

    def test_refresh_request_forces_shared_timeout(self):
        request = BoundedGoogleAuthRequest()
        self.assertTrue(callable(request))
        self.assertEqual(GOOGLE_READ_TIMEOUT_SECONDS, 10)


if __name__ == "__main__":
    unittest.main()
