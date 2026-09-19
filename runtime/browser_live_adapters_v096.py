
from __future__ import annotations

class BrowserLiveToolAdapters:
    # Translate existing AURA ToolResult/ToolSource into BrowserProvider adapters.

    def __init__(
        self,
        *,
        web_search_tool,
        web_fetch_tool,
        search_invoker,
        fetch_invoker,
    ):
        self.web_search_tool = web_search_tool
        self.web_fetch_tool = web_fetch_tool
        self.search_invoker = search_invoker
        self.fetch_invoker = fetch_invoker

    @staticmethod
    def _source_dict(source):
        if source is None:
            return None

        # Real AURA ToolSource contract: name / host / checked_at / url.
        # Keep legacy fallbacks so this bridge stays tolerant without touching
        # the existing Web stack.
        title = getattr(source, "name", None)
        if title is None:
            title = getattr(source, "title", "")

        publisher = getattr(source, "host", None)
        if publisher is None:
            publisher = getattr(source, "publisher", "")

        return {
            "title": str(title or ""),
            "publisher": str(publisher or ""),
            "checked_at": str(getattr(source, "checked_at", "") or ""),
            "url": str(getattr(source, "url", "") or ""),
        }

    @classmethod
    def _normalize_tool_result(cls, result):
        # Real AURA ToolResult contract:
        # ok / response / category / source / sources / ...
        # Legacy fallbacks are read-only compatibility only.
        response = getattr(result, "response", None)
        if response is None:
            response = getattr(result, "answer", "")

        category = getattr(result, "category", None)
        if category is None:
            category = getattr(result, "tool", "")

        origin = getattr(result, "source", None)
        if origin is None:
            origin = getattr(result, "status", "")

        category = str(category or "")
        origin = str(origin or "")

        return {
            "ok": bool(getattr(result, "ok", False)),
            "answer": str(response or ""),
            "tool": category or origin,
            "status": origin or category,
            "complete": bool(getattr(result, "complete", True)),
            "sources": [
                item
                for item in (
                    cls._source_dict(source)
                    for source in tuple(getattr(result, "sources", ()) or ())
                )
                if item is not None
            ],
        }

    def search(self, query: str):
        result = self.search_invoker(
            self.web_search_tool,
            str(query or "").strip(),
        )
        normalized = self._normalize_tool_result(result)

        if not normalized["ok"]:
            raise RuntimeError(
                "existing_web_search_failed:" + normalized["status"]
            )

        rows = []
        for source in normalized["sources"]:
            rows.append(
                {
                    "title": source["title"] or source["publisher"] or "Web source",
                    "url": source["url"],
                    "publisher": source["publisher"],
                    "checked_at": source["checked_at"],
                }
            )

        return {
            "query": str(query or "").strip(),
            "answer": normalized["answer"],
            "results": rows,
            "sources": normalized["sources"],
            "existing_tool": normalized["tool"],
        }

    def read(self, url: str):
        requested_url = str(url or "").strip()
        result = self.fetch_invoker(
            self.web_fetch_tool,
            requested_url,
        )
        normalized = self._normalize_tool_result(result)

        if not normalized["ok"]:
            raise RuntimeError(
                "existing_web_fetch_failed:" + normalized["status"]
            )

        final_url = requested_url
        for source in normalized["sources"]:
            if source["url"]:
                final_url = source["url"]
                break

        return {
            "final_url": final_url,
            "content": normalized["answer"],
            "sources": normalized["sources"],
            "existing_tool": normalized["tool"],
        }
