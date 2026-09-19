"""Adaptive holographic result surface for AURA v0.7.0.15.6.5.

This is intentionally Qt-only pseudo-3D: perspective lines, parallax-like glow,
scan motion and layered translucent cards.  It avoids a heavyweight 3D engine so
XTTS/Ollama keep GPU priority.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
logger = logging.getLogger("aura.ui.results")

from ui.text_rendering import normalize_markdown_text

from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class _HoloBackdrop(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        timer = QTimer(self)
        timer.setInterval(45)
        timer.timeout.connect(self._tick)
        timer.start()
        self._timer = timer

    def _tick(self):
        self._phase = (self._phase + 2) % 240
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        # Faint perspective grid: illusion of depth, very cheap to render.
        horizon = int(rect.height() * 0.34)
        painter.setPen(QPen(QColor(36, 174, 235, 28), 1))
        center = rect.center().x()
        for x in range(-rect.width(), rect.width() * 2, max(44, rect.width() // 18)):
            painter.drawLine(center, horizon, x, rect.bottom())
        for i in range(8):
            y = horizon + int(((i + 1) / 8) ** 1.65 * max(1, rect.height() - horizon))
            painter.drawLine(rect.left(), y, rect.right(), y)

        scan_y = (self._phase / 240.0) * max(1, rect.height())
        glow = QLinearGradient(0, scan_y - 20, 0, scan_y + 20)
        glow.setColorAt(0.0, QColor(67, 221, 255, 0))
        glow.setColorAt(0.5, QColor(67, 221, 255, 42))
        glow.setColorAt(1.0, QColor(160, 96, 255, 0))
        painter.fillRect(0, int(scan_y - 20), rect.width(), 40, glow)


class HolographicResultsPanel(QFrame):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("holographicResultsPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
        QFrame#holographicResultsPanel {
            background-color: #020916;
            border: 1px solid rgba(81, 214, 255, 205);
            border-radius: 18px;
        }
        QLabel#resultKicker { color:#66ddff; font-size:9px; font-weight:700; letter-spacing:2px; }
        QLabel#resultTitle { color:#eefbff; font-size:18px; font-weight:650; }
        QLabel#resultSubtitle { color:#9d83d8; font-size:10px; }
        QLabel#resultSources { color:#698ca5; font-size:9px; }
        QTextBrowser#resultBody {
            background-color: #041022;
            border: 1px solid rgba(73, 83, 132, 155);
            border-radius: 12px;
            color:#dceef8;
            padding:13px;
            font-family:'Segoe UI Variable Text','Segoe UI','Segoe UI Emoji','Segoe UI Symbol';
            font-size:12px;
            selection-background-color:#244c68;
        }
        QPushButton#resultAction {
            background-color:rgba(7,31,56,230); border:1px solid #1c638e; border-radius:10px;
            color:#74ddff; padding:7px 13px; font-size:9px; font-weight:600;
        }
        QPushButton#resultAction:hover { border-color:#ad86ff; color:#e3d2ff; }
        QPushButton#resultClose {
            background:transparent; border:1px solid rgba(100,156,190,90); border-radius:13px;
            color:#a9c7d8; font-size:16px;
        }
        QPushButton#resultClose:hover { background:#34152d; border-color:#8e4368; color:white; }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(17, 132, 205, 105))
        self.setGraphicsEffect(shadow)

        self._backdrop = _HoloBackdrop(self)
        self._backdrop.lower()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(9)

        top = QHBoxLayout()
        titles = QVBoxLayout()
        kicker = QLabel("◈  AURA VISUAL DATA SURFACE")
        kicker.setObjectName("resultKicker")
        self.title_label = QLabel("RÉSULTATS")
        self.title_label.setObjectName("resultTitle")
        self.subtitle_label = QLabel("Visual Result Handoff")
        self.subtitle_label.setObjectName("resultSubtitle")
        titles.addWidget(kicker)
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle_label)
        top.addLayout(titles, 1)
        close = QPushButton("×")
        close.setObjectName("resultClose")
        close.setFixedSize(28, 28)
        close.clicked.connect(self.hide_animated)
        top.addWidget(close, 0, Qt.AlignTop)
        layout.addLayout(top)

        self.body = QTextBrowser()
        self.body.setObjectName("resultBody")
        self.body.setOpenExternalLinks(True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        layout.addWidget(self.body, 1)

        self.sources_label = QLabel("")
        self.sources_label.setObjectName("resultSources")
        self.sources_label.setWordWrap(True)
        layout.addWidget(self.sources_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        copy_btn = QPushButton("COPIER")
        copy_btn.setObjectName("resultAction")
        copy_btn.clicked.connect(self._copy)
        actions.addWidget(copy_btn)
        close_btn = QPushButton("FERMER")
        close_btn.setObjectName("resultAction")
        close_btn.clicked.connect(self.hide_animated)
        actions.addWidget(close_btn)
        layout.addLayout(actions)

        self._opacity = QGraphicsOpacityEffect()
        # Keep drop shadow while animating by applying opacity to the body tree
        # is not possible with a second frame effect. Geometry animation carries
        # most of the entrance; opacity is applied only during the transition.
        self._animation = None
        self._target_geometry = QRect()
        self.hide()

    def resizeEvent(self, event):
        self._backdrop.setGeometry(self.rect())
        super().resizeEvent(event)

    def _copy(self):
        QApplication.clipboard().setText(self.body.toPlainText())

    def set_result(self, *, title: str, subtitle: str, text: str, sources=()):
        self.title_label.setText(title or "RÉSULTATS")
        self.subtitle_label.setText(subtitle or "AURA · Visual Result Handoff")
        clean_text = normalize_markdown_text(text)
        try:
            # Gemini/Groq naturally produce Markdown. Rendering it as plain text
            # exposed **, ###, pipes and other markup as distracting characters.
            # QTextDocument's native Markdown renderer keeps the response readable
            # without executing scripts or arbitrary web content.
            self.body.setMarkdown(clean_text)
        except Exception:
            self.body.setPlainText(clean_text)
        hosts = []
        for source in sources or ():
            name = str(getattr(source, "name", "") or "").strip()
            host = str(getattr(source, "host", "") or "").strip()
            label = name if name and name != host else host
            if label and label not in hosts:
                hosts.append(label)
        self.sources_label.setText("SOURCES  ·  " + "   •   ".join(hosts[:6]) if hosts else "AURA · DONNÉES LOCALES")

    def show_animated(self, target: QRect):
        """Show first, animate second: animation can never suppress the result."""
        self._target_geometry = QRect(target)
        # Commit the final geometry before any optional animation. This avoids a
        # Qt/Windows stacking edge case with a QOpenGLWidget sibling where an
        # exception in QPropertyAnimation previously aborted the whole LLM slot.
        self.setGeometry(target)
        self.show()
        self.raise_()
        try:
            start = QRect(target)
            start.adjust(18, 24, -18, -8)
            self.setGeometry(start)
            anim = QPropertyAnimation(self, b"geometry", self)
            anim.setDuration(220)
            anim.setStartValue(start)
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self._animation = anim
            anim.start()
        except Exception:
            logger.exception("Result panel entrance animation disabled")
            self.setGeometry(target)
        return True

    def hide_animated(self):
        if not self.isVisible():
            return
        start = self.geometry()
        end = QRect(start)
        end.adjust(24, 22, -24, -8)
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(190)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.finished.connect(self._finish_hide)
        self._animation = anim
        anim.start()

    def _finish_hide(self):
        self.hide()
        self.closed.emit()
