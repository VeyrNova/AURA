"""AURA final-shell action icons.

Patch 26.8 deliberately uses QPainter vectors instead of emoji/font glyphs so
attachment, microphone and send controls match the final neon interface on
Windows regardless of the installed emoji font.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


_COLORS = {
    "idle": QColor("#8f7ad8"),
    "hover": QColor("#b18cff"),
    "active": QColor("#55dcff"),
    "send": QColor("#d388ff"),
    "disabled": QColor("#46506d"),
}


def _pen(color: QColor, width: float = 1.75) -> QPen:
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _paint_icon(role: str, *, active: bool = False, disabled: bool = False, size: int = 32) -> QPixmap:
    size = max(20, int(size))
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    if disabled:
        color = _COLORS["disabled"]
    elif active:
        color = _COLORS["active"]
    elif role == "send":
        color = _COLORS["send"]
    else:
        color = _COLORS["idle"]

    # Soft neon halo: subtle enough to preserve the thin-line final UI.
    halo = QColor(color)
    halo.setAlpha(55 if active else 30)
    p.setPen(_pen(halo, 4.6))
    _draw_role(p, role, size)
    p.setPen(_pen(color, 1.7 if size <= 32 else 1.9))
    _draw_role(p, role, size)
    p.end()
    return pix


def _draw_role(p: QPainter, role: str, size: int) -> None:
    s = float(size)
    if role == "attach":
        # Two nested rounded curves: a compact, angled paperclip.
        path = QPainterPath(QPointF(s * .60, s * .24))
        path.cubicTo(QPointF(s * .72, s * .12), QPointF(s * .88, s * .23), QPointF(s * .78, s * .35))
        path.lineTo(QPointF(s * .46, s * .68))
        path.cubicTo(QPointF(s * .34, s * .80), QPointF(s * .17, s * .72), QPointF(s * .21, s * .55))
        path.cubicTo(QPointF(s * .22, s * .49), QPointF(s * .25, s * .45), QPointF(s * .30, s * .40))
        path.lineTo(QPointF(s * .56, s * .15))
        p.drawPath(path)
        inner = QPainterPath(QPointF(s * .35, s * .45))
        inner.lineTo(QPointF(s * .60, s * .21))
        inner.cubicTo(QPointF(s * .66, s * .15), QPointF(s * .74, s * .22), QPointF(s * .68, s * .28))
        inner.lineTo(QPointF(s * .42, s * .54))
        p.drawPath(inner)
        return

    if role == "microphone":
        capsule = QPainterPath()
        capsule.addRoundedRect(QRectF(s * .39, s * .18, s * .22, s * .40), s * .11, s * .11)
        p.drawPath(capsule)
        arc = QPainterPath(QPointF(s * .29, s * .49))
        arc.cubicTo(QPointF(s * .30, s * .69), QPointF(s * .70, s * .69), QPointF(s * .71, s * .49))
        p.drawPath(arc)
        p.drawLine(QPointF(s * .50, s * .69), QPointF(s * .50, s * .80))
        p.drawLine(QPointF(s * .39, s * .80), QPointF(s * .61, s * .80))
        return

    # send: angular paper plane with open center, matching the final mockup.
    poly = QPolygonF([
        QPointF(s * .20, s * .28),
        QPointF(s * .82, s * .16),
        QPointF(s * .64, s * .82),
        QPointF(s * .47, s * .56),
        QPointF(s * .31, s * .68),
        QPointF(s * .34, s * .48),
        QPointF(s * .20, s * .28),
    ])
    p.drawPolyline(poly)
    p.drawLine(QPointF(s * .34, s * .48), QPointF(s * .72, s * .25))
    p.drawLine(QPointF(s * .47, s * .56), QPointF(s * .72, s * .25))


def aura_action_icon(role: str, *, active: bool = False, disabled: bool = False, size: int = 32) -> QIcon:
    role = str(role or "").strip().casefold()
    if role not in {"attach", "microphone", "send"}:
        role = "send"
    return QIcon(_paint_icon(role, active=active, disabled=disabled, size=size))


def apply_action_icon(button, role: str, *, active: bool = False, disabled: bool = False, size: int = 20) -> None:
    """Apply a themed icon to an existing Qt button without changing its signal wiring."""
    button.setText("")
    button.setIcon(aura_action_icon(role, active=active, disabled=disabled, size=max(24, size + 8)))
    button.setIconSize(QSize(size, size))
    button.setProperty("auraActionRole", role)
