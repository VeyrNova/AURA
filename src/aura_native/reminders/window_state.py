from enum import Enum
class _Signal:
    def __init__(self): self._slots=[]
    def connect(self, slot): self._slots.append(slot)
    def emit(self, *args):
        for slot in tuple(self._slots): slot(*args)

class WindowState(str, Enum): ACTIVE='active'; INACTIVE='inactive'; MINIMIZED='minimized'; HIDDEN='hidden'; UNKNOWN='unknown'
class WindowStateAdapter:
    def __init__(self, window=None, parent=None): self.changed=_Signal(); self.window=None; self.state=WindowState.UNKNOWN; self.set_window(window)
    def set_window(self, window):
        self.window=window
        if window is None: self._set(WindowState.UNKNOWN); return
        for name in ('visibilityChanged','activeChanged'):
            signal=getattr(window,name,None)
            if signal is not None: signal.connect(lambda *_: self.refresh())
        self.refresh()
    def refresh(self):
        if self.window is None: return self._set(WindowState.UNKNOWN)
        try:
            from PySide6.QtGui import QWindow
            if self.window.visibility() in (QWindow.Minimized, QWindow.Hidden): return self._set(WindowState.MINIMIZED if self.window.visibility()==QWindow.Minimized else WindowState.HIDDEN)
            return self._set(WindowState.ACTIVE if self.window.isActive() else WindowState.INACTIVE)
        except Exception: return self._set(WindowState.UNKNOWN)
    def _set(self, value):
        if self.state != value: self.state=value; self.changed.emit(value.value)
