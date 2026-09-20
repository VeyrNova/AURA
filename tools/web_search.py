from __future__ import annotations

"""Zero-cost Web search for AURA Runtime v2.

v0.7.2.1 RC2.4 changes the normal explicit-research path after real-world
validation showed that Gemini 2.5 Flash / Flash-Lite Search Grounding can be
listed by ``models.list`` yet still return HTTP 404 for new Gemini users.

The primary search path is now the local ``ddgs`` metasearch client.  It does
not require an API key or a paid search account.  AURA tries a fixed allowlist
of public search backends *one at a time* (Google first by default, followed by
DuckDuckGo, Startpage, Yahoo and Mojeek).  Trying engines independently is deliberate:
one blocked/rate-limited engine must not poison successful results from another
engine.

This is not the official Google Search API.  The Google backend is an
unofficial Web-search backend exposed by DDGS and can be rate-limited or
blocked by the search engine.  When that happens AURA transparently continues
to the next zero-cost backend and reports which backend actually succeeded.

No paid provider fallback is present.  If DDGS is unavailable, every backend
fails, or no source URL is returned, the tool fails closed instead of asking a
language model to answer from memory.
"""

import importlib
import importlib.metadata
import importlib.util
import logging
import re
import sys
from pathlib import Path
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Iterable

import requests

from config.settings import settings
from tools.models import ToolResult, ToolSource

logger = logging.getLogger("aura.tools.web_search")


_ALLOWED_BACKENDS = ("google", "duckduckgo", "startpage", "yahoo", "mojeek")
_BACKEND_LABELS = {
    "google": "Google Web",
    "duckduckgo": "DuckDuckGo",
    "startpage": "Startpage",
    "yahoo": "Yahoo",
    "mojeek": "Mojeek",
    "google_news_rss": "Google News RSS",
}


_VENDORED_SEARCH_PATH = Path(__file__).resolve().parents[1] / "vendor" / "search_rc24"


def _ensure_vendor_path() -> None:
    """Expose AURA's private search dependency without touching global Python."""
    try:
        if _VENDORED_SEARCH_PATH.is_dir():
            value = str(_VENDORED_SEARCH_PATH)
            if value not in sys.path:
                sys.path.insert(0, value)
    except Exception:
        pass


def ddgs_available() -> bool:
    """Read-only dependency probe; never performs a network request."""
    _ensure_vendor_path()
    try:
        return importlib.util.find_spec("ddgs") is not None
    except Exception:
        return False


def ddgs_version() -> str:
    _ensure_vendor_path()
    try:
        return importlib.metadata.version("ddgs")
    except Exception:
        return "unknown" if ddgs_available() else "missing"


class FreeWebSearchTool:
    """No-key metasearch with fixed backends and source-labelled results."""

    def __init__(
        self,
        client=None,
        api_key: str = "",
        *,
        backends: str | Iterable[str] | None = None,
        region: str | None = None,
        safesearch: str | None = None,
        timeout: float | None = None,
        ddgs_factory=None,
    ):
        # ``client`` and ``api_key`` are accepted for constructor compatibility
        # with historical Brave / Google-search call sites.  RC2.4 does not use
        # any search API key.
        self.client = client
        self.api_key = str(api_key or "")
        raw = backends if backends is not None else settings.FREE_WEB_SEARCH_BACKENDS
        if isinstance(raw, str):
            items = [x.strip().casefold() for x in raw.split(",")]
        else:
            items = [str(x or "").strip().casefold() for x in raw]
        # RC3.1 runtime migration: RC2.4 documented ``bing`` in .env even
        # though DDGS 9.14.4 reports that backend disabled and silently falls
        # back to auto. Do not rewrite the user's .env; expand the legacy token
        # to truthful supported fallbacks in memory instead.
        migrated_items: list[str] = []
        legacy_bing = False
        for item in items:
            if item == "bing":
                legacy_bing = True
                migrated_items.extend(("yahoo", "mojeek"))
            else:
                migrated_items.append(item)
        self.backends = tuple(dict.fromkeys(x for x in migrated_items if x in _ALLOWED_BACKENDS)) or _ALLOWED_BACKENDS
        if legacy_bing:
            logger.info("Free Web Search legacy backend migration bing -> yahoo,mojeek (in-memory only)")
        self.region = str(region or settings.FREE_WEB_SEARCH_REGION).strip() or "fr-fr"
        safe = str(safesearch or settings.FREE_WEB_SEARCH_SAFESEARCH).strip().lower() or "moderate"
        self.safesearch = safe if safe in {"on", "moderate", "off"} else "moderate"
        self.timeout = max(2, min(int(round(float(timeout or settings.FREE_WEB_SEARCH_TIMEOUT_SECONDS))), 30))
        self._ddgs_factory = ddgs_factory
        self._last_backend = ""
        self._synthesis_session = requests.Session()
        self._synthesis_session.trust_env = False

    @staticmethod
    def _clean_text(value: Any, limit: int) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= limit:
            return text
        return text[: max(1, limit - 1)].rstrip() + "…"

    @staticmethod
    def _safe_url(value: Any) -> str:
        url = str(value or "").strip()
        try:
            parsed = urllib.parse.urlsplit(url)
        except Exception:
            return ""
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ""
        return url

    @staticmethod
    def _news_like(query: str) -> bool:
        q = query.casefold()
        return any(
            marker in q
            for marker in (
                "actualité", "actualite", "actualités", "actualites", "news",
                "dernière", "derniere", "dernières", "dernieres", "latest",
                "aujourd'hui", "aujourd hui", "récent", "recent",
            )
        )

    def _factory(self):
        if self._ddgs_factory is not None:
            return self._ddgs_factory
        _ensure_vendor_path()
        module = importlib.import_module("ddgs")
        factory = getattr(module, "DDGS", None)
        if factory is None:
            raise RuntimeError("DDGS class missing")
        return factory

    def _search_one_backend(self, backend: str, query: str, requested: int) -> list[dict[str, str]]:
        factory = self._factory()
        # Construct one client per engine attempt so a failing engine cannot
        # retain poisoned state for the next backend.
        searcher = factory(timeout=self.timeout)
        kwargs: dict[str, Any] = {
            "region": self.region,
            "safesearch": self.safesearch,
            "max_results": requested,
            "backend": backend,
        }
        if self._news_like(query):
            # Text search supports a recency hint on DDGS engines.  We avoid
            # DDGS.news() here because its backend set does not include Google.
            kwargs["timelimit"] = "w"
        raw = searcher.text(query, **kwargs)
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            url = self._safe_url(item.get("href") or item.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            title = self._clean_text(item.get("title") or urllib.parse.urlsplit(url).hostname or "Résultat Web", 180)
            body = self._clean_text(item.get("body") or item.get("description") or "", 420)
            results.append({"title": title, "url": url, "body": body})
            if len(results) >= requested:
                break
        return results

    def _search_google_news_rss(self, query: str, requested: int) -> list[dict[str, str]]:
        """Zero-key RSS fallback restricted to current/news queries.

        Uses AURA's existing SafeHTTPClient, so SSRF protections, proxy blocking,
        standard-port enforcement and response-size limits stay active.
        """
        if self.client is None:
            return []
        q = urllib.parse.quote_plus(str(query or "").strip())
        if not q:
            return []
        url = (
            "https://news.google.com/rss/search?q=" + q
            + "&hl=fr&gl=FR&ceid=FR:fr"
        )
        response = self.client.get(
            url,
            headers={
                "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.1",
                "User-Agent": "AURA/0.7.2 (+local controlled news fallback)",
            },
            allowed_types=("application/rss+xml", "application/xml", "text/xml", "text/plain"),
        )
        root = ET.fromstring(response.body)
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in root.findall(".//item"):
            title = self._clean_text(item.findtext("title") or "Actualité", 180)
            link = self._safe_url(item.findtext("link") or "")
            if not link or link in seen:
                continue
            seen.add(link)
            source_node = item.find("source")
            source_name = self._clean_text(source_node.text if source_node is not None else "", 120)
            published = self._clean_text(item.findtext("pubDate") or "", 120)
            body_parts = []
            if source_name:
                body_parts.append(f"Source : {source_name}.")
            if published:
                body_parts.append(f"Publié : {published}.")
            body = " ".join(body_parts) or "Article d'actualité disponible via Google News."
            results.append({"title": title, "url": link, "body": body})
            if len(results) >= requested:
                break
        return results

    @staticmethod
    def _format_results(results: list[dict[str, str]], backend: str) -> str:
        label = _BACKEND_LABELS.get(backend, backend)
        lines = [f"J’ai trouvé {len(results)} résultat{'s' if len(results) != 1 else ''} via {label} :"]
        for index, item in enumerate(results, 1):
            title = item["title"]
            body = item.get("body") or "Source Web disponible."
            lines.append(f"{index}. **{title}** — {body}")
        return "\n\n".join(lines)

    @staticmethod
    def _groq_host_allowed() -> bool:
        try:
            parsed = urllib.parse.urlsplit(str(settings.GROQ_BASE_URL or ""))
            return parsed.scheme == "https" and parsed.hostname == "api.groq.com"
        except Exception:
            return False

    def _synthesize_with_groq(self, query: str, results: list[dict[str, str]]) -> str:
        """Optional bounded synthesis from search snippets only.

        Search remains successful even if Groq synthesis is unavailable; the
        deterministic formatted result list is then returned instead.
        """
        if not bool(getattr(settings, "FREE_WEB_SEARCH_SYNTHESIS_ENABLED", True)):
            return ""
        if not bool(getattr(settings, "GROQ_ENABLED", False)) or not str(getattr(settings, "GROQ_API_KEY", "") or "").strip():
            return ""
        if not self._groq_host_allowed():
            logger.warning("Free Web Search synthesis skipped: Groq host rejected")
            return ""

        evidence = []
        for index, item in enumerate(results, 1):
            evidence.append(
                f"[{index}] {item['title']}\nURL: {item['url']}\nExtrait: {item.get('body') or '(aucun extrait)'}"
            )
        payload = {
            "model": settings.GROQ_FAST_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Tu synthétises des résultats de recherche Web pour AURA. "
                        "Utilise UNIQUEMENT les extraits fournis. N'invente aucun fait. "
                        "Si les extraits sont insuffisants ou contradictoires, dis-le. "
                        "Réponds en français et cite les sources par [1], [2], etc."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Requête: {query}\n\nRésultats:\n" + "\n\n".join(evidence),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 700,
            "stream": False,
        }
        try:
            response = self._synthesis_session.post(
                f"{settings.GROQ_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=(float(settings.GROQ_CONNECT_TIMEOUT), min(12.0, float(settings.GROQ_READ_TIMEOUT_SECONDS))),
                allow_redirects=False,
            )
            if int(response.status_code or 0) >= 400:
                logger.warning("Free Web Search Groq synthesis HTTP status=%d", int(response.status_code or 0))
                return ""
            data = response.json()
            text = str((((data or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            return text
        except Exception as exc:
            logger.warning("Free Web Search Groq synthesis unavailable: %s", type(exc).__name__)
            return ""

    def execute(self, query: str, *, count: int = 4) -> ToolResult:
        query = str(query or "").strip()
        requested = max(1, min(int(count), 8))
        if not query:
            return ToolResult(False, "Que dois-je rechercher sur le Web ?", "web_search", "missing_query", complete=False)
        if not settings.WEB_SEARCH_ENABLED or not settings.FREE_WEB_SEARCH_ENABLED:
            return ToolResult(
                False,
                "La recherche Web gratuite d'AURA est désactivée dans la configuration locale.",
                "web_search",
                "research_engine_disabled",
                expected_items=requested,
                complete=False,
            )

        ddgs_ok = bool(self._ddgs_factory is not None or ddgs_available())
        news_like = self._news_like(query)
        if not ddgs_ok and not news_like:
            return ToolResult(
                False,
                "Le moteur de recherche gratuit DDGS n'est pas installé. Lance INSTALLER_RECHERCHE_WEB_GRATUITE.bat puis redémarre AURA.",
                "web_search",
                "dependency_missing",
                expected_items=requested,
                complete=False,
                data={"dependency": "ddgs"},
            )

        started = time.perf_counter()
        errors: list[str] = []
        chosen_backend = ""
        results: list[dict[str, str]] = []
        if ddgs_ok:
            for backend in self.backends:
                try:
                    candidate = self._search_one_backend(backend, query, requested)
                except Exception as exc:
                    errors.append(f"{backend}:{type(exc).__name__}")
                    logger.warning("Free Web Search backend failed backend=%s error=%s", backend, type(exc).__name__)
                    continue
                if candidate:
                    chosen_backend = backend
                    results = candidate
                    break
                errors.append(f"{backend}:empty")
                logger.warning("Free Web Search backend empty backend=%s", backend)

        # P0.6.2.2.2 — bounded reliability fallback. When every DDGS backend
        # fails on a current/news request, try one public RSS endpoint instead
        # of failing immediately or asking an LLM to answer from memory.
        if not results and news_like:
            try:
                candidate = self._search_google_news_rss(query, requested)
            except Exception as exc:
                errors.append(f"google_news_rss:{type(exc).__name__}")
                logger.warning("Google News RSS fallback failed error=%s", type(exc).__name__)
            else:
                if candidate:
                    chosen_backend = "google_news_rss"
                    results = candidate
                else:
                    errors.append("google_news_rss:empty")
                    logger.warning("Google News RSS fallback empty")

        latency = time.perf_counter() - started
        if not results:
            return ToolResult(
                False,
                "Aucun moteur de recherche Web gratuit n'a répondu correctement. AURA n'utilise aucun moteur payant de secours.",
                "web_search",
                "free_search_unavailable",
                expected_items=requested,
                complete=False,
                data={"attempted_backends": list(self.backends) + (["google_news_rss"] if news_like else []), "errors": errors, "latency_seconds": round(latency, 3)},
            )

        checked = datetime.now().astimezone().isoformat(timespec="minutes")
        sources = tuple(
            ToolSource(
                item["title"],
                urllib.parse.urlsplit(item["url"]).hostname or item["title"],
                checked,
                item["url"],
            )
            for item in results
        )
        response = self._synthesize_with_groq(query, results)
        synthesized = bool(response)
        if not response:
            response = self._format_results(results, chosen_backend)
        self._last_backend = chosen_backend
        logger.info(
            "Free Web Search complete backend=%s latency=%.3fs results=%d requested=%d ddgs=%s synthesis=%s zero_cost=True paid_fallback=False",
            chosen_backend,
            latency,
            len(results),
            requested,
            ddgs_version(),
            "groq" if synthesized else "deterministic",
        )
        return ToolResult(
            True,
            response,
            "web_search",
            "free-web-search",
            sources,
            item_count=len(results),
            expected_items=requested,
            complete=len(results) >= requested,
            data={
                "provider": "google-news-rss" if chosen_backend == "google_news_rss" else "ddgs",
                "backend": chosen_backend,
                "backend_label": _BACKEND_LABELS.get(chosen_backend, chosen_backend),
                "attempted_backends": list(self.backends) + (["google_news_rss"] if news_like else []),
                "latency_seconds": round(latency, 3),
                "zero_cost": True,
                "paid_fallback": False,
                "synthesis": "groq" if synthesized else "deterministic",
                "ddgs_version": ddgs_version(),
            },
        )


class GoogleSearchGroundingTool(FreeWebSearchTool):
    """Compatibility name kept for old imports; now routes to zero-cost DDGS."""


# Historical name kept so old code/tests import cleanly.  The old Brave API key
# argument is ignored; normal RC2.4 routing never uses Brave's paid API.
BraveSearchTool = FreeWebSearchTool
