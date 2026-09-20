"""Security validators for configuration-controlled network endpoints."""
import ipaddress
from urllib.parse import urlparse


class SecurityValidationError(ValueError):
    pass


def _is_literal_loopback_host(hostname: str) -> bool:
    """Accept only localhost or a literal loopback address.

    No DNS resolution is performed here, which avoids hostname/DNS rebinding ambiguity
    for the default local-only LLM policy.
    """
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def validate_service_url(url: str, *, allow_remote: bool = False) -> str:
    """Validate a configured LLM service URL.

    Local HTTP endpoints are allowed. Remote endpoints are disabled by default;
    when explicitly enabled, HTTPS is mandatory.
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise SecurityValidationError("Schema URL non autorise pour le service IA.")
    if not parsed.hostname:
        raise SecurityValidationError("Hote du service IA manquant.")
    if parsed.username or parsed.password:
        raise SecurityValidationError("Les identifiants integres dans une URL sont interdits.")
    if parsed.query or parsed.fragment:
        raise SecurityValidationError("L'URL du service IA ne doit pas contenir query ou fragment.")
    if parsed.path not in {"", "/"}:
        raise SecurityValidationError("L'URL du service IA ne doit pas contenir de chemin personnalise.")

    is_loopback = _is_literal_loopback_host(parsed.hostname)
    if not is_loopback and not allow_remote:
        raise SecurityValidationError("Les services IA distants sont desactives par defaut.")
    if not is_loopback and parsed.scheme != "https":
        raise SecurityValidationError("Un service IA distant doit utiliser HTTPS.")

    return url.rstrip("/")
