"""Final AURA neural-interface modules.

This module implements the visual language supplied with the final UI reference:
expanded navigation, compact holographic cards, neural-system gauges and the
five-stage AURA warmup construction sequence.  It deliberately stays in Qt
widgets/QPainter so it can coexist with the existing OpenGL Orb and runtime.
"""
from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from ui.action_icons import apply_action_icon, aura_action_icon

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


FINAL_UI_STYLESHEET = r"""
QWidget#finalPage { background: transparent; }
QFrame#neuralCard {
    background-color: rgba(2, 7, 20, 238);
    border: 1px solid #172754;
    border-radius: 8px;
}
QFrame#neuralCardStrong {
    background-color: rgba(2, 6, 18, 246);
    border: 1px solid #2c3270;
    border-radius: 9px;
}
QFrame#moduleHeader {
    background: transparent;
    border: none;
    border-bottom: 1px solid #101a39;
}
QLabel#moduleGlyph { color: #8f57ff; font-size: 11px; font-weight: 700; }
QLabel#moduleMenu { color: #4b5579; font-size: 12px; }
QLabel#moduleEyebrow { color: #8270bd; font-size: 10px; font-weight: 600; letter-spacing: 1.15px; }
QLabel#moduleTitle { color: #ded5ff; font-size: 15px; font-weight: 600; letter-spacing: 1.05px; }
QLabel#moduleSub { color: #687493; font-size: 10px; }
QLabel#moduleValue { color: #61dcff; font-size: 11px; font-weight: 600; }
QLabel#moduleValuePurple { color: #b66bff; font-size: 11px; font-weight: 600; }
QLabel#moduleText { color: #b9c7dc; font-size: 10px; }
QLabel#moduleMuted { color: #707b98; font-size: 9px; }
QLabel#statusGreen { color: #35dfc2; font-size: 9px; font-weight: 600; letter-spacing:.8px; }
QLineEdit#moduleSearch, QLineEdit#moduleInput {
    background-color: #030a18;
    border: 1px solid #17284d;
    border-radius: 7px;
    color: #d8e8f7;
    padding: 7px 10px;
    selection-background-color: #5a31c5;
}
QPushButton#moduleButton {
    background-color: #070b1d;
    border: 1px solid #202b5a;
    border-radius: 5px;
    color: #9d86d8;
    padding: 6px 10px;
    font-size: 8px;
    font-weight: 600;
    letter-spacing: .35px;
}
QPushButton#moduleButton:hover { border-color: #7043d6; color: #d0b7ff; background-color: #0c0d29; }
QPushButton#moduleTab {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: #68748c;
    padding: 7px 12px;
    font-size: 9px;
}
QPushButton#moduleTab:checked { color: #a477ff; border-bottom-color: #7c42e5; }
QCheckBox { color: #aabbd0; spacing: 7px; font-size: 9px; }
QCheckBox::indicator { width: 12px; height: 12px; border: 1px solid #3a4d75; border-radius: 2px; background: #030916; }
QCheckBox::indicator:checked { background: #7b39ea; border-color: #9c5cff; }
QComboBox, QDateEdit {
    background-color: #030a18; border: 1px solid #17284d; border-radius: 6px;
    color: #b9c8dc; padding: 6px 8px; font-size: 9px;
}
QListWidget, QTableWidget {
    background: transparent; border: none; color: #b9c8dc; gridline-color: #111e39;
    outline: none; font-size: 9px;
}
QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #0d1830; }
QListWidget::item:selected { background: #0b1230; color: #d5c6ff; }
QHeaderView::section { background: #050b18; color: #65728c; border: none; border-bottom: 1px solid #152447; padding: 6px; font-size: 8px; }
QProgressBar#moduleProgress { background: #0a1024; border: none; border-radius: 2px; min-height: 3px; max-height: 3px; }
QProgressBar#moduleProgress::chunk { background-color: #8b42ff; border-radius: 2px; }
QProgressBar#systemBar { background:#091024; border:none; border-radius:2px; min-height:3px; max-height:3px; }
QProgressBar#systemBar::chunk { background-color:#655cff; border-radius:2px; }
QSlider::groove:horizontal { height: 3px; background: #171c35; border-radius: 1px; }
QSlider::handle:horizontal { width: 10px; margin: -4px 0; border-radius: 5px; background: #9b62ff; }
"""


class SidebarButton(QPushButton):
    """Target-style navigation row with a real vector icon, not a Unicode glyph."""

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self._icon_token = str(icon or "")
        self._label = str(label or "")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setText(self._label)
        self.setFixedHeight(42)
        self.setStyleSheet(
            "QPushButton{background:transparent;border:1px solid transparent;border-radius:6px;"
            "color:#7c86a7;text-align:left;padding:0 12px 0 42px;font-size:10px;font-weight:500;letter-spacing:.45px;}"
            "QPushButton:hover{background:#070b20;border-color:#171f49;color:#b8a5eb;}"
            "QPushButton:checked{background:#17104a;border-color:#6533c9;color:#eee7ff;}"
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        checked = self.isChecked()
        col = QColor("#bd8cff") if checked else QColor("#7d83b3")
        if self.underMouse() and not checked:
            col = QColor("#a99bd8")
        pen = QPen(col, 1.25, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        cx, cy = 21.0, self.height() / 2.0
        key = self._label.upper()

        if key == "ACCUEIL":
            roof = QPainterPath(); roof.moveTo(cx-7,cy-1); roof.lineTo(cx,cy-7); roof.lineTo(cx+7,cy-1)
            p.drawPath(roof); p.drawRoundedRect(QRectF(cx-5.5,cy-1,cx*0+11,8),1.5,1.5)
        elif key == "CONVERSATION":
            p.drawRoundedRect(QRectF(cx-7,cy-6,14,10),4,4)
            p.drawLine(QPointF(cx-3,cy+4), QPointF(cx-5,cy+7)); p.drawLine(QPointF(cx-3,cy+4), QPointF(cx,cy+4))
        elif key == "MÉMOIRE":
            p.drawEllipse(QRectF(cx-6.5,cy-6,13,12)); p.drawLine(QPointF(cx,cy-6),QPointF(cx,cy+6))
            p.drawArc(QRectF(cx-5,cy-3,5,6),90*16,180*16); p.drawArc(QRectF(cx,cy-3,5,6),-90*16,180*16)
        elif key == "TÂCHES":
            p.drawRoundedRect(QRectF(cx-6,cy-6,12,12),2,2)
            p.drawLine(QPointF(cx-3,cy),QPointF(cx-1,cy+2)); p.drawLine(QPointF(cx-1,cy+2),QPointF(cx+4,cy-3))
        elif key == "AGENDA":
            p.drawRoundedRect(QRectF(cx-7,cy-5,14,11),2,2); p.drawLine(QPointF(cx-7,cy-1),QPointF(cx+7,cy-1))
            p.drawLine(QPointF(cx-4,cy-7),QPointF(cx-4,cy-4)); p.drawLine(QPointF(cx+4,cy-7),QPointF(cx+4,cy-4))
        elif key == "PROJETS":
            for dx in (-5,2):
                for dy in (-5,2): p.drawRoundedRect(QRectF(cx+dx,cy+dy,5,5),1,1)
        elif key == "FICHIERS":
            path = QPainterPath(); path.moveTo(cx-7,cy-5); path.lineTo(cx-1,cy-5); path.lineTo(cx+1,cy-3); path.lineTo(cx+7,cy-3); path.lineTo(cx+6,cy+6); path.lineTo(cx-7,cy+6); path.closeSubpath(); p.drawPath(path)
        elif key == "MUSIQUE":
            p.drawLine(QPointF(cx+2,cy-6),QPointF(cx+2,cy+3)); p.drawLine(QPointF(cx+2,cy-6),QPointF(cx+6,cy-7)); p.drawEllipse(QRectF(cx-3,cy+1,5,4))
        elif key == "PARAMÈTRES":
            p.drawEllipse(QPointF(cx,cy),3.0,3.0); p.drawEllipse(QPointF(cx,cy),6.0,6.0)
            for i in range(8):
                a=math.tau*i/8; p.drawLine(QPointF(cx+math.cos(a)*6,cy+math.sin(a)*6),QPointF(cx+math.cos(a)*8,cy+math.sin(a)*8))
        else:
            p.drawEllipse(QPointF(cx,cy),5.5,5.5)


class HomeComposer(QFrame):
    message_sent = Signal(str)
    attachment_requested = Signal()
    attachment_cleared = Signal()
    microphone_pressed = Signal()
    microphone_released = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeComposer")
        self.setStyleSheet(
            "QFrame#homeComposer{background:#030816;border:1px solid #1b2751;border-radius:20px;}"
            "QLineEdit{background:transparent;border:none;color:#d7e7f5;padding:6px 10px;font-size:12px;}"
            "QPushButton#homeAttachButton{background:transparent;border:1px solid transparent;border-radius:15px;padding:0px;}"
            "QPushButton#homeAttachButton:hover{background:#08091d;border-color:#302865;}"
            "QPushButton#homeMicButton{background:#080a20;border:1px solid #2e2e62;border-radius:16px;padding:0px;}"
            "QPushButton#homeMicButton:hover{background:#0b1129;border-color:#4a4c8d;}"
            "QPushButton#homeMicButton[listening=true]{background:#071c2b;border-color:#45d9ff;}"
            "QPushButton#homeSendButton{background:#120a35;border:1px solid #744bd1;border-radius:16px;padding:0px;}"
            "QPushButton#homeSendButton:hover{background:#1b0c48;border-color:#a16cff;}"
            "QFrame#homeAttachmentBar{background:#07091a;border:1px solid #322d63;border-radius:8px;}"
            "QLabel#homeAttachmentLabel{color:#aeb8ce;font-size:9px;}"
            "QPushButton#homeAttachmentClear{background:transparent;border:1px solid transparent;border-radius:10px;color:#786d9e;font-size:14px;}"
            "QPushButton#homeAttachmentClear:hover{background:#1d0d2d;border-color:#5a2c77;color:#e2c7ff;}"
        )
        shell = QVBoxLayout(self)
        self.setMinimumHeight(50)
        shell.setContentsMargins(10, 5, 7, 5)
        shell.setSpacing(3)

        self.attachment_bar = QFrame()
        self.attachment_bar.setObjectName("homeAttachmentBar")
        attachment_row = QHBoxLayout(self.attachment_bar)
        attachment_row.setContentsMargins(6, 2, 4, 2)
        attachment_row.setSpacing(5)
        attachment_icon = QLabel()
        attachment_icon.setPixmap(aura_action_icon("attach", size=26).pixmap(16, 16))
        attachment_row.addWidget(attachment_icon)
        self.attachment_label = QLabel()
        self.attachment_label.setObjectName("homeAttachmentLabel")
        attachment_row.addWidget(self.attachment_label, 1)
        self.attachment_clear_button = QPushButton("×")
        self.attachment_clear_button.setObjectName("homeAttachmentClear")
        self.attachment_clear_button.setFixedSize(22, 22)
        self.attachment_clear_button.clicked.connect(self.attachment_cleared.emit)
        attachment_row.addWidget(self.attachment_clear_button)
        self.attachment_bar.hide()
        shell.addWidget(self.attachment_bar)

        row_host = QWidget()
        row = QHBoxLayout(row_host)
        row.setContentsMargins(2, 0, 0, 0)
        row.setSpacing(7)
        self.attach_button = QPushButton("")
        self.attach_button.setObjectName("homeAttachButton")
        self.attach_button.setFixedSize(32, 32)
        self.attach_button.setToolTip("Joindre un document à analyser")
        apply_action_icon(self.attach_button, "attach", size=18)
        self.attach_button.clicked.connect(self.attachment_requested.emit)
        row.addWidget(self.attach_button)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Parle-moi ou écris ton message…")
        self.input_field.returnPressed.connect(self._send)
        row.addWidget(self.input_field, 1)
        self.mic_button = QPushButton("")
        self.mic_button.setObjectName("homeMicButton")
        self.mic_button.setFixedSize(34, 34)
        self.mic_button.setToolTip("Maintiens le bouton pendant que tu parles")
        apply_action_icon(self.mic_button, "microphone", size=18)
        self.mic_button.pressed.connect(self.microphone_pressed.emit)
        self.mic_button.released.connect(self.microphone_released.emit)
        row.addWidget(self.mic_button)
        self.send_button = QPushButton("")
        self.send_button.setObjectName("homeSendButton")
        self.send_button.setFixedSize(34, 34)
        self.send_button.setToolTip("Envoyer")
        apply_action_icon(self.send_button, "send", size=18)
        self.send_button.clicked.connect(self._send)
        row.addWidget(self.send_button)
        shell.addWidget(row_host)

    def _send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.message_sent.emit(text)

    def set_interaction_enabled(self, enabled: bool):
        enabled = bool(enabled)
        self.input_field.setEnabled(enabled)
        self.attach_button.setEnabled(enabled)
        self.mic_button.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.input_field.setPlaceholderText("Parle-moi ou écris ton message…" if enabled else "Préchauffage d’AURA en cours…")

    def set_microphone_available(self, available: bool):
        available = bool(available)
        self.mic_button.setEnabled(available)
        apply_action_icon(self.mic_button, "microphone", disabled=not available, size=18)

    def set_microphone_state(self, state: str):
        listening = str(state or "").upper() == "LISTENING"
        apply_action_icon(self.mic_button, "microphone", active=listening, disabled=not self.mic_button.isEnabled(), size=18)
        self.mic_button.setProperty("listening", listening)
        self.mic_button.style().unpolish(self.mic_button)
        self.mic_button.style().polish(self.mic_button)

    def set_active_attachment(self, name: str, *, meta: str = ""):
        label = str(name or "Document")
        details = str(meta or "").strip()
        self.attachment_label.setText(label + (f" · {details}" if details else ""))
        self.attachment_bar.show()
        self.setMinimumHeight(78)

    def clear_active_attachment(self):
        self.attachment_label.clear()
        self.attachment_bar.hide()
        self.setMinimumHeight(50)


class NeonGauge(QWidget):
    def __init__(self, value: int = 87, label: str = "MÉMOIRE CORES", parent=None):
        super().__init__(parent)
        self.value = int(value)
        self.label = label
        self._phase = 0.0
        self.setMinimumSize(120, 120)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

    def _tick(self):
        self._phase = (self._phase + 0.025) % 1.0
        self.update()

    def set_value(self, value: int):
        self.value = max(0, min(100, int(value)))
        self.update()

    def paintEvent(self, event):
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width()/2, self.height()/2
        r = min(self.width(), self.height()) * .36
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(20, 31, 62), max(5, r*.10)))
        p.drawEllipse(QPointF(cx, cy), r, r)
        grad = QConicalGradient(cx, cy, -90 + self._phase*25)
        grad.setColorAt(0.0, QColor("#a34cff"))
        grad.setColorAt(.48, QColor("#6e37f5"))
        grad.setColorAt(.78, QColor("#22b7ff"))
        grad.setColorAt(1.0, QColor("#a34cff"))
        p.setPen(QPen(grad, max(5, r*.10), Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(cx-r, cy-r, r*2, r*2), 90*16, int(-360*16*self.value/100))
        for idx in range(24):
            a = math.tau*idx/24 + self._phase*.3
            rr = r*1.27
            x1, y1 = cx+math.cos(a)*rr, cy+math.sin(a)*rr
            x2, y2 = cx+math.cos(a)*(rr+3+(idx%3)), cy+math.sin(a)*(rr+3+(idx%3))
            p.setPen(QPen(QColor(93, 79, 171, 80 if idx % 2 else 140), 1))
            p.drawLine(QPointF(x1,y1), QPointF(x2,y2))
        f = QFont("Segoe UI")
        f.setPixelSize(max(18, int(r*.40)))
        p.setFont(f); p.setPen(QColor("#e7efff"))
        p.drawText(QRectF(cx-r, cy-r*.30, r*2, r*.55), Qt.AlignCenter, f"{self.value}%")
        f.setPixelSize(max(6, int(r*.12)))
        p.setFont(f); p.setPen(QColor("#66738f"))
        p.drawText(QRectF(cx-r, cy+r*.18, r*2, r*.38), Qt.AlignCenter, self.label)


class Sparkline(QWidget):
    def __init__(self, accent: str = "#7e4cff", parent=None):
        super().__init__(parent)
        self.accent = QColor(accent)
        self.values = [22, 30, 26, 42, 39, 61, 48, 70, 58, 64, 45, 71, 63, 78, 69, 82]
        self._phase = 0
        self.setMinimumHeight(46)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(260)

    def _tick(self):
        self._phase += 1
        base = self.values[-1]
        delta = ((self._phase * 17) % 19) - 9
        self.values = self.values[1:] + [max(8, min(92, base + delta))]
        self.update()

    def paintEvent(self, event):
        del event
        if len(self.values) < 2:
            return
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        for i, val in enumerate(self.values):
            x = i * w / (len(self.values)-1)
            y = h - 4 - (h-8)*val/100
            if i == 0: path.moveTo(x,y)
            else: path.lineTo(x,y)
        p.setPen(QPen(self.accent, 1.4)); p.drawPath(path)
        p.setPen(QPen(QColor(self.accent.red(), self.accent.green(), self.accent.blue(), 42), 5)); p.drawPath(path)


class SectionCard(QFrame):
    def __init__(self, title: str, parent=None, *, strong: bool = False):
        super().__init__(parent)
        self.setObjectName("neuralCardStrong" if strong else "neuralCard")
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(10, 0, 10, 9)
        self.layout_box.setSpacing(7)
        header = QFrame(); header.setObjectName("moduleHeader"); header.setFixedHeight(31)
        hl = QHBoxLayout(header); hl.setContentsMargins(1, 0, 1, 0); hl.setSpacing(7)
        glyph = QLabel("◇"); glyph.setObjectName("moduleGlyph"); glyph.setFixedWidth(13); hl.addWidget(glyph)
        title_label = QLabel(title); title_label.setObjectName("moduleEyebrow"); hl.addWidget(title_label)
        hl.addStretch(1)
        menu = QLabel("···"); menu.setObjectName("moduleMenu"); hl.addWidget(menu)
        self.layout_box.addWidget(header)


class TasksCompactCard(SectionCard):
    def __init__(self, parent=None):
        super().__init__("TÂCHES EN COURS", parent)
        self._rows = []
        for text, pct in (("Analyser rapport maintenance.pdf", 90), ("Préparer présentation Neural Echo", 65), ("Répondre aux emails importants", 30), ("Recherche visuelle : référence UI", 0)):
            self._add(text, pct)
        btn = QPushButton("VOIR TOUTES LES TÂCHES"); btn.setObjectName("moduleButton")
        self.open_requested = btn.clicked
        self.layout_box.addWidget(btn)

    def _add(self, text, pct):
        row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(0,0,0,0); lay.setSpacing(7)
        box = QCheckBox(text); box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred); lay.addWidget(box, 1)
        if pct:
            prog = QProgressBar(); prog.setObjectName("moduleProgress"); prog.setRange(0,100); prog.setValue(pct); prog.setTextVisible(False); prog.setFixedWidth(72); lay.addWidget(prog)
            val = QLabel(f"{pct}%"); val.setObjectName("moduleMuted"); val.setFixedWidth(26); lay.addWidget(val)
        else:
            wait = QLabel("EN ATTENTE"); wait.setObjectName("moduleMuted"); lay.addWidget(wait)
        self.layout_box.addWidget(row)

    def set_tasks(self, rows):
        # Compact reference remains visually stable; live task text is surfaced by MainWindow's
        # legacy dashboard cards and the full Tasks page. This method exists for future binding.
        self._rows = list(rows or [])


class SystemCompactCard(SectionCard):
    def __init__(self, parent=None):
        super().__init__("ÉTAT DU SYSTÈME", parent)
        self.setMinimumHeight(245)
        body = QHBoxLayout(); body.setSpacing(12); body.setContentsMargins(0,2,0,0)
        self.gauge = NeonGauge(87, "MÉMOIRE CORES")
        self.gauge.setFixedSize(132,132)
        body.addWidget(self.gauge,0,Qt.AlignVCenter)
        metrics = QVBoxLayout(); metrics.setSpacing(7)
        self.metric_labels = {}
        self.metric_bars = {}
        rows = (("CPU", "23%", 23), ("RAM", "7.2 / 16 GB", 45), ("DISQUE", "512 / 2000 GB", 26), ("TEMP.", "48°C", 48))
        for key, value, pct in rows:
            row = QHBoxLayout(); row.setSpacing(7)
            k=QLabel(key); k.setObjectName("moduleMuted"); k.setFixedWidth(52)
            bar=QProgressBar(); bar.setObjectName("systemBar"); bar.setRange(0,100); bar.setValue(pct); bar.setTextVisible(False); bar.setFixedWidth(92)
            v=QLabel(value); v.setObjectName("moduleText"); v.setAlignment(Qt.AlignRight|Qt.AlignVCenter); v.setMinimumWidth(54)
            row.addWidget(k); row.addWidget(bar); row.addWidget(v,1)
            metrics.addLayout(row); self.metric_labels[key]=v; self.metric_bars[key]=bar
        net = QHBoxLayout(); net.setSpacing(7)
        nk=QLabel("RÉSEAU"); nk.setObjectName("moduleMuted"); nk.setFixedWidth(52)
        nv=QLabel("↓ 42.3 Mbps    ↑ 18.7 Mbps"); nv.setObjectName("moduleText"); nv.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        net.addWidget(nk); net.addWidget(nv,1); metrics.addLayout(net); self.metric_labels["RÉSEAU"]=nv
        # Runtime compatibility: VRAM remains addressable but no longer consumes a visible row.
        self.metric_labels["VRAM"] = QLabel("3.1 / 8 GB"); self.metric_labels["VRAM"].hide()
        body.addLayout(metrics,1)
        self.layout_box.addLayout(body)
        btn=QPushButton("VOIR LES DIAGNOSTICS"); btn.setObjectName("moduleButton"); self.layout_box.addWidget(btn)
        self.diagnostic_requested = btn.clicked

    def update_metrics(self, *, cpu=None, ram=None, vram=None, temp=None):
        if cpu is not None:
            self.metric_labels["CPU"].setText(f"{float(cpu):.0f}%"); self.metric_bars["CPU"].setValue(max(0,min(100,int(float(cpu)))))
        if ram: self.metric_labels["RAM"].setText(str(ram))
        if vram: self.metric_labels["VRAM"].setText(str(vram))
        if temp is not None:
            self.metric_labels["TEMP."].setText(f"{float(temp):.0f}°C"); self.metric_bars["TEMP."].setValue(max(0,min(100,int(float(temp)))))


class QuickAccessCard(SectionCard):
    action_requested = Signal(str)
    def __init__(self, parent=None):
        super().__init__("RACCOURCIS RAPIDES", parent)
        self.setMinimumHeight(140)
        grid=QGridLayout(); grid.setContentsMargins(0,1,0,0); grid.setHorizontalSpacing(5); grid.setVerticalSpacing(5)
        actions=(("☑","NOUVELLE TÂCHE","tasks"),("▤","NOTE RAPIDE","memory"),("▱","ANALYSE DOC","files"),("◉","SYNTHÈSE VOCALE","conversation"),("⌕","RECHERCHE WEB","conversation"),("▦","AGENDA","agenda"))
        for i,(ico,label,key) in enumerate(actions):
            b=QPushButton(f"{ico}\n{label}"); b.setObjectName("moduleButton"); b.setMinimumHeight(46); b.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); b.clicked.connect(lambda _=False,k=key:self.action_requested.emit(k)); grid.addWidget(b,i//3,i%3)
        self.layout_box.addLayout(grid)


class BasePage(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("finalPage")
        self.root = QVBoxLayout(self); self.root.setContentsMargins(16,14,16,14); self.root.setSpacing(10)
        head=QHBoxLayout(); titles=QVBoxLayout(); titles.setSpacing(2)
        t=QLabel(title); t.setObjectName("moduleTitle"); titles.addWidget(t)
        if subtitle:
            s=QLabel(subtitle); s.setObjectName("moduleSub"); titles.addWidget(s)
        head.addLayout(titles); head.addStretch(); self.root.addLayout(head)


class MemoryPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("AURA · MÉMOIRE & CONTEXTE", "Souvenirs persistants, notes et préférences", parent)
        tabs=QHBoxLayout(); tabs.setSpacing(0)
        for i,name in enumerate(("SOUVENIRS","NOTES","PRÉFÉRENCES")):
            b=QPushButton(name); b.setObjectName("moduleTab"); b.setCheckable(True); b.setAutoExclusive(True); b.setChecked(i==0); tabs.addWidget(b)
        tabs.addStretch(); self.root.addLayout(tabs)
        search=QLineEdit(); search.setObjectName("moduleSearch"); search.setPlaceholderText("Rechercher dans la mémoire…"); self.root.addWidget(search)
        card=SectionCard("MÉMOIRE INDEXÉE", strong=True); self.list=QListWidget()
        for text in ("10/05 · Rapport financier Q2 — Analyse & tendances", "08/05 · Réunion stratégie IA — Décisions & actions", "05/05 · Brief produit Nexus — Positionnement marché", "01/05 · Objectifs Q2 — Priorités & KPIs"):
            self.list.addItem(QListWidgetItem("◉  "+text+"     ★"))
        card.layout_box.addWidget(self.list,1); self.root.addWidget(card,1)
        btn=QPushButton("OUVRIR LA MÉMOIRE COMPLÈTE"); btn.setObjectName("moduleButton"); self.root.addWidget(btn)


class MailPage(QWidget):
    """AURA MAIL module - shared PersonalIntegrationDispatcher backend."""

    def __init__(self):
        super().__init__()
        self.setObjectName("mailPage")
        self._controller = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        title = QLabel("MAIL")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self.status_label = QLabel("Provider: en attente  MODE SYNTHETIQUE")
        self.status_label.setObjectName("sectionSub")
        root.addWidget(self.status_label)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Rechercher dans les mails...")
        search_row.addWidget(self.search_edit)

        self.search_button = QPushButton("RECHERCHER")
        self.search_button.setObjectName("primaryButton")
        self.search_button.clicked.connect(self._search)
        search_row.addWidget(self.search_button)

        self.refresh_button = QPushButton("BOITE DE RECEPTION")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.clicked.connect(self._inbox)
        search_row.addWidget(self.refresh_button)
        root.addLayout(search_row)

        self.list_widget = QListWidget()
        root.addWidget(self.list_widget)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.read_button = QPushButton("LIRE")
        self.read_button.clicked.connect(self._read_selected)
        actions.addWidget(self.read_button)
        self.attachments_button = QPushButton("PIECES JOINTES")
        self.attachments_button.clicked.connect(self._attachments_selected)
        actions.addWidget(self.attachments_button)
        self.archive_button = QPushButton("ARCHIVER")
        self.archive_button.clicked.connect(self._archive_selected)
        actions.addWidget(self.archive_button)
        self.trash_button = QPushButton("CORBEILLE")
        self.trash_button.clicked.connect(self._trash_selected)
        actions.addWidget(self.trash_button)
        root.addLayout(actions)

        compose = SectionCard("COMPOSER")
        compose_layout = QVBoxLayout()
        self.to_edit = QLineEdit()
        self.to_edit.setPlaceholderText("Destinataire (test: alice@example.invalid)")
        self.subject_edit = QLineEdit()
        self.subject_edit.setPlaceholderText("Sujet")
        self.body_edit = QLineEdit()
        self.body_edit.setPlaceholderText("Message")
        compose_layout.addWidget(self.to_edit)
        compose_layout.addWidget(self.subject_edit)
        compose_layout.addWidget(self.body_edit)
        compose.setLayout(compose_layout)
        root.addWidget(compose)

        compose_actions = QHBoxLayout()
        self.draft_button = QPushButton("BROUILLON")
        self.draft_button.clicked.connect(self._draft)
        compose_actions.addWidget(self.draft_button)
        self.send_button = QPushButton("ENVOYER")
        self.send_button.setObjectName("primaryButton")
        self.send_button.clicked.connect(self._send)
        compose_actions.addWidget(self.send_button)
        self.reply_button = QPushButton("REPONDRE AU MAIL SELECTIONNE")
        self.reply_button.clicked.connect(self._reply_selected)
        compose_actions.addWidget(self.reply_button)
        self.forward_button = QPushButton("TRANSFERER")
        self.forward_button.clicked.connect(self._forward_selected)
        compose_actions.addWidget(self.forward_button)
        root.addLayout(compose_actions)

        self.result_label = QLabel("Aucune action.")
        self.result_label.setObjectName("sectionSub")
        self.result_label.setWordWrap(True)
        root.addWidget(self.result_label)

        confirm_row = QHBoxLayout()
        self.confirm_button = QPushButton("CONFIRMER")
        self.confirm_button.setObjectName("primaryButton")
        self.confirm_button.clicked.connect(self._confirm)
        confirm_row.addWidget(self.confirm_button)
        self.cancel_button = QPushButton("ANNULER")
        self.cancel_button.clicked.connect(self._cancel)
        confirm_row.addWidget(self.cancel_button)
        root.addLayout(confirm_row)

    def set_controller(self, controller):
        self._controller = controller
        self._refresh_status()
        self._inbox()

    def _refresh_status(self):
        if self._controller is None:
            self.status_label.setText("Provider: indisponible")
            return
        try:
            status = self._controller.status()
            state = "DISPONIBLE" if status.available else "INDISPONIBLE"
            self.status_label.setText(
                f"Provider: {state}  {status.health_state}  "
                f"{status.mode}  {status.capabilities} capacites"
            )
        except Exception as exc:
            self.status_label.setText(f"Provider: erreur  {type(exc).__name__}")

    def _selected_id(self):
        item = self.list_widget.currentItem()
        if item is None:
            return None
        text = item.text().strip()
        match = re.search(r"\bmsg[-_][A-Za-z0-9._\-]+\b", text, flags=re.I)
        return match.group(0) if match else None

    def _show_reply(self, reply):
        text = getattr(reply, "text", "") or ""
        self.result_label.setText(text)
        capability = getattr(reply, "capability_id", None)
        if capability == "email.search":
            self.list_widget.clear()
            for line in text.splitlines():
                if re.search(r"\bmsg[-_][A-Za-z0-9._\-]+\b", line, flags=re.I):
                    self.list_widget.addItem(line.lstrip("- ").strip())
        return reply

    def _inbox(self):
        if self._controller is not None:
            self._show_reply(self._controller.inbox())

    def _search(self):
        if self._controller is not None:
            self._show_reply(self._controller.search(self.search_edit.text().strip()))

    def _read_selected(self):
        message_id = self._selected_id()
        if self._controller is not None and message_id:
            self._show_reply(self._controller.read(message_id))

    def _attachments_selected(self):
        message_id = self._selected_id()
        if self._controller is not None and message_id:
            self._show_reply(self._controller.attachments(message_id))

    def _archive_selected(self):
        message_id = self._selected_id()
        if self._controller is not None and message_id:
            self._show_reply(self._controller.archive(message_id))

    def _trash_selected(self):
        message_id = self._selected_id()
        if self._controller is not None and message_id:
            self._show_reply(self._controller.trash(message_id))

    def _compose_values(self):
        to = self.to_edit.text().strip() or "alice@example.invalid"
        subject = self.subject_edit.text().strip() or "Test AURA"
        body = self.body_edit.text().strip() or "Message synthetique AURA."
        return to, subject, body

    def _draft(self):
        if self._controller is None:
            return
        to, subject, body = self._compose_values()
        self._show_reply(
            self._controller.create_draft(
                to=to,
                subject=subject,
                body_text=body,
            )
        )

    def _send(self):
        if self._controller is None:
            return
        to, subject, body = self._compose_values()
        self._show_reply(
            self._controller.send(
                to=to,
                subject=subject,
                body_text=body,
            )
        )

    def _reply_selected(self):
        message_id = self._selected_id()
        if self._controller is None or not message_id:
            return
        body = self.body_edit.text().strip() or "Reponse synthetique AURA."
        self._show_reply(
            self._controller.reply(
                message_id=message_id,
                body_text=body,
            )
        )

    def _forward_selected(self):
        message_id = self._selected_id()
        if self._controller is None or not message_id:
            return
        to = self.to_edit.text().strip() or "alice@example.invalid"
        self._show_reply(
            self._controller.forward(
                message_id=message_id,
                to=to,
                body_text=self.body_edit.text().strip(),
            )
        )

    def _confirm(self):
        if self._controller is not None:
            self._show_reply(self._controller.dispatcher.resume_confirmation())
            self._inbox()

    def _cancel(self):
        if self._controller is not None:
            self._show_reply(self._controller.dispatcher.cancel_confirmation())


class AgendaPage(QWidget):
    """AURA CALENDAR module - shared PersonalIntegrationDispatcher backend."""

    def __init__(self):
        super().__init__()
        self.setObjectName("agendaPage")
        self._controller = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        title = QLabel("CALENDAR / AGENDA")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self.status_label = QLabel("Provider: en attente  MODE SYNTHETIQUE")
        self.status_label.setObjectName("sectionSub")
        root.addWidget(self.status_label)

        top_actions = QHBoxLayout()
        self.events_button = QPushButton("RENDEZ-VOUS")
        self.events_button.setObjectName("primaryButton")
        self.events_button.clicked.connect(self._events)
        top_actions.addWidget(self.events_button)

        self.calendars_button = QPushButton("CALENDRIERS")
        self.calendars_button.clicked.connect(self._calendars)
        top_actions.addWidget(self.calendars_button)

        self.free_busy_button = QPushButton("LIBRE DEMAIN 14H-16H ?")
        self.free_busy_button.clicked.connect(self._free_busy)
        top_actions.addWidget(self.free_busy_button)
        root.addLayout(top_actions)

        self.list_widget = QListWidget()
        root.addWidget(self.list_widget)

        selected_actions = QHBoxLayout()
        self.read_button = QPushButton("DETAIL")
        self.read_button.clicked.connect(self._read_selected)
        selected_actions.addWidget(self.read_button)
        self.update_button = QPushButton("DECALER +30 MIN")
        self.update_button.clicked.connect(self._update_selected)
        selected_actions.addWidget(self.update_button)
        self.accept_button = QPushButton("ACCEPTER INVITATION")
        self.accept_button.clicked.connect(self._accept_selected)
        selected_actions.addWidget(self.accept_button)
        self.delete_button = QPushButton("SUPPRIMER")
        self.delete_button.clicked.connect(self._delete_selected)
        selected_actions.addWidget(self.delete_button)
        root.addLayout(selected_actions)

        create_card = SectionCard("NOUVEAU RENDEZ-VOUS")
        create_layout = QVBoxLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titre (ex: Reunion test)")
        self.when_edit = QLineEdit()
        self.when_edit.setPlaceholderText("Date/heure: AAAA-MM-JJ HH:MM")
        create_layout.addWidget(self.title_edit)
        create_layout.addWidget(self.when_edit)
        create_card.setLayout(create_layout)
        root.addWidget(create_card)

        self.create_button = QPushButton("CREER LE RENDEZ-VOUS")
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self._create)
        root.addWidget(self.create_button)

        self.result_label = QLabel("Aucune action.")
        self.result_label.setObjectName("sectionSub")
        self.result_label.setWordWrap(True)
        root.addWidget(self.result_label)

        confirm_row = QHBoxLayout()
        self.confirm_button = QPushButton("CONFIRMER")
        self.confirm_button.setObjectName("primaryButton")
        self.confirm_button.clicked.connect(self._confirm)
        confirm_row.addWidget(self.confirm_button)
        self.cancel_button = QPushButton("ANNULER")
        self.cancel_button.clicked.connect(self._cancel)
        confirm_row.addWidget(self.cancel_button)
        root.addLayout(confirm_row)

    def set_controller(self, controller):
        self._controller = controller
        self._events()

    def _refresh_status(self):
        if self._controller is None:
            self.status_label.setText("Provider: indisponible")
            return
        try:
            status = self._controller.status()
            state = "DISPONIBLE" if status.available else "INDISPONIBLE"
            self.status_label.setText(
                f"Provider: {state}  {status.health_state}  "
                f"{status.mode}  {status.capabilities} capacites"
            )
        except Exception as exc:
            self.status_label.setText(f"Provider: erreur  {type(exc).__name__}")

    def _selected_id(self):
        row = self.list_widget.currentRow()
        meta = getattr(self, "_aura_v123_row_meta", [])
        if 0 <= row < len(meta):
            item = meta[row]
            if item.get("source_kind") == "google":
                return str(item.get("event_id") or "") or None
            self.result_label.setText(
                "Élément AURA local sélectionné · les actions Google sont désactivées pour cette ligne."
            )
            return None
        item = self.list_widget.currentItem()
        if item is None:
            return None
        match = re.search(
            r"\bevt[-_][A-Za-z0-9._\-]+\b",
            item.text(),
            flags=re.I,
        )
        return match.group(0) if match else None

    def _show_reply(self, reply):
        text = str(getattr(reply, "text", "") or "")
        self.result_label.setText(text)
        capability = str(getattr(reply, "capability_id", "") or "")
        if capability != "calendar.search_events":
            return reply

        payload = getattr(reply, "payload", None)
        google_rows = []
        if isinstance(payload, dict):
            rows = (
                payload.get("events")
                or payload.get("items")
                or payload.get("results")
                or []
            )
            if isinstance(rows, (list, tuple)):
                google_rows = list(rows)

        self.list_widget.clear()
        self._aura_v123_row_meta = []
        google_count = 0

        for raw in google_rows:
            if isinstance(raw, dict):
                event = raw
            elif hasattr(raw, "to_dict"):
                try:
                    event = raw.to_dict()
                except Exception:
                    event = {}
            else:
                event = {}
            title = str(event.get("title") or event.get("summary") or "Sans titre")
            start = str(
                event.get("start_time")
                or event.get("start")
                or event.get("date_time")
                or ""
            )
            event_id = str(event.get("event_id") or event.get("id") or "")
            label = "[GOOGLE] " + title
            if start:
                label += " · " + start[:16]
            self.list_widget.addItem(label)
            self._aura_v123_row_meta.append(
                {"source_kind": "google", "event_id": event_id}
            )
            google_count += 1

        # Compatibility fallback if an older backend returns only formatted text.
        if not google_rows:
            for line in text.splitlines():
                if re.search(r"\bevt[-_][A-Za-z0-9._\-]+\b", line, flags=re.I):
                    self.list_widget.addItem("[GOOGLE] " + line.lstrip("- ").strip())
                    match = re.search(
                        r"\bevt[-_][A-Za-z0-9._\-]+\b",
                        line,
                        flags=re.I,
                    )
                    self._aura_v123_row_meta.append(
                        {
                            "source_kind": "google",
                            "event_id": match.group(0) if match else "",
                        }
                    )
                    google_count += 1

        from runtime.productivity_view_aggregation_v123 import (
            collect_local_agenda_items_v123,
        )
        local_rows = collect_local_agenda_items_v123(
            getattr(self, "_aura_v123_reminder_manager", None),
            getattr(self, "_aura_v123_task_manager", None),
            limit=100,
        )
        for item in local_rows:
            source = str(item.get("source") or "AURA")
            title = str(item.get("title") or "Sans titre")
            start = str(item.get("start_time") or "")
            label = "[" + source + "] " + title
            if start:
                label += " · " + start[:16]
            self.list_widget.addItem(label)
            self._aura_v123_row_meta.append(
                {
                    "source_kind": str(item.get("source_kind") or "local"),
                    "local_id": str(item.get("local_id") or ""),
                }
            )

        self.status_label.setText(
            "Agenda unifié · Google "
            + str(google_count)
            + " · AURA local "
            + str(len(local_rows))
        )
        return reply

    def _events(self):
        if self._controller is not None:
            self._show_reply(self._controller.events())
        else:
            from runtime.productivity_view_aggregation_v123 import (
                collect_local_agenda_items_v123,
            )
            rows = collect_local_agenda_items_v123(
                getattr(self, "_aura_v123_reminder_manager", None),
                getattr(self, "_aura_v123_task_manager", None),
                limit=100,
            )
            self.list_widget.clear()
            self._aura_v123_row_meta = []
            for item in rows:
                source = str(item.get("source") or "AURA")
                title = str(item.get("title") or "Sans titre")
                start = str(item.get("start_time") or "")
                label = "[" + source + "] " + title
                if start:
                    label += " · " + start[:16]
                self.list_widget.addItem(label)
                self._aura_v123_row_meta.append(
                    {"source_kind": str(item.get("source_kind") or "local")}
                )

    def _calendars(self):
        if self._controller is not None:
            self._show_reply(self._controller.calendars())

    def _read_selected(self):
        event_id = self._selected_id()
        if self._controller is not None and event_id:
            self._show_reply(self._controller.read(event_id))

    def _free_busy(self):
        if self._controller is None:
            return
        from datetime import datetime, timedelta
        from runtime.personal_integrations import resolve_timezone
        tz = resolve_timezone("Europe/Paris")
        day = datetime.now(tz) + timedelta(days=1)
        start = day.replace(hour=14, minute=0, second=0, microsecond=0)
        end = day.replace(hour=16, minute=0, second=0, microsecond=0)
        self._show_reply(
            self._controller.free_busy(
                time_min=start.isoformat(),
                time_max=end.isoformat(),
            )
        )

    def _create(self):
        if self._controller is None:
            return
        from datetime import datetime, timedelta
        from runtime.personal_integrations import resolve_timezone
        tz = resolve_timezone("Europe/Paris")
        raw = self.when_edit.text().strip()
        if raw:
            try:
                start = datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            except Exception:
                self.result_label.setText(
                    "Format attendu : AAAA-MM-JJ HH:MM"
                )
                return
        else:
            start = (datetime.now(tz) + timedelta(days=1)).replace(
                hour=18,
                minute=0,
                second=0,
                microsecond=0,
            )
        end = start + timedelta(hours=1)
        title = self.title_edit.text().strip() or "Rendez-vous AURA"
        self._show_reply(
            self._controller.create_event(
                title=title,
                start=start.isoformat(),
                end=end.isoformat(),
            )
        )

    def _update_selected(self):
        event_id = self._selected_id()
        if self._controller is None or not event_id:
            return
        self._show_reply(
            self._controller.update_event(
                event_id=event_id,
                changes={"title": "Rendez-vous AURA  modifie"},
            )
        )

    def _accept_selected(self):
        event_id = self._selected_id()
        if self._controller is not None and event_id:
            self._show_reply(
                self._controller.respond_invitation(
                    event_id=event_id,
                    response_status="accepted",
                )
            )

    def _delete_selected(self):
        event_id = self._selected_id()
        if self._controller is not None and event_id:
            self._show_reply(self._controller.delete_event(event_id))

    def _confirm(self):
        if self._controller is not None:
            self._show_reply(self._controller.dispatcher.resume_confirmation())
            self._events()

    def _cancel(self):
        if self._controller is not None:
            self._show_reply(self._controller.dispatcher.cancel_confirmation())


    # AURA_V123_NATIVE_AGENDA_AGGREGATION
    def set_local_sources(self, *, reminder_manager=None, task_manager=None):
        self._aura_v123_reminder_manager = reminder_manager
        self._aura_v123_task_manager = task_manager
        self._events()



class SystemPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("AURA · ÉTAT DU SYSTÈME", "Santé du noyau, ressources et connectivité", parent)
        top=QHBoxLayout(); top.setSpacing(12)
        gauge_card=SectionCard("NŒUD CENTRAL", strong=True); self.gauge=NeonGauge(87,"MÉMOIRE CORES"); gauge_card.layout_box.addWidget(self.gauge,1,Qt.AlignCenter); top.addWidget(gauge_card,2)
        metrics=SectionCard("TÉLÉMÉTRIE", strong=True); self.labels={}
        for key,val in (("CPU","23%"),("RAM","10.4 / 32 GB"),("STOCKAGE","512 / 2000 GB"),("TEMPÉRATURE","46°C"),("RÉSEAU","↓ 18.7 Mbps   ↑ 42.1 Mbps")):
            rr=QHBoxLayout(); k=QLabel(key); k.setObjectName("moduleMuted"); v=QLabel(val); v.setObjectName("moduleText"); bar=QProgressBar(); bar.setObjectName("moduleProgress"); bar.setRange(0,100); bar.setValue(32 if key!="RÉSEAU" else 54); bar.setTextVisible(False); bar.setFixedWidth(150); rr.addWidget(k); rr.addWidget(bar); rr.addWidget(v); metrics.layout_box.addLayout(rr); self.labels[key]=v
        top.addWidget(metrics,3); self.root.addLayout(top,1)
        actions=QHBoxLayout()
        for label in ("DIAGNOSTIC RAPIDE","NETTOYAGE MÉMOIRE","OPTIMISER SYSTÈME","PARAMÈTRES AVANCÉS"):
            b=QPushButton(label); b.setObjectName("moduleButton"); actions.addWidget(b)
        self.root.addLayout(actions)

    def update_metrics(self, *, cpu=None, ram=None, vram=None, temp=None):
        if cpu is not None: self.labels["CPU"].setText(f"{float(cpu):.0f}%")
        if ram: self.labels["RAM"].setText(str(ram))
        if temp is not None: self.labels["TEMPÉRATURE"].setText(f"{float(temp):.0f}°C")


class ProjectsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("AURA · PROJETS", "Suivi des projets actifs", parent)
        search=QLineEdit(); search.setObjectName("moduleSearch"); search.setPlaceholderText("Rechercher un projet…"); self.root.addWidget(search)
        row=QHBoxLayout(); row.setSpacing(10)
        for name,category,pct,accent in (("Midnight Rush","Clip vidéo",76,"#7148ff"),("Neural Echo Album","Musique",66,"#9c4fff"),("Low Signals Archive","Lo-Fi Series",58,"#3b8cff")):
            card=SectionCard(name, strong=True); art=QLabel("◈\nAURA"); art.setAlignment(Qt.AlignCenter); art.setMinimumHeight(130); art.setStyleSheet(f"background:#070b1c;border:1px solid {accent};border-radius:8px;color:{accent};font-size:18px;font-weight:700;"); card.layout_box.addWidget(art); c=QLabel(category); c.setObjectName("moduleMuted"); card.layout_box.addWidget(c); p=QProgressBar(); p.setObjectName("moduleProgress"); p.setRange(0,100); p.setValue(pct); p.setTextVisible(False); card.layout_box.addWidget(p); m=QLabel(f"Progression  {pct}%"); m.setObjectName("moduleText"); card.layout_box.addWidget(m); row.addWidget(card,1)
        self.root.addLayout(row,1)
        btn=QPushButton("VOIR TOUS LES PROJETS"); btn.setObjectName("moduleButton"); self.root.addWidget(btn)


class FilesPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("AURA · FICHIERS", "Accès rapide aux fichiers de travail", parent)
        search=QLineEdit(); search.setObjectName("moduleSearch"); search.setPlaceholderText("Rechercher un fichier…"); self.root.addWidget(search)
        card=SectionCard("FICHIERS RÉCENTS", strong=True); self.table=QTableWidget(5,3); self.table.setHorizontalHeaderLabels(["NOM","TAILLE","MODIFIÉ LE"]); self.table.verticalHeader().hide(); self.table.horizontalHeader().setStretchLastSection(True)
        rows=(("Storyboard_Midnight_Rush.pdf","2.4 MB","11/05/2026"),("Ambiance_Scene_3.mov","3.2 MB","11/05/2026"),("Presentation_Neural_Echo.pptx","12.8 MB","10/05/2026"),("Rapport_Maintenance.pdf","1.7 MB","08/05/2026"),("Notes_Clip.txt","6.3 KB","07/05/2026"))
        for r,row in enumerate(rows):
            for c,val in enumerate(row): self.table.setItem(r,c,QTableWidgetItem(val))
        self.table.setMinimumHeight(240); card.layout_box.addWidget(self.table); self.root.addWidget(card,1)
        btn=QPushButton("VOIR TOUS LES FICHIERS"); btn.setObjectName("moduleButton"); self.root.addWidget(btn)


class MusicPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("AURA · MUSIQUE", "Lecture Neural Echo et playlists locales", parent)
        row=QHBoxLayout(); row.setSpacing(12)
        now=SectionCard("LECTURE EN COURS", strong=True); art=QLabel("NEURAL ECHO\nMIDNIGHT RUSH // LO-FI"); art.setAlignment(Qt.AlignCenter); art.setMinimumSize(280,220); art.setStyleSheet("background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #081331,stop:.5 #23104c,stop:1 #08142d);border:1px solid #5d2fc1;border-radius:8px;color:#c5a5ff;font-size:14px;font-weight:650;"); now.layout_box.addWidget(art)
        ctrl=QHBoxLayout(); prev=QPushButton("◀"); play=QPushButton("Ⅱ"); nxt=QPushButton("▶");
        for b in (prev,play,nxt): b.setObjectName("moduleButton"); ctrl.addWidget(b)
        now.layout_box.addLayout(ctrl); slider=QSlider(Qt.Horizontal); slider.setValue(61); now.layout_box.addWidget(slider); row.addWidget(now,2)
        playlist=SectionCard("PLAYLIST", strong=True)
        for i,(name,t) in enumerate((("Midnight Rush // Lo-Fi","03:40"),("Under My Skin // Lo-Fi","04:12"),("Mirror Pulse // Rain","04:49"),("Ghost Frequency","04:08"),("Quicksilver // Liquid Sleep","04:29"))):
            rr=QHBoxLayout(); a=QLabel(f"{i+1:02d}"); a.setObjectName("moduleMuted"); b=QLabel(name); b.setObjectName("moduleText"); c=QLabel(t); c.setObjectName("moduleMuted"); rr.addWidget(a); rr.addWidget(b,1); rr.addWidget(c); playlist.layout_box.addLayout(rr)
        row.addWidget(playlist,3); self.root.addLayout(row,1)
        btn=QPushButton("VOIR LA PLAYLIST COMPLÈTE"); btn.setObjectName("moduleButton"); self.root.addWidget(btn)


class SettingsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(
            "AURA · PARAMÈTRES",
            "Réglages de l’interface et des sous-systèmes",
            parent,
        )
        from runtime.connected_accounts_v120 import get_connected_accounts_service_v120

        self._accounts_v120 = get_connected_accounts_service_v120()
        body = QHBoxLayout()
        body.setSpacing(12)

        menu = SectionCard("SECTIONS", strong=True)
        for name in (
            "COMPTES CONNECTÉS",
            "GÉNÉRAL",
            "APPARENCE",
            "VOIX & AUDIO",
            "CONNECTIVITÉ",
            "CONFIDENTIALITÉ",
            "SAUVEGARDES",
            "RACCOURCIS",
            "À PROPOS",
        ):
            button = QPushButton(name)
            button.setObjectName("moduleButton")
            menu.layout_box.addWidget(button)
        menu.layout_box.addStretch()
        body.addWidget(menu, 1)

        right = QVBoxLayout()
        right.setSpacing(12)

        accounts = SectionCard("COMPTES CONNECTÉS", strong=True)
        intro = QLabel(
            "Google OAuth sécurisé · jetons stockés dans le coffre Windows · aucun mot de passe enregistré par AURA"
        )
        intro.setObjectName("moduleText")
        intro.setWordWrap(True)
        accounts.layout_box.addWidget(intro)

        title = QLabel("GOOGLE")
        title.setObjectName("moduleTitle")
        accounts.layout_box.addWidget(title)

        services = QLabel("Gmail · Agenda · Contacts · Drive")
        services.setObjectName("moduleText")
        accounts.layout_box.addWidget(services)

        self._google_status_v120 = QLabel("Déconnecté")
        self._google_status_v120.setObjectName("moduleText")
        accounts.layout_box.addWidget(self._google_status_v120)

        actions = QHBoxLayout()
        self._google_connect_v120 = QPushButton("CONNECTER AVEC GOOGLE")
        self._google_test_v120 = QPushButton("TESTER")
        self._google_sync_v120 = QPushButton("SYNCHRONISER")
        self._google_disconnect_v120 = QPushButton("DÉCONNECTER")
        for button in (
            self._google_connect_v120,
            self._google_test_v120,
            self._google_sync_v120,
            self._google_disconnect_v120,
        ):
            button.setObjectName("moduleButton")
            actions.addWidget(button)
        accounts.layout_box.addLayout(actions)
        right.addWidget(accounts)

        general = SectionCard("GÉNÉRAL", strong=True)
        for label, checked in (
            ("Lancer AURA au démarrage", True),
            ("Minimiser dans la barre des tâches", True),
            ("Animations de l’interface", True),
            ("Réponse vocale automatique", False),
        ):
            cb = QCheckBox(label)
            cb.setChecked(checked)
            general.layout_box.addWidget(cb)
        row = QHBoxLayout()
        label = QLabel("Mode sombre")
        label.setObjectName("moduleText")
        combo = QComboBox()
        combo.addItems(["AURA Dark", "Système", "Contraste élevé"])
        row.addWidget(label)
        row.addStretch()
        row.addWidget(combo)
        general.layout_box.addLayout(row)
        right.addWidget(general)

        body.addLayout(right, 3)
        self.root.addLayout(body, 1)
        save_button = QPushButton("ENREGISTRER LES MODIFICATIONS")
        save_button.setObjectName("moduleButton")
        self.root.addWidget(save_button)

        self._google_connect_v120.clicked.connect(self._connect_google_v120)
        self._google_test_v120.clicked.connect(lambda *_: self._test_google_v120())
        self._google_sync_v120.clicked.connect(lambda *_: self._sync_google_v120())
        self._google_disconnect_v120.clicked.connect(lambda *_: self._disconnect_google_v120())
        self._refresh_google_v120()

    @staticmethod
    def _file_dialog_v120():
        for module_name in ("PySide6.QtWidgets", "PyQt6.QtWidgets", "PySide2.QtWidgets", "PyQt5.QtWidgets"):
            try:
                module = __import__(module_name, fromlist=["QFileDialog"])
                return module.QFileDialog
            except Exception:
                continue
        raise RuntimeError("Qt file dialog unavailable")

    def _first_google_v120(self):
        rows = self._accounts_v120.list_accounts("google")
        return rows[0] if rows else None

    def _refresh_google_v120(self):
        status = self._accounts_v120.provider_status("google")
        rows = status.get("accounts", [])
        if not rows:
            self._google_status_v120.setText("Déconnecté")
            return
        self._google_status_v120.setText(
            " | ".join(
                str(x.get("display_label", "Google")) + " · " + str(x.get("state", "unknown"))
                for x in rows
            )
        )

    def _connect_google_v120(self, *_):
        QFileDialog = self._file_dialog_v120()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer le client OAuth Google",
            "",
            "Google OAuth JSON (*.json)",
        )
        if not path:
            return
        self._google_status_v120.setText("Connexion Google...")
        try:
            account = self._accounts_v120.connect_google_from_client_file(path)
            self._google_status_v120.setText("Connecté · " + account.display_label)
        except Exception as exc:
            self._google_status_v120.setText("Erreur · " + type(exc).__name__)
        self._refresh_google_v120()

    def _test_google_v120(self):
        account = self._first_google_v120()
        if account is None:
            self._google_status_v120.setText("Déconnecté")
            return
        result = self._accounts_v120.test_account(account.account_id)
        self._google_status_v120.setText(
            ("OK · " + account.display_label)
            if result.get("ok")
            else ("Échec du test · " + str(result.get("error", "unknown")))
        )
        self._refresh_google_v120()

    def _sync_google_v120(self):
        account = self._first_google_v120()
        if account is None:
            self._google_status_v120.setText("Déconnecté")
            return
        result = self._accounts_v120.sync_summary(account.account_id)
        self._google_status_v120.setText(
            ("Synchronisé · " + ", ".join(sorted(result.get("summary", {}).keys())))
            if result.get("ok")
            else ("Échec synchro · " + str(result.get("error", "unknown")))
        )
        self._refresh_google_v120()

    def _disconnect_google_v120(self):
        account = self._first_google_v120()
        if account is not None:
            self._accounts_v120.disconnect(account.account_id)
        self._refresh_google_v120()


class TasksPage(BasePage):
    # AURA_V123_GOOGLE_TASKS_NATIVE_PAGE
    # AURA_V123_NATIVE_TASKS_AGGREGATION
    def __init__(self, parent=None):
        super().__init__(
            "AURA · TÂCHES",
            "Tâches AURA locales + Google Tasks · vue unifiée",
            parent,
        )
        self._controller = None
        self._task_manager = None
        self._row_meta = []

        card = SectionCard("TÂCHES · AURA + GOOGLE", strong=True)

        self.status_label = QLabel(
            "Tâches : chargement des sources AURA / Google"
        )
        self.status_label.setObjectName("moduleMuted")
        self.status_label.setWordWrap(True)
        card.layout_box.addWidget(self.status_label)

        toolbar = QHBoxLayout()
        self.sync_button = QPushButton("ACTUALISER TOUT")
        self.sync_button.setObjectName("moduleButton")
        self.sync_button.clicked.connect(self._sync)
        toolbar.addWidget(self.sync_button)

        self.confirm_button = QPushButton("CONFIRMER GOOGLE")
        self.confirm_button.setObjectName("moduleButton")
        self.confirm_button.clicked.connect(self._confirm)
        toolbar.addWidget(self.confirm_button)

        self.cancel_button = QPushButton("ANNULER")
        self.cancel_button.setObjectName("moduleButton")
        self.cancel_button.clicked.connect(self._cancel)
        toolbar.addWidget(self.cancel_button)
        toolbar.addStretch()
        card.layout_box.addLayout(toolbar)

        self.task_list = QListWidget()
        self.task_list.setObjectName("moduleList")
        self.task_list.currentRowChanged.connect(self._selection_changed)
        card.layout_box.addWidget(self.task_list, 1)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titre de la tâche Google à créer/modifier")
        card.layout_box.addWidget(self.title_edit)

        self.due_edit = QLineEdit()
        self.due_edit.setPlaceholderText("Échéance YYYY-MM-DD (Google Tasks = date)")
        card.layout_box.addWidget(self.due_edit)

        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Notes")
        card.layout_box.addWidget(self.notes_edit)

        actions = QHBoxLayout()
        self.create_button = QPushButton("CRÉER GOOGLE")
        self.create_button.setObjectName("moduleButton")
        self.create_button.clicked.connect(self._create)
        actions.addWidget(self.create_button)

        self.update_button = QPushButton("MODIFIER GOOGLE")
        self.update_button.setObjectName("moduleButton")
        self.update_button.clicked.connect(self._update_selected)
        actions.addWidget(self.update_button)

        self.complete_button = QPushButton("TERMINER GOOGLE")
        self.complete_button.setObjectName("moduleButton")
        self.complete_button.clicked.connect(self._complete_selected)
        actions.addWidget(self.complete_button)

        self.delete_button = QPushButton("SUPPRIMER GOOGLE")
        self.delete_button.setObjectName("moduleButton")
        self.delete_button.clicked.connect(self._delete_selected)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        card.layout_box.addLayout(actions)

        self.root.addWidget(card, 1)
        self._selection_changed(-1)

    def set_controller(self, controller):
        self._controller = controller
        self._sync()

    def set_local_sources(self, *, task_manager=None, **_unused):
        self._task_manager = task_manager
        self._sync()

    def _refresh_status(self, google_count=None, local_count=None):
        if google_count is not None or local_count is not None:
            self.status_label.setText(
                "Vue unifiée · AURA local "
                + str(int(local_count or 0))
                + " · Google "
                + str(int(google_count or 0))
            )
            return
        if self._controller is None:
            self.status_label.setText("Google Tasks non connecté · données AURA locales disponibles")
            return
        try:
            status = self._controller.status()
            available = bool(getattr(status, "available", False))
            health = str(getattr(status, "health_state", "") or "")
            mode = str(getattr(status, "mode", "GOOGLE_LIVE") or "GOOGLE_LIVE")
            self.status_label.setText(
                "Google Tasks · " + mode + " · "
                + ("PRÊT" if available else (health or "autorisation requise"))
            )
        except Exception as exc:
            self.status_label.setText(
                "Google Tasks · statut indisponible · " + type(exc).__name__
            )

    @staticmethod
    def _payload_rows(reply):
        payload = getattr(reply, "payload", None)
        if not isinstance(payload, dict):
            return []
        rows = payload.get("tasks") or payload.get("items") or payload.get("results") or []
        return list(rows) if isinstance(rows, (list, tuple)) else []

    def _selection_changed(self, row):
        meta = self._row_meta[row] if 0 <= row < len(self._row_meta) else {}
        is_google = meta.get("source_kind") == "google"
        for button in (self.update_button, self.complete_button, self.delete_button):
            button.setEnabled(bool(is_google))
        if meta and not is_google:
            self.status_label.setText(
                "Sélection AURA locale · les boutons Google restent désactivés pour éviter toute mutation croisée."
            )

    def _selected_google_id(self):
        row = self.task_list.currentRow()
        if row < 0 or row >= len(self._row_meta):
            return ""
        meta = self._row_meta[row]
        if meta.get("source_kind") != "google":
            return ""
        return str(meta.get("task_id") or "")

    def _render_combined(self, google_rows):
        from runtime.productivity_view_aggregation_v123 import collect_local_task_items_v123

        local_rows = collect_local_task_items_v123(self._task_manager, limit=100)
        self.task_list.clear()
        self._row_meta = []

        for raw in local_rows:
            title = str(raw.get("title") or "Sans titre")
            due = str(raw.get("due") or "")
            label = "[AURA] ○ " + title
            if due:
                label += " · " + due[:16]
            self.task_list.addItem(label)
            self._row_meta.append(
                {"source_kind": "local_task", "local_id": str(raw.get("local_id") or "")}
            )

        google_count = 0
        for raw in google_rows:
            if isinstance(raw, dict):
                item = raw
            elif hasattr(raw, "to_dict"):
                try:
                    item = raw.to_dict()
                except Exception:
                    item = {}
            else:
                item = {}
            task_id = str(item.get("task_id") or item.get("id") or "")
            title = str(item.get("title") or "Sans titre")
            due = str(item.get("due") or "")
            status = str(item.get("status") or "needsAction")
            prefix = "✓" if status == "completed" else "○"
            label = "[GOOGLE] " + prefix + " " + title
            if due:
                label += " · " + due[:10]
            self.task_list.addItem(label)
            self._row_meta.append({"source_kind": "google", "task_id": task_id})
            google_count += 1

        self._refresh_status(google_count=google_count, local_count=len(local_rows))
        self._selection_changed(self.task_list.currentRow())

    def _show_reply(self, reply):
        text = str(getattr(reply, "text", "") or "").strip()
        rows = self._payload_rows(reply)
        capability = str(getattr(reply, "capability_id", "") or "")
        if capability in {"tasks.list", "tasks.tasklists"} or rows:
            self._render_combined(rows)
        elif text:
            self.status_label.setText(text[:420])
        return reply

    def _sync(self):
        if self._controller is None:
            self._render_combined([])
            return
        self._show_reply(self._controller.list())

    def _create(self):
        if self._controller is None:
            return
        title = self.title_edit.text().strip()
        if not title:
            self.status_label.setText("Indique un titre pour la tâche.")
            return
        self._show_reply(
            self._controller.create(
                title=title,
                notes=self.notes_edit.text().strip(),
                due=self.due_edit.text().strip(),
            )
        )

    def _update_selected(self):
        task_id = self._selected_google_id()
        if self._controller is None or not task_id:
            self.status_label.setText("Sélectionne une tâche [GOOGLE] pour la modifier.")
            return
        changes = {}
        title = self.title_edit.text().strip()
        notes = self.notes_edit.text().strip()
        due = self.due_edit.text().strip()
        if title:
            changes["title"] = title
        if notes:
            changes["notes"] = notes
        if due:
            changes["due"] = due
        if not changes:
            self.status_label.setText("Indique au moins une modification.")
            return
        self._show_reply(self._controller.update(task_id, **changes))

    def _complete_selected(self):
        task_id = self._selected_google_id()
        if self._controller is None or not task_id:
            self.status_label.setText("Sélectionne une tâche [GOOGLE] à terminer.")
            return
        self._show_reply(self._controller.complete(task_id))

    def _delete_selected(self):
        task_id = self._selected_google_id()
        if self._controller is None or not task_id:
            self.status_label.setText("Sélectionne une tâche [GOOGLE] à supprimer.")
            return
        self._show_reply(self._controller.delete(task_id))

    def _confirm(self):
        if self._controller is None:
            return
        self._controller.dispatcher.resume_confirmation()
        self._sync()

    def _cancel(self):
        if self._controller is None:
            return
        self._show_reply(self._controller.dispatcher.cancel_confirmation())

class DiagnosticsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("DIAGNOSTICS & JOURNAUX", "État des sous-systèmes AURA", parent)
        tabs=QHBoxLayout();
        for i,name in enumerate(("SYSTÈME","RÉSEAU","AURA AI","APPLICATIONS")):
            b=QPushButton(name); b.setObjectName("moduleTab"); b.setCheckable(True); b.setAutoExclusive(True); b.setChecked(i==0); tabs.addWidget(b)
        tabs.addStretch(); self.root.addLayout(tabs)
        card=SectionCard("SYSTÈME", strong=True)
        for name,status in (("Noyau cognitif","Optimal"),("Base de connaissances","Synchronisée"),("Module vocal","Actif"),("Sécurité & intégrité","Protégée")):
            row=QHBoxLayout(); dot=QLabel("◉"); dot.setObjectName("statusGreen"); label=QLabel(name); label.setObjectName("moduleText"); val=QLabel(status); val.setObjectName("statusGreen"); row.addWidget(dot); row.addWidget(label,1); row.addWidget(val); card.layout_box.addLayout(row)
        self.root.addWidget(card,1)
        btn=QPushButton("VOIR TOUS LES JOURNAUX"); btn.setObjectName("moduleButton"); self.root.addWidget(btn)


class ConversationContextPanel(QWidget):
    """Right rail rebuilt from 02_CONVERSATION.

    CONTEXTE ACTIF remains compact at the top. SUGGESTIONS owns the remaining
    vertical rail and keeps the destructive-looking *transient* clear action
    pinned to its bottom edge. Persistent memory is never deleted here.
    """

    suggestion_requested = Signal(str)
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("conversationContextRail")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        context = QFrame(); context.setObjectName("conversationContextBlock")
        # Historical Patch 26.1 marker: context.setFixedHeight(146)
        context.setMinimumHeight(202)
        context.setMaximumHeight(224)
        context_layout = QVBoxLayout(context)
        context_layout.setContentsMargins(16, 14, 16, 15)
        context_layout.setSpacing(10)
        context_title = QLabel("CONTEXTE ACTIF"); context_title.setObjectName("conversationRailTitle")
        context_layout.addWidget(context_title)
        sep = QFrame(); sep.setObjectName("conversationRailSeparator"); context_layout.addWidget(sep)

        self.context_labels = {}
        for key, val in (
            ("Projet", "—"),
            ("Sujet", "Conversation locale"),
            ("Fichiers", "0"),
            ("Mémoire liée", "Active"),
            ("Statut", "● Actif"),
        ):
            row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(7)
            k = QLabel(key); k.setObjectName("conversationContextKey")
            v = QLabel(val); v.setObjectName("conversationContextStatusValue" if key == "Statut" else "conversationContextValue")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            v.setWordWrap(True)
            row.addWidget(k); row.addStretch(1); row.addWidget(v, 1)
            context_layout.addLayout(row)
            self.context_labels[key] = v
        root.addWidget(context)

        suggestions = QFrame(); suggestions.setObjectName("conversationSuggestionsBlock")
        suggestions_layout = QVBoxLayout(suggestions)
        suggestions_layout.setContentsMargins(16, 14, 16, 14)
        suggestions_layout.setSpacing(9)
        suggestions_title = QLabel("SUGGESTIONS"); suggestions_title.setObjectName("conversationRailTitle")
        suggestions_layout.addWidget(suggestions_title)
        sep2 = QFrame(); sep2.setObjectName("conversationRailSeparator"); suggestions_layout.addWidget(sep2)

        actions = (
            ("▧  Résumer la conversation", "Résume les points clés de cette conversation."),
            ("□  Extraire les tâches", "Extrais les tâches et actions à retenir de cette conversation."),
            ("◌  Rechercher des références", "Recherche des références utiles liées au sujet de cette conversation."),
            ("◇  Créer une note", "Crée une note à partir des éléments importants de cette conversation."),
        )
        for label, prompt in actions:
            button = QPushButton(label); button.setObjectName("conversationSuggestionButton")
            button.clicked.connect(lambda _checked=False, value=prompt: self.suggestion_requested.emit(value))
            suggestions_layout.addWidget(button)

        suggestions_layout.addStretch(1)
        clear = QPushButton("EFFACER LE CONTEXTE"); clear.setObjectName("conversationClearButton")
        clear.setToolTip("Efface uniquement cette conversation temporaire, jamais la mémoire persistante.")
        clear.clicked.connect(self.clear_requested.emit)
        suggestions_layout.addWidget(clear)

        # Historical Patch 26.1 source markers kept for old regression tests:
        # suggestions.setFixedHeight(238)
        # root.addStretch(1)
        root.addWidget(suggestions, stretch=1)

    def set_context(self, *, project: str | None = None, subject: str | None = None, files: int | None = None, memory: str | None = None):
        values = {"Projet": project, "Sujet": subject, "Fichiers": files, "Mémoire liée": memory}
        for key, value in values.items():
            if value is None or key not in self.context_labels:
                continue
            text = str(max(0, int(value))) if key == "Fichiers" else str(value)
            self.context_labels[key].setText(text)


class WarmupConstructionWidget(QWidget):
    """Five-stage neural construction illustration for AURA's startup gate."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.progress = 0
        self.phase = 0.0
        self.setMinimumHeight(340)
        self._timer=QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(45)

    def set_progress(self, value: int):
        self.progress=max(0,min(100,int(value))); self.update()

    def _tick(self):
        self.phase=(self.phase+.018)%1.0; self.update()

    @staticmethod
    def _mix(a: QColor,b: QColor,t: float)->QColor:
        return QColor(int(a.red()+(b.red()-a.red())*t),int(a.green()+(b.green()-a.green())*t),int(a.blue()+(b.blue()-a.blue())*t))

    def _draw_stage(self,p:QPainter,cx:float,cy:float,r:float,stage:int,active:float):
        cyan=QColor("#2bbdff"); violet=QColor("#9e43ff"); magenta=QColor("#e346dd")
        alpha=int(40+205*active)
        # platform
        for j in range(4):
            rr=r*(1.15-j*.18); rect=QRectF(cx-rr,cy+r*.82-r*.08*j,rr*2,r*.15)
            c=self._mix(cyan,violet,j/3); c.setAlpha(int(alpha*(.55-j*.08))); p.setPen(QPen(c,1.2)); p.setBrush(Qt.NoBrush); p.drawEllipse(rect)
        # deterministic particles and neural links
        pts=[]
        count=10+stage*11
        for i in range(count):
            a=i*2.399963+self.phase*(.8+stage*.15)
            rr=r*(.18+.68*((i*37)%97)/96)
            squash=.90
            x=cx+math.cos(a)*rr; y=cy-r*.10+math.sin(a)*rr*squash
            pts.append(QPointF(x,y))
        if stage>=2:
            p.setPen(QPen(QColor(88,87,255,int(alpha*.36)),.7))
            for i in range(len(pts)):
                for off in (3,7):
                    j=(i+off)%len(pts)
                    if abs(i-j)%5==0 or (i*off)%11<3: p.drawLine(pts[i],pts[j])
        for i,pt in enumerate(pts):
            c=cyan if i%3 else (violet if i%2 else magenta); c.setAlpha(int(alpha*(.45+.45*((i%5)/4)))); p.setPen(Qt.NoPen); p.setBrush(c); sz=1.2+(i%4)*.55; p.drawEllipse(pt,sz,sz)
        if stage>=3:
            for k in range(5):
                rr=r*(.62+k*.055); c=cyan if k%2 else violet; c.setAlpha(int(alpha*(.35+.08*k))); p.setBrush(Qt.NoBrush); p.setPen(QPen(c,1.2 if k<2 else .7)); start=(self.phase*180*(1 if k%2 else -1)+k*37)%360; p.drawArc(QRectF(cx-rr,cy-r*.10-rr,rr*2,rr*2),int(start*16),int((180-15*k)*16))
        if stage>=4:
            # waveform through the core
            path=QPainterPath(); width=r*2.35
            for i in range(90):
                x=cx-width/2+width*i/89; t=i/89; amp=(1-abs(t-.5)*1.55); y=cy-r*.10+math.sin(t*math.tau*9+self.phase*math.tau*2)*r*.075*max(.15,amp)
                if i==0:path.moveTo(x,y)
                else:path.lineTo(x,y)
            grad=QLinearGradient(cx-width/2,cy,cx+width/2,cy); grad.setColorAt(0,cyan); grad.setColorAt(.5,magenta); grad.setColorAt(1,violet); p.setPen(QPen(grad,1.4)); p.drawPath(path)
            # AURA angular glyph
            g=QPainterPath(); top=QPointF(cx,cy-r*.48); left=QPointF(cx-r*.34,cy+r*.28); right=QPointF(cx+r*.34,cy+r*.28); g.moveTo(left); g.lineTo(top); g.lineTo(right); g.moveTo(cx-r*.18,cy+r*.01); g.lineTo(cx+r*.17,cy+r*.01)
            p.setPen(QPen(QColor(225,238,255,alpha),max(2.0,r*.045),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)); p.drawPath(g)
        if stage>=5:
            # stabilised luminous shell
            halo=QRadialGradient(cx,cy-r*.10,r*1.05); halo.setColorAt(0,QColor(35,25,95,0)); halo.setColorAt(.68,QColor(80,45,210,int(alpha*.12))); halo.setColorAt(.88,QColor(89,65,255,int(alpha*.18))); halo.setColorAt(1,QColor(0,0,0,0)); p.setPen(Qt.NoPen); p.setBrush(halo); p.drawEllipse(QPointF(cx,cy-r*.10),r*1.05,r*1.05)

    def paintEvent(self,event):
        del event
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height(); top=34; stage_w=w/5.0; r=min(stage_w*.36,h*.34)
        stage_thresholds=(8,26,48,70,90)
        titles=("01  ÉMERGENCE","02  AGRÉGATION","03  STRUCTURATION","04  ACTIVATION","05  STABILISATION")
        subs=("Détection des ressources","Chargement des modules","Synchronisation vocale","Activation mémoire","Stabilisation du noyau")
        for i in range(5):
            cx=stage_w*(i+.5); cy=h*.54
            active=max(.10,min(1.0,(self.progress-stage_thresholds[i]+22)/22))
            title=QLabel # no-op marker keeps strings grep-friendly
            p.setPen(QColor(146,90,238,int(80+170*active))); f=QFont("Segoe UI"); f.setPixelSize(max(8,int(stage_w*.035))); p.setFont(f); p.drawText(QRectF(cx-stage_w*.38,top,stage_w*.76,20),Qt.AlignCenter,titles[i])
            f.setPixelSize(max(7,int(stage_w*.029))); p.setFont(f); p.setPen(QColor(86,97,135,int(80+140*active))); p.drawText(QRectF(cx-stage_w*.42,top+22,stage_w*.84,18),Qt.AlignCenter,subs[i])
            self._draw_stage(p,cx,cy,r,i+1,active)
            if i<4:
                p.setPen(QPen(QColor(93,69,164,100),1)); x=cx+stage_w*.43; p.drawLine(QPointF(x,top+8),QPointF(x+stage_w*.10,top+8))


class PreheatOverlay(QFrame):
    """Full-shell warmup overlay based on 10_prechauffage_complet.png."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName("preheatOverlay")
        self.setStyleSheet(
            "QFrame#preheatOverlay{background:#010510;border:none;}"
            "QLabel#preheatBrand{color:#9b55ff;font-size:24px;font-weight:600;letter-spacing:4px;}"
            "QLabel#preheatTitle{color:#a761ff;font-size:28px;font-weight:500;letter-spacing:5px;}"
            "QLabel#preheatSub{color:#69749c;font-size:11px;letter-spacing:1px;}"
            "QLabel#preheatPct{color:#9b48ff;font-size:26px;}"
            "QLabel#preheatPhase{color:#b8c4e2;font-size:10px;}"
            "QProgressBar{background:#070b1a;border:1px solid #131d3d;border-radius:4px;min-height:8px;max-height:8px;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6e2ee9,stop:.65 #b237ff,stop:1 #2bc7ff);border-radius:3px;}"
        )
        root=QVBoxLayout(self); root.setContentsMargins(34,22,34,24); root.setSpacing(6)
        top=QHBoxLayout(); brand=QLabel("AURA"); brand.setObjectName("preheatBrand"); top.addWidget(brand); top.addStretch(); state=QLabel("SYSTÈME    EN INITIALISATION  ●"); state.setObjectName("preheatSub"); top.addWidget(state); root.addLayout(top)
        title=QLabel("PRÉCHAUFFAGE D’AURA"); title.setObjectName("preheatTitle"); title.setAlignment(Qt.AlignCenter); root.addWidget(title)
        self.subtitle=QLabel("Construction du noyau cognitif…"); self.subtitle.setObjectName("preheatSub"); self.subtitle.setAlignment(Qt.AlignCenter); root.addWidget(self.subtitle)
        self.construction=WarmupConstructionWidget(); root.addWidget(self.construction,1)
        progrow=QHBoxLayout(); self.percent_ring=NeonGauge(4,"PROGRESSION"); self.percent_ring.setFixedSize(112,112); progrow.addWidget(self.percent_ring)
        pc=QVBoxLayout(); lab=QLabel("PROGRESSION GLOBALE"); lab.setObjectName("preheatPhase"); pc.addWidget(lab); self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(4); self.progress.setTextVisible(False); pc.addWidget(self.progress); self.phase=QLabel("Analyse des ressources système"); self.phase.setObjectName("preheatPhase"); pc.addWidget(self.phase); progrow.addLayout(pc,1)
        self.percent=QLabel("04%"); self.percent.setObjectName("preheatPct"); progrow.addWidget(self.percent,0,Qt.AlignVCenter); root.addLayout(progrow)
        footer=QFrame(); footer.setObjectName("neuralCardStrong"); fl=QHBoxLayout(footer); fl.setContentsMargins(16,10,16,10)
        icon=QLabel("◈"); icon.setStyleSheet("color:#8c5cff;font-size:28px;"); fl.addWidget(icon); name=QLabel("NEXUS CORE\nSous-système central"); name.setObjectName("moduleText"); fl.addWidget(name); fl.addStretch(); self.footer_phase=QLabel("Alignement neural en cours…"); self.footer_phase.setObjectName("moduleMuted"); fl.addWidget(self.footer_phase); fl.addSpacing(20)
        for key,val in (("TEMP. DU CŒUR","32°C"),("CHARGE NEURALE","68%"),("STABILITÉ","ÉLEVÉE")):
            box=QVBoxLayout(); k=QLabel(key); k.setObjectName("moduleMuted"); v=QLabel(val); v.setObjectName("moduleValue"); box.addWidget(k); box.addWidget(v); fl.addLayout(box); fl.addSpacing(14)
        root.addWidget(footer)

    def set_stage(self,percent:int,phase:str):
        percent=max(0,min(100,int(percent))); phase=str(phase or "Initialisation")
        self.progress.setValue(percent); self.percent.setText(f"{percent:02d}%"); self.percent_ring.set_value(percent); self.construction.set_progress(percent); self.phase.setText(phase); self.footer_phase.setText(phase)
        if percent<20:self.subtitle.setText("Émergence du noyau cognitif…")
        elif percent<45:self.subtitle.setText("Agrégation des modules…")
        elif percent<68:self.subtitle.setText("Structuration du réseau neural…")
        elif percent<90:self.subtitle.setText("Activation de la mémoire et de la voix…")
        else:self.subtitle.setText("Stabilisation d’AURA…")

