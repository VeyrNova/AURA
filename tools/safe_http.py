"""Small fail-closed HTTP client for AURA controlled Internet tools.

This client is intentionally read-only. It rejects non-HTTP(S) schemes, userinfo,
private/link-local/loopback/reserved IP targets, oversized payloads and unsafe
redirects. Proxies are disabled so local environment variables cannot silently
reroute requests through an unexpected endpoint.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class SafeHTTPError(RuntimeError):
    pass


@dataclass(frozen=True)
class HTTPResponse:
    url: str
    status: int
    content_type: str
    body: bytes


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # pragma: no cover - urllib callback
        return None


class SafeHTTPClient:
    def __init__(self, *, timeout: float = 8.0, max_bytes: int = 262_144, max_redirects: int = 3):
        self.timeout = max(1.0, float(timeout))
        self.max_bytes = max(4096, int(max_bytes))
        self.max_redirects = max(0, int(max_redirects))
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirect(),
        )

    @staticmethod
    def _validate_url(url: str) -> urllib.parse.SplitResult:
        try:
            parsed = urllib.parse.urlsplit((url or "").strip())
        except Exception as exc:
            raise SafeHTTPError("URL invalide.") from exc
        if parsed.scheme.lower() not in {"http", "https"}:
            raise SafeHTTPError("Seules les URL HTTP/HTTPS sont autorisées.")
        if not parsed.hostname:
            raise SafeHTTPError("Hôte Internet absent.")
        if parsed.username or parsed.password:
            raise SafeHTTPError("Les identifiants intégrés dans une URL sont refusés.")
        try:
            port = parsed.port
        except ValueError as exc:
            raise SafeHTTPError("Port réseau invalide.") from exc
        if port is not None and port not in {80, 443}:
            raise SafeHTTPError("Les ports réseau non standards sont refusés par AURA.")
        return parsed

    @staticmethod
    def _public_ip(ip_text: str) -> bool:
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            return False
        return bool(ip.is_global)

    def _validate_host_resolution(self, parsed: urllib.parse.SplitResult) -> None:
        host = parsed.hostname or ""
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal is not None:
            if not self._public_ip(str(literal)):
                raise SafeHTTPError("Les adresses réseau locales ou privées sont bloquées.")
            return
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as exc:
            raise SafeHTTPError("Impossible de résoudre l'hôte Internet demandé.") from exc
        addresses = {item[4][0] for item in infos if item and item[4]}
        if not addresses:
            raise SafeHTTPError("Aucune adresse réseau valide n'a été résolue.")
        if any(not self._public_ip(ip) for ip in addresses):
            raise SafeHTTPError("La destination résout vers une adresse locale/privée : requête bloquée.")

    def get(self, url: str, *, headers: dict[str, str] | None = None, allowed_types: tuple[str, ...] = ()) -> HTTPResponse:
        current = (url or "").strip()
        request_headers = {
            "User-Agent": "AURA/0.7.0 (+local controlled web tool)",
            "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.1",
        }
        if headers:
            request_headers.update(headers)
        deadline = time.monotonic() + self.timeout
        for redirect_count in range(self.max_redirects + 1):
            parsed = self._validate_url(current)
            self._validate_host_resolution(parsed)
            req = urllib.request.Request(current, headers=request_headers, method="GET")
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SafeHTTPError("La requête Internet a expiré.")
                with self._opener.open(req, timeout=max(0.5, remaining)) as resp:
                    status = int(getattr(resp, "status", 200) or 200)
                    content_type = (resp.headers.get_content_type() or "application/octet-stream").lower()
                    if allowed_types and not any(content_type.startswith(prefix) for prefix in allowed_types):
                        raise SafeHTTPError(f"Type de contenu refusé : {content_type}.")
                    raw = resp.read(self.max_bytes + 1)
                    if len(raw) > self.max_bytes:
                        raise SafeHTTPError("La réponse Internet dépasse la taille maximale autorisée.")
                    return HTTPResponse(str(resp.geturl() or current), status, content_type, raw)
            except urllib.error.HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    if redirect_count >= self.max_redirects:
                        raise SafeHTTPError("Trop de redirections Internet.") from exc
                    location = exc.headers.get("Location") if exc.headers else None
                    if not location:
                        raise SafeHTTPError("Redirection Internet sans destination.") from exc
                    current = urllib.parse.urljoin(current, location)
                    continue
                raise SafeHTTPError(f"Le serveur Internet a répondu avec l'erreur HTTP {exc.code}.") from exc
            except urllib.error.URLError as exc:
                raise SafeHTTPError("La ressource Internet n'est pas joignable actuellement.") from exc
            except TimeoutError as exc:
                raise SafeHTTPError("La requête Internet a expiré.") from exc
        raise SafeHTTPError("Redirection Internet non autorisée.")

    def get_json(self, url: str, *, headers: dict[str, str] | None = None, allow_list: bool = False) -> tuple[dict | list, HTTPResponse]:
        response = self.get(url, headers=headers, allowed_types=("application/json", "text/json"))
        try:
            payload = json.loads(response.body.decode("utf-8", errors="strict"))
        except Exception as exc:
            raise SafeHTTPError("La source Internet n'a pas renvoyé un JSON valide.") from exc
        if isinstance(payload, dict):
            return payload, response
        if allow_list and isinstance(payload, list):
            return payload, response
        raise SafeHTTPError("Format de réponse Internet inattendu.")
