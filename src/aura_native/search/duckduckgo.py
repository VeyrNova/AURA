from __future__ import annotations

from html.parser import HTMLParser
import html
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

from .service import SearchError


class _ResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._capture = ""
        self._href = ""
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if tag == "a" and "result__a" in classes:
            self._capture, self._href, self._parts = "title", dict(attrs).get("href", ""), []
        elif tag in {"a", "div"} and "result__snippet" in classes:
            self._capture, self._parts = "snippet", []

    def handle_data(self, data):
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if self._capture == "title" and tag == "a":
            self.results.append({"title": " ".join(self._parts).strip(), "url": self._href, "snippet": "", "provider": "duckduckgo"})
            self._capture = ""
        elif self._capture == "snippet" and tag in {"a", "div"}:
            if self.results:
                self.results[-1]["snippet"] = " ".join(self._parts).strip()
            self._capture = ""


def _destination_url(value: str) -> str:
    value = html.unescape(str(value or ""))
    parsed = urlsplit(value)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        return parse_qs(parsed.query).get("uddg", [""])[0]
    return value


class DuckDuckGoHtmlBackend:
    endpoint = "https://html.duckduckgo.com/html/"

    def search(self, query: str, *, limit: int, timeout: float):
        request = Request(
            self.endpoint,
            data=urlencode({"q": query}).encode("utf-8"),
            headers={"User-Agent": "AURA-Native/1.0", "Accept": "text/html"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get_content_type()
                if content_type != "text/html":
                    raise SearchError("invalid_response", "unexpected response type")
                body = response.read(1_500_001)
                if len(body) > 1_500_000:
                    raise SearchError("invalid_response", "response too large")
        except (TimeoutError, socket.timeout) as exc:
            raise SearchError("timeout", "search timed out") from exc
        except HTTPError as exc:
            raise SearchError("network_unavailable" if exc.code >= 500 else "provider_error") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise SearchError("timeout", "search timed out") from exc
            raise SearchError("network_unavailable", "network unavailable") from exc
        parser = _ResultsParser()
        parser.feed(body.decode("utf-8", errors="replace"))
        rows = []
        for item in parser.results:
            item["url"] = _destination_url(item["url"])
            rows.append(item)
            if len(rows) >= limit:
                break
        return rows
