"""Local-only mail summaries with bounded input and an in-memory cache."""
from concurrent.futures import ThreadPoolExecutor
from time import time
class MailSummaryService:
    def __init__(self, summarizer=None, *, max_input=4000, max_output=280):
        self.summarizer = summarizer
        self.max_input = int(max_input); self.max_output = int(max_output); self._cache = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="AuraMailSummary")
        self.provider_mode = "LOCAL_ONLY"

    def summarize(self, message, model_id="local"):
        key = self.cache_key(message, model_id)
        if key in self._cache: return self._cache[key]
        fallback = str(getattr(message, "snippet", "") or getattr(message, "subject", "") or "Message sans contenu").strip()
        text = str(getattr(message, "body", "") or fallback).strip()[:self.max_input]
        result = fallback
        if self.summarizer is not None and text:
            try:
                value = str(self.summarizer(text) or "").strip()
                if value: result = value[:self.max_output]
            except Exception:
                result = fallback
        self._cache[key] = result
        return result

    def cache_key(self, message, model_id="local"):
        return (str(getattr(message, "message_id", "")), str(getattr(message, "date", "")), str(model_id))

    def summarize_async(self, message, callback, *, generation=0, model_id="local"):
        key = self.cache_key(message, model_id)
        if key in self._cache:
            callback(message, self._cache[key], generation, False); return None
        def work():
            value = self.summarize(message, model_id)
            callback(message, value, generation, True)
        return self._executor.submit(work)

    def close(self): self._executor.shutdown(wait=False, cancel_futures=True)
