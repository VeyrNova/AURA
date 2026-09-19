"""
notifications.py
Notifications natives Windows (section 31 du cahier des charges), via
QSystemTrayIcon : aucune dependance externe supplementaire necessaire.
"""
import logging
from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtGui import QIcon, QPixmap, QColor

logger = logging.getLogger("aura.notifications")


class NotificationService:
    def __init__(self, app_name: str = "AURA"):
        self.app_name = app_name
        self.tray_icon = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("Zone de notification systeme indisponible : "
                            "les notifications desktop seront desactivees.")
            return

        self.tray_icon = QSystemTrayIcon(self._build_icon())
        self.tray_icon.setToolTip(app_name)
        self.tray_icon.show()

    @staticmethod
    def _build_icon() -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 200, 255))
        return QIcon(pixmap)

    def notify(self, title: str, message: str):
        if self.tray_icon is None:
            logger.info(f"[Notification indisponible] {title} — {message}")
            return
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 8000)
