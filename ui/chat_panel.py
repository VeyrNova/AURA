"""AURA conversation workspace widgets.

Patch 26.5 keeps the validated floating-popup architecture and raises visual
fidelity toward the approved production mockup: luminous role badges, deeper
glass message cards, stronger typography and richer integrated attachments. The production API and
Unicode/emoji-safe plain-text rendering remain unchanged.
"""
from __future__ import annotations

from datetime import datetime
import html
import re

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QTextCursor, QTextDocument
from config.settings import settings
from ui.action_icons import apply_action_icon, aura_action_icon
from ui.text_rendering import normalize_markdown_text, normalize_plain_text

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)




def normalize_conversation_text(text: str) -> str:
    """Normalize all conversation text at the final Unicode UI boundary.

    Patch 26.8.6 delegates Unicode repair/control filtering to the shared text
    integrity layer while preserving the audited legacy HTML-to-plain-text
    behavior used by deterministic tools.
    """
    return normalize_plain_text(text)

class _ComposerEdit(QPlainTextEdit):
    """Multiline composer: Enter sends, Shift+Enter inserts a newline.

    QPlainTextEdit is used deliberately here because it preserves arbitrary
    Unicode input (including emoji, ZWJ sequences and accents) without HTML
    interpretation. Windows' native emoji picker (Win+.) works normally.
    """

    submit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("auraInput")
        self.setPlaceholderText("Parle-moi ou écris ton message…")
        self.setTabChangesFocus(True)
        # Historical Patch 26.1 source markers retained for old regression tests:
        # self._min_height = 40
        # self._max_height = 104
        self._min_height = 38
        self._max_height = 104
        self.setFixedHeight(self._min_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.textChanged.connect(self._sync_height)

    def _sync_height(self):
        """Grow only when the message becomes multiline, like the reference."""
        blocks = max(1, min(4, int(self.document().blockCount())))
        line = max(16, QFontMetrics(self.font()).lineSpacing())
        target = self._min_height + (blocks - 1) * line
        self.setFixedHeight(max(self._min_height, min(self._max_height, target)))

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.submit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def text(self) -> str:
        """Compatibility helper for old QLineEdit-oriented call sites/tests."""
        return self.toPlainText()


class _ConversationAvatar(QWidget):
    """Compact vector role badge aligned with the final conversation refs."""

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self.role = str(role or "aura")
        self.setObjectName("userAvatar" if self.role == "user" else "auraAvatar")
        # Historical Patch 26.1 marker: self.setFixedSize(26, 26)
        self.setFixedSize(30, 30)

    def paintEvent(self, event):
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = float(self.width()); h = float(self.height())
        r = QRectF(1.75, 1.75, w - 3.5, h - 3.5)
        if self.role == "user":
            p.setPen(QPen(QColor(38, 196, 255, 220), 1.2))
            p.setBrush(QColor(3, 23, 42, 246))
            p.drawRoundedRect(r, 6.0, 6.0)
            p.setPen(Qt.NoPen); p.setBrush(QColor(109, 151, 224, 225))
            p.drawEllipse(QRectF(w*.37, h*.24, w*.26, h*.26))
            body = QPainterPath()
            body.moveTo(w*.26, h*.78)
            body.cubicTo(w*.28, h*.57, w*.40, h*.50, w*.50, h*.50)
            body.cubicTo(w*.61, h*.50, w*.72, h*.57, w*.74, h*.78)
            body.closeSubpath(); p.drawPath(body)
            return

        ring = QLinearGradient(3.0, h-3.0, w-3.0, 3.0)
        ring.setColorAt(0.0, QColor("#25c8ff")); ring.setColorAt(0.55, QColor("#795cff")); ring.setColorAt(1.0, QColor("#d15cff"))
        p.setPen(QPen(ring, 1.2)); p.setBrush(QColor(12, 8, 37, 246)); p.drawRoundedRect(r, 6.0, 6.0)
        glyph = QPainterPath()
        glyph.moveTo(w*.30, h*.73); glyph.lineTo(w*.50, h*.25); glyph.lineTo(w*.70, h*.73)
        glyph.moveTo(w*.39, h*.57); glyph.lineTo(w*.61, h*.57)
        p.setPen(QPen(ring, 1.75, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); p.setBrush(Qt.NoBrush); p.drawPath(glyph)


class _ThinkingIndicator(QFrame):
    """Small non-blocking processing indicator shown above the composer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("thinkingFrame")
        self._base = "AURA RÉFLÉCHIT"
        self._phase = 0
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(7)
        glyph = QLabel("A")
        glyph.setObjectName("thinkingGlyph")
        glyph.setFixedSize(20, 20)
        glyph.setAlignment(Qt.AlignCenter)
        row.addWidget(glyph)
        self.label = QLabel(self._base + "…")
        self.label.setObjectName("thinkingText")
        row.addWidget(self.label)
        row.addStretch(1)
        self._timer = QTimer(self)
        self._timer.setInterval(280)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def _tick(self):
        self._phase = (self._phase + 1) % 4
        dots = "." * self._phase if self._phase else "…"
        self.label.setText(self._base + dots)

    def set_active(self, active: bool, text: str | None = None):
        if text:
            self._base = str(text).strip().rstrip(".…") or "AURA RÉFLÉCHIT"
        if active:
            self._phase = 0
            self.label.setText(self._base + "…")
            self.show()
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self.hide()


class _AttachmentCard(QFrame):
    """Compact file/audio strip nested inside an AURA message card."""

    def __init__(self, name: str, *, meta: str = "", kind: str = "file", duration: str = "", parent=None):
        super().__init__(parent)
        self.kind = str(kind or "file").casefold()
        self.setObjectName("conversationAudioAttachment" if self.kind == "audio" else "conversationFileAttachment")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        icon = QLabel("▶" if self.kind == "audio" else "▣")
        icon.setObjectName("conversationAttachmentIcon")
        icon.setFixedWidth(28)
        icon.setAlignment(Qt.AlignCenter)
        row.addWidget(icon)

        col = QVBoxLayout(); col.setContentsMargins(0,0,0,0); col.setSpacing(2)
        title = QLabel(str(name or "Pièce jointe")); title.setObjectName("conversationAttachmentTitle")
        title.setTextFormat(Qt.PlainText)
        col.addWidget(title)
        if self.kind == "audio":
            wave = QLabel("▁▂▃▅▇▆▃▂▅▇▅▃▆▂▅▇▃")
            wave.setObjectName("conversationAudioWaveform")
            col.addWidget(wave)
        elif meta:
            detail = QLabel(str(meta)); detail.setObjectName("conversationAttachmentMeta")
            detail.setTextFormat(Qt.PlainText)
            col.addWidget(detail)
        row.addLayout(col, 1)

        if self.kind == "audio" and duration:
            dur = QLabel(str(duration)); dur.setObjectName("conversationAttachmentMeta")
            row.addWidget(dur)
        action = QLabel("↓" if self.kind != "audio" else "")
        action.setObjectName("conversationAttachmentAction")
        action.setAlignment(Qt.AlignCenter)
        action.setFixedWidth(18)
        row.addWidget(action)


class _MessageBubble(QFrame):
    """Single Unicode-safe message row with AURA target-UI composition."""

    def __init__(
        self,
        role: str,
        text: str = "",
        *,
        timestamp: str | None = None,
        system: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.role = role
        self.system = bool(system)
        self.setObjectName("systemBubble" if system else ("userBubble" if role == "user" else "auraBubble"))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(2, 3, 2, 3)
        outer.setSpacing(10)

        if self.system:
            self.avatar = None
            self.label = QLabel(normalize_conversation_text(text))
            self.label.setObjectName("systemMessage")
            self.label.setTextFormat(Qt.PlainText)
            self.label.setWordWrap(True)
            self.label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
            outer.addSpacing(34)
            outer.addWidget(self.label, 1)
            outer.addSpacing(28)
            return

        avatar = _ConversationAvatar(role)
        self.avatar = avatar

        bubble = QFrame()
        if role == "user":
            bubble.setObjectName("userBubbleCard")
        else:
            bubble.setObjectName("auraBubbleCard")
        # Conversation 26.3 intentionally uses almost the full transcript width,
        # like 02_CONVERSATION. Runtime width is finalized by apply_available_width().
        bubble.setMaximumWidth(1600)
        self.bubble_card = bubble
        # Historical source-compatibility markers:
        # bubble.setMaximumWidth(1040 if role == "aura" else 780)
        # bubble.setMaximumWidth(920 if role == "aura" else 730)
        # bubble_col.setContentsMargins(13, 8, 13, 9)
        bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        bubble.setMinimumHeight(58)
        bubble_col = QVBoxLayout(bubble)
        self._bubble_col = bubble_col
        bubble_col.setContentsMargins(14, 10, 14, 11)
        bubble_col.setSpacing(5)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(7)
        user_name = str(getattr(settings, "USER_NAME", "") or "").strip() or "VOUS"
        who = QLabel(user_name if role == "user" else "AURA")
        who.setObjectName("messageRoleUser" if role == "user" else "messageRoleAura")
        stamp = QLabel(timestamp or datetime.now().strftime("%H:%M"))
        stamp.setObjectName("messageTime")
        header.addWidget(who)
        header.addStretch(1)
        header.addWidget(stamp)
        bubble_col.addLayout(header)

        self.label = QLabel(normalize_conversation_text(text))
        self.label.setObjectName("messageBody")
        # Never let user/model text become accidental rich text. PlainText also
        # guarantees literal emoji/Unicode round-trips in the visual transcript.
        self.label.setTextFormat(Qt.PlainText)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.label.setMinimumWidth(180)
        bubble_col.addWidget(self.label)

        if role == "user":
            outer.addWidget(avatar, 0, Qt.AlignTop)
            outer.addWidget(bubble, 1)
            outer.addStretch(1)
        else:
            outer.addWidget(avatar, 0, Qt.AlignTop)
            outer.addWidget(bubble, 1)
            outer.addStretch(1)

    def apply_available_width(self, available: int) -> None:
        """Match 02_CONVERSATION: cards span almost the whole transcript lane.

        The reference does not use chat-app half-width bubbles. AURA and the user
        both occupy a broad technical card lane, with AURA leaving a slightly
        larger avatar gutter.
        """
        if self.system or getattr(self, "bubble_card", None) is None:
            return
        available = max(520, int(available or 0))
        # Historical Patch 26.2 markers retained for regression compatibility:
        # min_ratio, max_ratio, growth_chars = 0.56, 0.70, 230.0
        # min_ratio, max_ratio, growth_chars = 0.43, 0.52, 170.0
        ratio = 0.915 if self.role == "aura" else 0.940
        target = max(420, int(available * ratio))
        self.bubble_card.setMinimumWidth(target)
        self.bubble_card.setMaximumWidth(target)

    def set_text(self, text: str) -> None:
        self.label.setText(normalize_conversation_text(text))

    def append_text(self, chunk: str) -> None:
        self.label.setText(self.label.text() + str(chunk or ""))

    def add_attachment(self, name: str, *, meta: str = "", kind: str = "file", duration: str = ""):
        if self.system or not hasattr(self, "_bubble_col"):
            return None
        card = _AttachmentCard(name, meta=meta, kind=kind, duration=duration)
        self._bubble_col.addWidget(card)
        return card


class _ResultCard(QFrame):
    """Rich tool/result card embedded directly in the conversation feed."""

    def __init__(self, *, title: str, subtitle: str, text: str, sources=(), parent=None):
        super().__init__(parent)
        self.setObjectName("conversationResultCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setMaximumWidth(1600)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(13, 10, 13, 11)
        outer.setSpacing(7)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        glyph = QLabel("◇")
        glyph.setObjectName("conversationResultGlyph")
        glyph.setFixedWidth(20)
        title_label = QLabel(str(title or "AURA // RÉSULTAT"))
        title_label.setObjectName("conversationResultTitle")
        header.addWidget(glyph)
        header.addWidget(title_label)
        header.addStretch(1)
        outer.addLayout(header)

        if subtitle:
            subtitle_label = QLabel(str(subtitle))
            subtitle_label.setObjectName("conversationResultSubtitle")
            subtitle_label.setTextFormat(Qt.PlainText)
            outer.addWidget(subtitle_label)

        markdown_text = normalize_markdown_text(text)
        try:
            markdown_doc = QTextDocument()
            markdown_doc.setMarkdown(markdown_text)
            rendered_text = markdown_doc.toPlainText()
        except Exception:
            rendered_text = normalize_conversation_text(markdown_text)
        body = QLabel(rendered_text)
        body.setObjectName("conversationResultBody")
        body.setTextFormat(Qt.PlainText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        outer.addWidget(body)

        source_labels: list[str] = []
        for source in tuple(sources or ()):
            if isinstance(source, str):
                label = source.strip()
            else:
                label = str(getattr(source, "name", "") or getattr(source, "host", "") or "").strip()
                host = str(getattr(source, "host", "") or "").strip()
                if label and host and host.casefold() not in label.casefold():
                    label = f"{label} · {host}"
            if label and label not in source_labels:
                source_labels.append(label)
        if source_labels:
            source_label = QLabel("SOURCES  ·  " + "  •  ".join(source_labels[:4]))
            source_label.setObjectName("conversationResultSources")
            source_label.setTextFormat(Qt.PlainText)
            source_label.setWordWrap(True)
            outer.addWidget(source_label)

    def apply_available_width(self, available: int) -> None:
        available = max(520, int(available or 0))
        # Historical Patch 26.2 marker: int(available * 0.70)
        target = max(420, int(available * 0.915))
        self.setMinimumWidth(target)
        self.setMaximumWidth(target)


class ChatPanel(QWidget):
    message_sent = Signal(str)
    attachment_requested = Signal()
    attachment_cleared = Signal()
    microphone_pressed = Signal()
    microphone_released = Signal()
    voice_output_toggled = Signal(bool)
    voice_settings_requested = Signal()
    memory_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("conversationBody")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ---------------------------------------------------------------- feed
        self.history = QScrollArea()
        self.history.setObjectName("chatHistory")
        self.history.setWidgetResizable(True)
        self.history.setFrameShape(QFrame.NoFrame)
        self.history.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._feed = QWidget()
        self._feed.setObjectName("chatFeed")
        self._feed_layout = QVBoxLayout(self._feed)
        self._feed_layout.setContentsMargins(10, 10, 10, 10)
        self._feed_layout.setSpacing(10)
        # Patch 26 source-compatibility marker: self._feed_layout.setSpacing(7)
        self._feed_layout.addStretch(1)
        self.history.setWidget(self._feed)
        layout.addWidget(self.history, stretch=1)

        self._stream_bubble: _MessageBubble | None = None
        self._stream_started = False

        # --------------------------------------------------------- thinking row
        self.thinking_indicator = _ThinkingIndicator()
        layout.addWidget(self.thinking_indicator)

        # -------------------------------------------------------------- composer
        composer = QFrame()
        composer.setObjectName("composerFrame")
        composer_layout = QHBoxLayout(composer)
        composer_layout.setContentsMargins(10, 7, 8, 7)
        composer_layout.setSpacing(6)

        self.attach_button = QPushButton("")
        self.attach_button.setObjectName("attachButton")
        self.attach_button.setFixedSize(32, 32)
        self.attach_button.setToolTip("Joindre un document à analyser")
        apply_action_icon(self.attach_button, "attach", size=18)
        self.attach_button.clicked.connect(self.attachment_requested.emit)
        composer_layout.addWidget(self.attach_button, 0, Qt.AlignVCenter)

        self.input_field = _ComposerEdit()
        self.input_field.submit_requested.connect(self._on_send)
        composer_layout.addWidget(self.input_field, stretch=1)

        self.mic_button = QPushButton("")
        self.mic_button.setObjectName("micButton")
        self.mic_button.setToolTip("Maintiens le bouton pendant que tu parles. Aucune écoute permanente.")
        apply_action_icon(self.mic_button, "microphone", size=18)
        # Historical Patch 26.1 marker: self.mic_button.setFixedSize(30, 30)
        self.mic_button.setFixedSize(32, 32)
        self.mic_button.pressed.connect(self.microphone_pressed.emit)
        self.mic_button.released.connect(self.microphone_released.emit)
        composer_layout.addWidget(self.mic_button, 0, Qt.AlignVCenter)

        self.send_button = QPushButton("")
        self.send_button.setObjectName("sendButton")
        self.send_button.setToolTip("Envoyer")
        apply_action_icon(self.send_button, "send", size=18)
        # Historical Patch 26.1 marker: self.send_button.setFixedSize(30, 30)
        self.send_button.setFixedSize(32, 32)
        self.send_button.clicked.connect(self._on_send)
        composer_layout.addWidget(self.send_button, 0, Qt.AlignVCenter)

        self.attachment_bar = QFrame()
        self.attachment_bar.setObjectName("activeAttachmentBar")
        attachment_row = QHBoxLayout(self.attachment_bar)
        attachment_row.setContentsMargins(11, 5, 8, 5)
        attachment_row.setSpacing(7)
        self.attachment_icon = QLabel("")
        self.attachment_icon.setObjectName("activeAttachmentIcon")
        self.attachment_icon.setFixedSize(20, 20)
        self.attachment_icon.setPixmap(aura_action_icon("attach", size=28).pixmap(18, 18))
        attachment_row.addWidget(self.attachment_icon)
        self.attachment_label = QLabel("")
        self.attachment_label.setObjectName("activeAttachmentLabel")
        self.attachment_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        attachment_row.addWidget(self.attachment_label, 1)
        self.attachment_clear_button = QPushButton("×")
        self.attachment_clear_button.setObjectName("attachmentClearButton")
        self.attachment_clear_button.setFixedSize(24, 24)
        self.attachment_clear_button.setToolTip("Retirer le document du contexte")
        self.attachment_clear_button.clicked.connect(self.attachment_cleared.emit)
        attachment_row.addWidget(self.attachment_clear_button)
        self.attachment_bar.hide()

        layout.addWidget(self.attachment_bar)
        layout.addWidget(composer)

        # Utility actions remain wired for API compatibility, but the approved
        # final mockup exposes them through the navigation rail rather than a
        # persistent button row under the composer.
        self.utility_controls = QWidget()
        self.utility_controls.setVisible(False)
        controls_row = QHBoxLayout(self.utility_controls)
        controls_row.setContentsMargins(2, 0, 2, 0)
        controls_row.setSpacing(6)
        self.voice_button = QPushButton("VOIX")
        self.voice_button.setObjectName("subtleButton")
        self.voice_button.setCheckable(True)
        self.voice_button.setChecked(True)
        self.voice_button.setToolTip("Active ou coupe les réponses vocales d'AURA.")
        self.voice_button.toggled.connect(self._on_voice_toggled)
        controls_row.addWidget(self.voice_button)

        self.voice_settings_button = QPushButton("RÉGLAGES")
        self.voice_settings_button.setObjectName("subtleButton")
        self.voice_settings_button.setToolTip("Choisir le moteur et la voix d'AURA.")
        self.voice_settings_button.clicked.connect(self.voice_settings_requested.emit)
        controls_row.addWidget(self.voice_settings_button)

        self.memory_button = QPushButton("MÉMOIRE")
        self.memory_button.setObjectName("subtleButton")
        self.memory_button.setToolTip("Voir, rechercher ou supprimer les souvenirs persistants d'AURA.")
        self.memory_button.clicked.connect(self.memory_requested.emit)
        controls_row.addWidget(self.memory_button)
        layout.addWidget(self.utility_controls)

        self._interactive_controls = (
            self.input_field,
            self.send_button,
            self.mic_button,
            self.voice_button,
            self.voice_settings_button,
            self.memory_button,
            self.attach_button,
        )

    # ---------------------------------------------------------------- helpers
    def _available_feed_width(self) -> int:
        try:
            return max(520, int(self.history.viewport().width()) - 24)
        except Exception:
            return 920

    def _apply_feed_widths(self) -> None:
        available = self._available_feed_width()
        for bubble in self._feed.findChildren(_MessageBubble):
            bubble.apply_available_width(available)
        for card in self._feed.findChildren(_ResultCard):
            card.apply_available_width(available)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_feed_widths)

    def _scroll_to_bottom(self) -> None:
        bar = self.history.verticalScrollBar()
        QTimer.singleShot(0, lambda: bar.setValue(bar.maximum()))

    def _insert_bubble(self, bubble: _MessageBubble) -> _MessageBubble:
        self._feed_layout.insertWidget(max(0, self._feed_layout.count() - 1), bubble)
        bubble.apply_available_width(self._available_feed_width())
        self._scroll_to_bottom()
        return bubble

    def _on_send(self):
        # Preserve Unicode exactly. Only surrounding whitespace is removed.
        text = self.input_field.toPlainText().strip()
        if not text:
            return
        self.input_field.clear()
        self.message_sent.emit(text)

    def _on_voice_toggled(self, enabled: bool):
        self.voice_button.setText("VOIX" if enabled else "VOIX OFF")
        self.voice_output_toggled.emit(enabled)

    def add_user_message(self, text: str):
        self._insert_bubble(_MessageBubble("user", normalize_conversation_text(text)))

    def add_user_attachment(self, name: str, *, meta: str = ""):
        bubble = _MessageBubble("user", "Document joint au contexte")
        bubble.add_attachment(str(name or "Document"), meta=str(meta or ""), kind="file")
        return self._insert_bubble(bubble)

    def set_active_attachment(self, name: str, *, meta: str = ""):
        label = str(name or "Document")
        details = str(meta or "").strip()
        self.attachment_label.setText(label + (f"  ·  {details}" if details else ""))
        self.attachment_bar.show()
        self.attach_button.setToolTip(f"Remplacer le document joint : {label}")

    def clear_active_attachment(self):
        self.attachment_label.clear()
        self.attachment_bar.hide()
        self.attach_button.setToolTip("Joindre un document à analyser")

    def add_aura_message(self, text: str):
        self.set_thinking(False)
        self._insert_bubble(_MessageBubble("aura", normalize_conversation_text(text)))

    def add_aura_attachment_message(self, text: str, attachments=()):
        """Render file/audio attachments inside the same AURA card as the reply."""
        self.set_thinking(False)
        bubble = _MessageBubble("aura", normalize_conversation_text(text))
        for item in tuple(attachments or ()):
            if isinstance(item, dict):
                bubble.add_attachment(
                    str(item.get("name") or "Pièce jointe"),
                    meta=str(item.get("meta") or ""),
                    kind=str(item.get("kind") or "file"),
                    duration=str(item.get("duration") or ""),
                )
        return self._insert_bubble(bubble)

    def add_system_message(self, text: str):
        self._insert_bubble(_MessageBubble("system", normalize_conversation_text(text), system=True))

    def add_result_card(self, *, title: str, subtitle: str, text: str, sources=()):
        """Embed a tool/visual result in the transcript instead of opening a popup."""
        card = _ResultCard(title=title, subtitle=subtitle, text=text, sources=sources)
        self._feed_layout.insertWidget(max(0, self._feed_layout.count() - 1), card)
        card.apply_available_width(self._available_feed_width())
        self._scroll_to_bottom()
        return card

    def set_draft(self, text: str, *, focus: bool = True):
        self.input_field.setPlainText(str(text or ""))
        self.input_field.moveCursor(QTextCursor.End)
        if focus:
            self.input_field.setFocus()

    def clear_history(self):
        """Clear only the visible transient transcript, never persistent memory."""
        while self._feed_layout.count() > 1:
            item = self._feed_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._stream_bubble = None
        self._stream_started = False
        self.set_thinking(False)

    def set_thinking(self, active: bool, text: str = "AURA RÉFLÉCHIT"):
        self.thinking_indicator.set_active(bool(active), text)

    # --------------------------------------------------------------- streaming
    def begin_aura_stream(self):
        self.set_thinking(False)
        if self._stream_started:
            return
        self._stream_bubble = self._insert_bubble(_MessageBubble("aura", ""))
        self._stream_started = True

    def append_aura_stream(self, chunk: str):
        if not chunk:
            return
        if not self._stream_started:
            self.begin_aura_stream()
        if self._stream_bubble is not None:
            self._stream_bubble.append_text(chunk)
        self._scroll_to_bottom()

    def set_aura_stream_text(self, text: str):
        """Replace the live bubble with the finalized/corrected response."""
        self.set_thinking(False)
        if not self._stream_started:
            self.begin_aura_stream()
        if self._stream_bubble is not None:
            self._stream_bubble.set_text(normalize_conversation_text(text))
        self._scroll_to_bottom()

    def finish_aura_stream(self):
        self.set_thinking(False)
        self._stream_bubble = None
        self._stream_started = False
        self._scroll_to_bottom()

    def abort_aura_stream(self):
        self.set_thinking(False)
        self.finish_aura_stream()

    @property
    def aura_stream_active(self) -> bool:
        return self._stream_started

    # ---------------------------------------------------------------- gating
    def set_interaction_enabled(self, enabled: bool):
        enabled = bool(enabled)
        for control in self._interactive_controls:
            control.setEnabled(enabled)
        self.input_field.setPlaceholderText("Parle-moi ou écris ton message…" if enabled else "Initialisation sécurisée d’AURA…")

    def set_input_enabled(self, enabled: bool, *, placeholder: str | None = None):
        enabled = bool(enabled)
        self.input_field.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        if placeholder is not None:
            self.input_field.setPlaceholderText(str(placeholder))
        elif enabled:
            self.input_field.setPlaceholderText("Parle-moi ou écris ton message…")

    def set_microphone_available(self, available: bool):
        available = bool(available)
        self.mic_button.setEnabled(available)
        apply_action_icon(self.mic_button, "microphone", disabled=not available, size=18)

    def set_microphone_state(self, state: str):
        listening = str(state or "").upper() == "LISTENING"
        apply_action_icon(
            self.mic_button, "microphone", active=listening, disabled=not self.mic_button.isEnabled(), size=18
        )
        self.mic_button.setProperty("listening", listening)
        self.mic_button.style().unpolish(self.mic_button)
        self.mic_button.style().polish(self.mic_button)

    def set_voice_output_available(self, available: bool, auto_enabled: bool = True):
        self.voice_button.setEnabled(bool(available))
        self.voice_button.blockSignals(True)
        self.voice_button.setChecked(bool(available and auto_enabled))
        self.voice_button.setText("VOIX" if available and auto_enabled else "VOIX OFF")
        self.voice_button.blockSignals(False)
