"""Futuristic gated startup window for AURA v0.7.0.3.

The production launcher displays this window while the local core and safe
prewarm sequence initialize. The interactive MainWindow remains hidden until
startup_ready is emitted.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.settings import settings
from ui.orb_widget import OrbWidget


STARTUP_STYLESHEET = """
QWidget#startupRoot {
    background-color: #04070d;
    color: #dff8ff;
    font-family: 'Segoe UI', sans-serif;
}
QFrame#startupShell {
    background-color: #070c14;
    border: 1px solid #17344d;
    border-radius: 22px;
}
QLabel#brand {
    color: #e8fbff;
    font-size: 38px;
    font-weight: 700;
    letter-spacing: 8px;
}
QLabel#subtitle {
    color: #69dfff;
    font-size: 11px;
    letter-spacing: 3px;
}
QLabel#phase {
    color: #d7f6ff;
    font-size: 15px;
    font-weight: 600;
}
QLabel#detail {
    color: #7296aa;
    font-size: 11px;
}
QLabel#footer {
    color: #4c7d93;
    font-size: 10px;
    letter-spacing: 1px;
}
QProgressBar {
    border: 1px solid #17344d;
    border-radius: 4px;
    background-color: #07111b;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    border-radius: 3px;
    background-color: #00c8ff;
}
QPushButton#errorClose {
    background-color: #25121a;
    border: 1px solid #ff5577;
    color: #ffdbe3;
    border-radius: 7px;
    padding: 8px 18px;
}
QPushButton#errorClose:hover { background-color: #351823; }
"""


class StartupWindow(QWidget):
    """Non-interactive boot surface shown before the MainWindow is revealed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("startupRoot")
        self.setWindowTitle(f"{settings.APP_NAME} — Initialisation")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(780, 480)
        self.setStyleSheet(STARTUP_STYLESHEET)

        self._base_phase = "Initialisation du système"
        self._dot_index = 0
        self._error = False

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)

        shell = QFrame()
        shell.setObjectName("startupShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(34, 28, 34, 26)
        shell_layout.setSpacing(8)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        self.brand = QLabel("AURA")
        self.brand.setObjectName("brand")
        self.subtitle = QLabel("ADAPTIVE UNIFIED REASONING ARCHITECTURE")
        self.subtitle.setObjectName("subtitle")
        title_col.addWidget(self.brand)
        title_col.addWidget(self.subtitle)
        header.addLayout(title_col)
        header.addStretch()
        version = QLabel(f"v{settings.APP_VERSION}\nLOCAL CORE")
        version.setObjectName("detail")
        version.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(version)
        shell_layout.addLayout(header)

        shell_layout.addSpacing(10)
        self.orb = OrbWidget()
        self.orb.setMinimumSize(196, 196)
        self.orb.setMaximumSize(196, 196)
        self.orb.set_state("PROCESSING")
        shell_layout.addWidget(self.orb, alignment=Qt.AlignHCenter)

        self.phase_label = QLabel(self._base_phase)
        self.phase_label.setObjectName("phase")
        self.phase_label.setAlignment(Qt.AlignCenter)
        shell_layout.addWidget(self.phase_label)

        self.detail_label = QLabel("Secure boot // mémoire locale // Resource Guardian")
        self.detail_label.setObjectName("detail")
        self.detail_label.setAlignment(Qt.AlignCenter)
        shell_layout.addWidget(self.detail_label)

        shell_layout.addSpacing(8)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(4)
        self.progress.setTextVisible(False)
        shell_layout.addWidget(self.progress)

        self.progress_text = QLabel("04%")
        self.progress_text.setObjectName("detail")
        self.progress_text.setAlignment(Qt.AlignRight)
        shell_layout.addWidget(self.progress_text)

        self.error_close = QPushButton("Fermer AURA")
        self.error_close.setObjectName("errorClose")
        self.error_close.hide()
        shell_layout.addWidget(self.error_close, alignment=Qt.AlignCenter)

        shell_layout.addStretch()
        footer = QLabel("LOCAL FIRST  //  ZERO TRUST  //  CONTROLLED INTERNET  //  SECURE STARTUP GATE")
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)
        shell_layout.addWidget(footer)

        root.addWidget(shell)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(420)
        self._anim_timer.timeout.connect(self._animate_phase)
        self._anim_timer.start()

    def set_stage(self, percent: int, phase: str, detail: str | None = None) -> None:
        """Update the visible boot stage without allowing user interaction."""
        if self._error:
            return
        percent = max(0, min(100, int(percent)))
        self.progress.setValue(percent)
        self.progress_text.setText(f"{percent:02d}%")
        self._base_phase = str(phase or "Initialisation")
        self.phase_label.setText(self._base_phase)
        if detail is not None:
            self.detail_label.setText(detail)
        if percent >= 100:
            self.orb.set_state("IDLE")
            self.detail_label.setText("Tous les systèmes autorisés sont prêts")

    def show_error(self, message: str) -> None:
        self._error = True
        self._anim_timer.stop()
        self.orb.set_state("ERROR")
        self.phase_label.setText("ÉCHEC DE L'INITIALISATION")
        self.detail_label.setText(message or "Une erreur empêche le démarrage sécurisé d'AURA.")
        self.progress.setValue(100)
        self.progress_text.setText("ERROR")
        self.error_close.show()

    def _animate_phase(self) -> None:
        if self._error or self.progress.value() >= 100:
            return
        self._dot_index = (self._dot_index + 1) % 4
        self.phase_label.setText(self._base_phase + ("." * self._dot_index))

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(
                area.center().x() - self.width() // 2,
                area.center().y() - self.height() // 2,
            )

    def paintEvent(self, event):
        # A restrained technical frame around the future-UI boot surface.
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(0, 200, 255, 42), 1)
        painter.setPen(pen)
        margin = 9
        painter.drawRoundedRect(
            QRectF(
                margin,
                margin,
                self.width() - margin * 2 - 1,
                self.height() - margin * 2 - 1,
            ),
            24,
            24,
        )
