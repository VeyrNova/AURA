from PySide6.QtCore import QObject, Qt, Signal, Slot

class QtBusDispatcher(QObject):
    """Owns bus draining on the QObject/UI thread only."""
    wakeRequested = Signal()
    def __init__(self, bus, parent=None):
        super().__init__(parent); self._bus=bus; self._active=True
        self.wakeRequested.connect(self.drain, Qt.QueuedConnection); bus.set_waker(self.wakeRequested.emit)
    @Slot()
    def drain(self):
        if self._active:self._bus.drain()
    def close(self):
        self._active=False; self._bus.set_waker(None)
