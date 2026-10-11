from __future__ import annotations

from threading import Thread

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from .service import SearchError, safe_web_url


class NativeSearchBridge(QObject):
    changed = Signal()
    _completed = Signal(object, str, int)

    def __init__(self, service, parent=None, opener=None) -> None:
        super().__init__(parent)
        self.service = service
        self._opener = opener or QDesktopServices.openUrl
        self._state = "idle"
        self._query = ""
        self._results: list[dict] = []
        self._error = ""
        self._generation = 0
        self._completed.connect(self._apply_result)

    @Property(str, notify=changed)
    def state(self): return self._state

    @Property(str, notify=changed)
    def query(self): return self._query

    @Property("QVariantList", notify=changed)
    def results(self): return list(self._results)

    @Property(str, notify=changed)
    def errorCode(self): return self._error

    @Property(bool, notify=changed)
    def loading(self): return self._state == "loading"

    @Slot(str)
    def search(self, query):
        self._query = " ".join(str(query or "").split())
        self._generation += 1
        generation = self._generation
        if not self._query:
            self._results, self._error, self._state = [], "", "idle"
            self.changed.emit(); return
        self._results, self._error, self._state = [], "", "loading"
        self.changed.emit()
        def worker():
            try:
                rows = [item.to_dict() for item in self.service.search(self._query)]
                error = ""
            except SearchError as exc:
                rows, error = [], exc.code
            except Exception:
                rows, error = [], "provider_error"
            self._completed.emit(rows, error, generation)
        Thread(target=worker, daemon=True, name="AuraNativeWebSearch").start()

    @Slot(object, str, int)
    def _apply_result(self, rows, error, generation):
        if generation != self._generation:
            return
        self._results = list(rows)
        self._error = error
        self._state = ("timeout" if error == "timeout" else
                       "offline" if error == "network_unavailable" else
                       "error" if error else
                       "ready" if self._results else "empty")
        self.changed.emit()

    @Slot()
    def cancel(self):
        self._generation += 1
        self._state, self._error = "idle", ""
        self.changed.emit()

    @Slot(str, result=bool)
    def openResult(self, url):
        safe = safe_web_url(url)
        return bool(safe and self._opener(QUrl(safe)))
