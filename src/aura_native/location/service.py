"""Native current-location boundary. No IP or browser geolocation fallback."""
from __future__ import annotations
from dataclasses import dataclass
from PySide6.QtCore import QObject, QTimer, Signal

@dataclass(frozen=True)
class CurrentLocation:
    latitude: float
    longitude: float
    accuracy: float | None = None
    timestamp: str = ''

class QtCurrentLocationProvider(QObject):
    """QtPositioning provider; unavailable when Windows exposes no source."""
    position = Signal(object)
    error = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self.source = None
        try:
            from PySide6.QtPositioning import QGeoPositionInfoSource
            self.source = QGeoPositionInfoSource.createDefaultSource(self)
            if self.source:
                self.source.positionUpdated.connect(self._position)
                self.source.errorOccurred.connect(lambda *_: self.error.emit('error'))
        except Exception:
            self.source = None
    def request(self):
        if not self.source:
            self.error.emit('unavailable'); return
        self.source.requestUpdate(10000)
    def _position(self, info):
        c = info.coordinate()
        if not c.isValid(): self.error.emit('error'); return
        self.position.emit(CurrentLocation(c.latitude(), c.longitude(), c.accuracy(), info.timestamp().toString()))

class FakeCurrentLocationProvider(QObject):
    position = Signal(object)
    error = Signal(str)
    def __init__(self, result=None, error=''):
        super().__init__(); self.result=result; self.error_code=error; self.calls=0
    def request(self):
        self.calls += 1
        if self.error_code: self.error.emit(self.error_code)
        elif self.result is not None: self.position.emit(self.result)

class CurrentLocationService(QObject):
    stateChanged = Signal(); locationChanged = Signal()
    def __init__(self, provider=None, timeout_ms=10000, parent=None):
        super().__init__(parent); self.provider=provider or QtCurrentLocationProvider(self); self.timeout_ms=timeout_ms; self._state='idle'; self._location=None
        self._timer=QTimer(self); self._timer.setSingleShot(True); self._timer.timeout.connect(lambda: self._finish('timeout'))
        self.provider.position.connect(self._ready); self.provider.error.connect(self._finish)
    @property
    def state(self): return self._state
    @property
    def location(self): return self._location
    def request(self):
        self._location=None; self._state='requesting'; self.stateChanged.emit(); self._timer.start(self.timeout_ms); self.provider.request()
    def _ready(self, location): self._timer.stop(); self._location=location; self._finish('ready')
    def _finish(self, state):
        self._timer.stop(); self._state={'denied':'permission_denied','permission_required':'permission_required'}.get(str(state), str(state)); self.stateChanged.emit(); self.locationChanged.emit()
