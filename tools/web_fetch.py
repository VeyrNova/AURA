from __future__ import annotations

import html
import re
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser

from tools.models import ToolResult, ToolSource
from tools.safe_http import SafeHTTPClient, SafeHTTPError


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "article", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        text = re.sub(r"\s+", " ", html.unescape(data or "")).strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        self.parts.append(text)

    def text(self) -> str:
        text = " ".join(self.parts)
        return re.sub(r"\s+", " ", text).strip()


class WebFetchTool:
    def __init__(self, client: SafeHTTPClient, *, max_text_chars: int = 1800):
        self.client = client
        self.max_text_chars = max(400, int(max_text_chars))

    def execute(self, url: str) -> ToolResult:
        try:
            response = self.client.get(url, allowed_types=("text/html", "text/plain"))
            charset = "utf-8"
            raw = response.body.decode(charset, errors="replace")
            title = ""
            if response.content_type.startswith("text/html"):
                parser = _TextExtractor()
                parser.feed(raw)
                text = parser.text()
                title = parser.title
            else:
                text = re.sub(r"\s+", " ", raw).strip()
            if not text:
                return ToolResult(False, "La page est accessible mais je n'y ai trouvé aucun texte exploitable.", "web_fetch", "empty_page")
            text = text[: self.max_text_chars].rstrip()
            host = urllib.parse.urlsplit(response.url).hostname or "source Web"
            checked = datetime.now().astimezone().isoformat(timespec="minutes")
            heading = f"« {title} » sur {host}" if title else host
            answer = f"J'ai lu {heading}. Extrait vérifié à {datetime.now().astimezone().strftime('%H:%M')} : {text}"
            source = ToolSource(title or host, host, checked, response.url)
            return ToolResult(True, answer, "web_fetch", host, (source,))
        except SafeHTTPError as exc:
            return ToolResult(False, f"Je n'ai pas pu lire cette page : {exc}", "web_fetch", "fetch_error")
