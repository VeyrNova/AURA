from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit


READ_ONLY_CAPABILITIES = frozenset({
    "browser.open",
    "browser.navigate",
    "browser.read",
    "browser.extract",
    "browser.search",
})

CONFIRMATION_ONLY_CAPABILITIES = frozenset({
    "browser.click",
    "browser.fill",
    "browser.submit",
    "browser.download",
})

ORCHESTRATED_CAPABILITIES = frozenset({
    "browser.workflow",
})

ALL_BROWSER_CAPABILITIES = (
    READ_ONLY_CAPABILITIES
    | CONFIRMATION_ONLY_CAPABILITIES
    | ORCHESTRATED_CAPABILITIES
)


@dataclass(frozen=True)
class BrowserRouteIntentV096:
    provider_id: str
    capability_id: str
    params: dict
    summary: str
    route_kind: str


def _clean(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def _extract_url(text: str) -> str:
    raw = _clean(text)
    match = re.search(r"https?://[^\s<>\"]+", raw, flags=re.IGNORECASE)
    if match:
        return match.group(0).rstrip(".,;:!?)]}")
    match = re.search(
        r"\b(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:/[^\s<>\"]*)?",
        raw,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    candidate = match.group(0).rstrip(".,;:!?)]}")
    if candidate.lower().startswith(("http://", "https://")):
        return candidate
    return "https://" + candidate


def _valid_http_url(url: str) -> bool:
    try:
        parsed = urlsplit(str(url or "").strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _after_keywords(text: str, keywords: tuple[str, ...]) -> str:
    raw = _clean(text)
    lowered = raw.casefold()
    best = None
    for keyword in keywords:
        idx = lowered.find(keyword.casefold())
        if idx >= 0:
            end = idx + len(keyword)
            if best is None or end < best:
                best = end
    if best is None:
        return ""
    value = raw[best:].strip(" \t:,-")
    return value


def resolve_browser_route_v096(text: str):
    raw = _clean(text)
    if not raw:
        return None
    normalized = raw.casefold()

    # Explicit search phrasing. Existing generic Web search remains authoritative;
    # this route is intentionally limited to explicit browser-language commands.
    search_markers = (
        "navigateur cherche ",
        "navigateur recherche ",
        "cherche dans le navigateur ",
        "recherche dans le navigateur ",
        "browser search ",
        "search in browser ",
    )
    if any(marker in normalized for marker in search_markers):
        query = _after_keywords(raw, search_markers)
        if query:
            return BrowserRouteIntentV096(
                "browser.provider",
                "browser.search",
                {"query": query},
                "Recherche navigateur : " + query,
                "read_only",
            )

    url = _extract_url(raw)

    read_markers = (
        "lis cette page",
        "lire cette page",
        "lis la page",
        "lire la page",
        "browser read",
        "read this page",
    )
    if url and any(marker in normalized for marker in read_markers):
        return BrowserRouteIntentV096(
            "browser.provider",
            "browser.read",
            {"url": url},
            "Lire la page " + url,
            "read_only",
        )

    extract_markers = (
        "extrais cette page",
        "extraire cette page",
        "extrais le contenu",
        "extraire le contenu",
        "browser extract",
        "extract this page",
    )
    if url and any(marker in normalized for marker in extract_markers):
        return BrowserRouteIntentV096(
            "browser.provider",
            "browser.extract",
            {"url": url},
            "Extraire le contenu de " + url,
            "read_only",
        )

    open_markers = (
        "ouvre dans le navigateur",
        "ouvrir dans le navigateur",
        "browser open",
        "open in browser",
    )
    if url and any(marker in normalized for marker in open_markers):
        return BrowserRouteIntentV096(
            "browser.provider",
            "browser.open",
            {"url": url},
            "Ouvrir " + url,
            "read_only",
        )

    navigate_markers = (
        "navigue vers",
        "naviguer vers",
        "va sur le site",
        "browser navigate",
        "navigate to",
    )
    if url and any(marker in normalized for marker in navigate_markers):
        return BrowserRouteIntentV096(
            "browser.provider",
            "browser.navigate",
            {"url": url},
            "Naviguer vers " + url,
            "read_only",
        )

    # State-changing capabilities are routable only to the existing confirmation
    # path. The browser provider still owns the final fail-closed behavior.
    click_match = re.search(
        r"(?:navigateur\s+)?(?:clique|cliquer|browser click)\s+(?:sur\s+)?(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if click_match:
        selector = click_match.group(1).strip()
        if selector:
            return BrowserRouteIntentV096(
                "browser.provider",
                "browser.click",
                {"selector": selector},
                "Cliquer dans le navigateur",
                "confirmation_only",
            )

    fill_match = re.search(
        r"(?:navigateur\s+)?(?:remplis|remplir|browser fill)\s+(.+?)\s+(?:avec|par|with)\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if fill_match:
        selector = fill_match.group(1).strip()
        value = fill_match.group(2).strip()
        if selector and value:
            return BrowserRouteIntentV096(
                "browser.provider",
                "browser.fill",
                {"selector": selector, "value": value},
                "Remplir un champ dans le navigateur",
                "confirmation_only",
            )

    submit_match = re.search(
        r"(?:navigateur\s+)?(?:valide|valider|soumets|soumettre|browser submit)(?:\s+(.+))?$",
        raw,
        flags=re.IGNORECASE,
    )
    if submit_match:
        selector = (submit_match.group(1) or "form").strip()
        return BrowserRouteIntentV096(
            "browser.provider",
            "browser.submit",
            {"selector": selector},
            "Soumettre dans le navigateur",
            "confirmation_only",
        )

    download_markers = (
        "telecharge dans le navigateur",
        "télécharge dans le navigateur",
        "telecharger dans le navigateur",
        "télécharger dans le navigateur",
        "browser download",
    )
    if url and any(marker in normalized for marker in download_markers):
        return BrowserRouteIntentV096(
            "browser.provider",
            "browser.download",
            {"url": url},
            "Telecharger depuis " + url,
            "confirmation_only",
        )

    return None


def dispatch_browser_route_v096(dispatcher, text: str):
    intent = resolve_browser_route_v096(text)
    if intent is None:
        return None
    if intent.capability_id not in ALL_BROWSER_CAPABILITIES:
        raise RuntimeError("browser capability outside certified set")
    return dispatcher.dispatch_capability(
        provider_id=intent.provider_id,
        capability_id=intent.capability_id,
        params=dict(intent.params),
        summary=intent.summary,
    )
