"""Bounded Google READ transport shared by Calendar, Gmail and Tasks."""
from __future__ import annotations
from threading import Lock

GOOGLE_READ_TIMEOUT_SECONDS = 10
_refresh_lock = Lock()


class BoundedGoogleAuthRequest:
    """google-auth request adapter that forces the shared timeout."""
    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        import requests
        response = requests.request(
            method=method,
            url=url,
            data=body,
            headers=headers,
            timeout=GOOGLE_READ_TIMEOUT_SECONDS,
            **{key: value for key, value in kwargs.items() if key in ("cert", "verify")},
        )
        return type("GoogleAuthResponse", (), {
            "status": response.status_code,
            "data": response.content,
            "headers": response.headers,
        })()


def refresh_credentials_if_needed(credentials):
    """Refresh expired credentials once, with a bounded token request."""
    if not getattr(credentials, "expired", False):
        return False
    if not getattr(credentials, "refresh_token", None):
        return False
    with _refresh_lock:
        if not getattr(credentials, "expired", False):
            return False
        try:
            credentials.refresh(BoundedGoogleAuthRequest())
        except Exception as exc:
            normalized = normalized_transport_error(exc)
            if normalized:
                raise RuntimeError(normalized) from exc
            raise
        return True


def build_authorized_service(api_name, version, credentials):
    """Build a Google API client with a real socket timeout.

    The explicit fake builders used by offline tests remain handled by each
    provider; this helper is only used for the real discovery transport.
    """
    import httplib2
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build

    refresh_credentials_if_needed(credentials)
    http = httplib2.Http(timeout=GOOGLE_READ_TIMEOUT_SECONDS)
    authorized = AuthorizedHttp(credentials, http=http)
    return build(api_name, version, http=authorized, cache_discovery=False)


def normalized_transport_error(exc):
    import socket
    try:
        import requests
        request_timeout = isinstance(exc, requests.Timeout)
    except Exception:
        request_timeout = False

    if request_timeout or isinstance(exc, (TimeoutError, socket.timeout)):
        return "TIMEOUT"
    text = str(exc).casefold()
    if any(token in text for token in ("name or service not known", "getaddrinfo", "nodename", "network is unreachable", "connection refused")):
        return "NETWORK_UNAVAILABLE"
    return None
