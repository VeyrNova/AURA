"""Floating Conversation workspace for AURA.

Patch 26.4 turns Conversation into a true child popup: the main AURA shell
remains visible behind it, while the focused chat workspace floats above a
subtle dim layer.  The popup deliberately stays smaller than the parent window
and never replaces/maximizes the primary AURA interface.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from config.settings import settings
from ui.chat_panel import ChatPanel
from ui.final_modules import ConversationContextPanel


class _PopupTitleBar(QFrame):
    """Draggable title bar for the frameless child popup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("conversationPopupTitleBar")
        self.setFixedHeight(58)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            window = self.window()
            handle = window.windowHandle() if window is not None else None
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)


class ConversationPopup(QDialog):
    """Non-modal, parent-owned popup matching the approved Conversation render."""

    hidden = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("conversationPopupWindow")
        self.setWindowTitle("AURA • CONVERSATION")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(False)
        self._expanded = False
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(0)

        self.surface = QFrame()
        self.surface.setObjectName("conversationPopupSurface")
        self.surface.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        shadow = QGraphicsDropShadowEffect(self.surface)
        shadow.setBlurRadius(52.0)
        shadow.setOffset(0.0, 8.0)
        shadow.setColor(QColor(84, 48, 196, 112))
        self.surface.setGraphicsEffect(shadow)
        self._surface_shadow = shadow
        root_layout.addWidget(self.surface)

        surface_layout = QVBoxLayout(self.surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        titlebar = _PopupTitleBar()
        title_layout = QHBoxLayout(titlebar)
        title_layout.setContentsMargins(20, 0, 14, 0)
        title_layout.setSpacing(9)

        logo = QLabel("A")
        logo.setObjectName("conversationPopupLogo")
        logo.setFixedSize(32, 32)
        logo.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(logo)

        title = QLabel("AURA • CONVERSATION")
        title.setObjectName("conversationPopupTitle")
        title_layout.addWidget(title)
        title_layout.addStretch(1)

        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("conversationPopupWindowButton")
        self.collapse_button.setText("—")
        self.collapse_button.setToolTip("Masquer la conversation")
        self.collapse_button.setFixedSize(30, 28)
        self.collapse_button.clicked.connect(self.hide)
        title_layout.addWidget(self.collapse_button)

        self.expand_button = QToolButton()
        self.expand_button.setObjectName("conversationPopupWindowButton")
        self.expand_button.setText("□")
        self.expand_button.setToolTip("Agrandir la popup")
        self.expand_button.setFixedSize(30, 28)
        self.expand_button.clicked.connect(self.toggle_expanded)
        title_layout.addWidget(self.expand_button)

        self.close_button = QToolButton()
        self.close_button.setObjectName("conversationPopupCloseButton")
        self.close_button.setText("×")
        self.close_button.setToolTip("Fermer le mode conversation")
        self.close_button.setFixedSize(30, 28)
        self.close_button.clicked.connect(self.hide)
        title_layout.addWidget(self.close_button)
        surface_layout.addWidget(titlebar)

        body = QWidget()
        body.setObjectName("conversationPopupBody")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 18, 18, 18)
        body_layout.setSpacing(18)

        self.chat_panel = ChatPanel()
        body_layout.addWidget(self.chat_panel, 72)

        self.context_panel = ConversationContextPanel()
        # Historical Patch 25/26 marker: self.context_panel.setMinimumWidth(270)
        self.context_panel.setMinimumWidth(292)
        self.context_panel.setMaximumWidth(365)
        self.context_panel.set_context(memory="Active" if settings.MEMORY_ENABLED else "Désactivée")
        body_layout.addWidget(self.context_panel, 28)
        surface_layout.addWidget(body, 1)

    def _target_size(self) -> tuple[int, int]:
        parent = self.parentWidget()
        if parent is None:
            return (1080, 800)
        pw = max(1, int(parent.width()))
        ph = max(1, int(parent.height()))
        if self._expanded:
            width = min(1450, max(980, int(pw * 0.84)))
            height = min(920, max(720, int(ph * 0.90)))
        else:
            width = min(1220, max(900, int(pw * 0.64)))
            height = min(860, max(680, int(ph * 0.82)))
        # Always remain visibly smaller than the parent window.
        width = min(width, max(760, pw - 120))
        height = min(height, max(620, ph - 90))
        return width, height

    def sync_to_parent(self, *, resize: bool = True) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        if resize:
            width, height = self._target_size()
            self.resize(width, height)
        origin = parent.mapToGlobal(QPoint(0, 0))
        x = origin.x() + max(0, (parent.width() - self.width()) // 2)
        y = origin.y() + max(0, (parent.height() - self.height()) // 2)
        self.move(x, y)

    def show_centered(self, *, focus_input: bool = True) -> None:
        self.sync_to_parent(resize=True)
        self.show()
        self.raise_()
        self.activateWindow()
        if focus_input:
            self.chat_panel.input_field.setFocus()

    def toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self.expand_button.setText("❐" if self._expanded else "□")
        self.sync_to_parent(resize=True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.hidden.emit()

    def reject(self) -> None:
        # Escape closes only the popup; the main AURA window remains alive.
        self.hide()
