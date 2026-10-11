from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

class AuraTrayService(QObject):
    clicked=Signal()
    def __init__(self, window, app, icon_path, shutdown=None, parent=None):
        super().__init__(parent); self.window=window; self.app=app; self.tray=None; self._shutdown=shutdown; self._closed=False
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print('TRAY_AVAILABLE available=false messages_supported=false', flush=True); return
        self.tray=QSystemTrayIcon(QIcon(str(icon_path)), self); self.tray.setToolTip('AURA'); self.tray.messageClicked.connect(self._message_clicked)
        menu=QMenu(); open_action=menu.addAction('OUVRIR AURA'); open_action.triggered.connect(self.open); menu.addSeparator(); quit_action=menu.addAction('QUITTER AURA'); quit_action.triggered.connect(self.quit); self.tray.setContextMenu(menu); self.tray.show()
        print(f'TRAY_AVAILABLE available=true messages_supported={str(self.tray.supportsMessages()).lower()}', flush=True)
    def _message_clicked(self): self.clicked.emit(); self.open(); print('WINDOWS_REMINDER_CLICKED', flush=True)
    def open(self):
        if self.window:
            print('AURA_WINDOW_RESTORE_REQUESTED', flush=True); self.window.showNormal(); self.window.show(); self.window.raise_(); self.window.requestActivate(); print('TRAY_ACTION action=open', flush=True)
    def quit(self):
        print('TRAY_ACTION action=quit', flush=True)
        if self._shutdown: self._shutdown()
        else: self.app.quit()
    def close(self):
        if self._closed: return
        self._closed=True
        if self.tray: self.tray.hide(); self.tray.deleteLater(); self.tray=None
