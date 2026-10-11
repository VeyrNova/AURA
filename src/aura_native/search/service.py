from __future__ import annotations

from typing import Protocol, Sequence
from urllib.parse import urlsplit

from .models import SearchResult


class SearchError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class SearchBackend(Protocol):
    def search(self, query: str, *, limit: int, timeout: float) -> Sequence[object]: ...


def safe_web_url(value: object) -> str:
    text = str(value or "").strip()
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    if parsed.username or parsed.password:
        return ""
    return text


class SearchService:
    def __init__(self, backend: SearchBackend, *, timeout: float = 8.0, limit: int = 12) -> None:
        self.backend = backend
        self.timeout = max(0.1, min(float(timeout), 30.0))
        self.limit = max(1, min(int(limit), 20))

    def search(self, query: str) -> tuple[SearchResult, ...]:
        clean_query = " ".join(str(query or "").split())
        if not clean_query:
            return ()
        try:
            raw_results = self.backend.search(clean_query, limit=self.limit, timeout=self.timeout)
        except SearchError:
            raise
        except TimeoutError as exc:
            raise SearchError("timeout", "search timed out") from exc
        except OSError as exc:
            raise SearchError("network_unavailable", "network unavailable") from exc
        except Exception as exc:
            raise SearchError("provider_error", "search provider failed") from exc

        results: list[SearchResult] = []
        seen: set[str] = set()
        for item in raw_results or ():
            value = item.to_dict() if hasattr(item, "to_dict") else dict(item)
            url = safe_web_url(value.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            domain = (urlsplit(url).hostname or "").lower()
            results.append(SearchResult(
                title=" ".join(str(value.get("title") or domain).split())[:240],
                url=url,
                domain=domain,
                snippet=" ".join(str(value.get("snippet") or "").split())[:600],
                provider=str(value.get("provider") or "web"),
            ))
            if len(results) >= self.limit:
                break
        return tuple(results)
