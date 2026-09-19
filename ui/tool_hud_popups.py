from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QLinearGradient, QPainter, QPainterPath, QPen
from ui.map_widget import AuraMapWidget
from tools.maps import format_duration_minutes
from config.settings import settings

from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)


_POPUP_STYLE = """
QDialog { background:#020815; color:#e9f6ff; }
QFrame#hudSurface { background:#04101f; border:1px solid #17658b; border-radius:20px; }
QFrame#weatherCard { background:#061426; border:1px solid #164f72; border-radius:16px; }
QFrame#routeMetric { background:#061426; border:1px solid #123f5e; border-radius:12px; }
QLabel#miniTemp { color:#f5fbff; font:300 44px 'Segoe UI'; }
QLabel#miniCondition { color:#dfefff; font:600 14px 'Segoe UI'; }
QLabel#statusOk { color:#6fffd2; font:600 9px 'Segoe UI'; }
QLabel#eyebrow { color:#62dcff; font:600 10px 'Segoe UI'; letter-spacing:2px; }
QLabel#title { color:#f1f9ff; font:600 22px 'Segoe UI'; }
QLabel#subtitle { color:#7e9ab2; font:500 10px 'Segoe UI'; }
QLabel#bigTemp { color:#f5fbff; font:300 64px 'Segoe UI'; }
QLabel#condition { color:#dfefff; font:600 18px 'Segoe UI'; }
QLabel#metricName { color:#6e8ba5; font:500 9px 'Segoe UI'; }
QLabel#metricValue { color:#eef9ff; font:600 15px 'Segoe UI'; }
QLabel#routeTitle { color:#eef9ff; font:600 18px 'Segoe UI'; }
QLabel#routeText { color:#a9c2d6; font:500 11px 'Segoe UI'; }
QPushButton { background:#06243a; color:#66e5ff; border:1px solid #1685aa; border-radius:10px; padding:8px 14px; font:600 10px 'Segoe UI'; }
QPushButton:hover { background:#09324c; border-color:#35dfff; }
QPushButton#close { min-width:34px; max-width:34px; padding:6px; color:#91aabd; }
"""


def _fmt(value, suffix="", digits=0, empty="—") -> str:
    if value is None:
        return empty
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except Exception:
        return f"{value}{suffix}"


class _WeatherGlyph(QWidget):
    """Lightweight weather glyph animated by its parent HUD timer.

    The widget never owns a timer. ``set_phase`` is driven by the single
    WeatherHudPopup animation clock so the HUD does not create a farm of Qt
    timers or extra OpenGL work.
    """

    def __init__(self, code: int = 0, parent=None):
        super().__init__(parent)
        self.code = int(code or 0)
        self.phase = 0.0
        self.setFixedSize(82, 82)

    def set_phase(self, phase: float) -> None:
        self.phase = float(phase) % 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pulse = 1.0 + 0.055 * __import__('math').sin(self.phase * 6.283185307)
        base = QRectF(9, 9, 64, 64)
        r = QRectF(base.center().x() - 32 * pulse, base.center().y() - 32 * pulse, 64 * pulse, 64 * pulse)
        if self.code in {0, 1}:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, QColor("#ffd331")); g.setColorAt(1, QColor("#ff781f"))
            p.setBrush(g); p.setPen(Qt.NoPen); p.drawEllipse(r)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(98, 220, 255, 115), 1.5))
            halo = r.adjusted(-6, -6, 6, 6)
            p.drawArc(halo, int((self.phase * 360) * 16), 120 * 16)
        else:
            drift = 2.2 * __import__('math').sin(self.phase * 6.283185307)
            p.save(); p.translate(drift, 0)
            p.setPen(QPen(QColor("#55dcff"), 4))
            p.setBrush(QColor(18, 77, 116, 210))
            path = QPainterPath(); path.moveTo(18, 54); path.cubicTo(10, 45, 18, 34, 29, 36)
            path.cubicTo(34, 21, 55, 22, 59, 37); path.cubicTo(74, 37, 77, 55, 64, 60)
            path.lineTo(25, 60); path.cubicTo(20, 60, 18, 58, 18, 54); p.drawPath(path)
            if self.code >= 51:
                p.setPen(QPen(QColor("#8f78ff"), 3))
                rain_shift = int((self.phase * 8) % 5)
                for x in (31, 46, 60):
                    p.drawLine(x, 64 + rain_shift, x-3, 73 + rain_shift)
            p.restore()


class _HudMotionOverlay(QWidget):
    """Non-interactive scan/corner layer for the Jarvis-style HUD motion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.0
        self.entrance = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def set_motion(self, phase: float, entrance: float) -> None:
        self.phase = float(phase) % 1.0
        self.entrance = max(0.0, min(1.0, float(entrance)))
        self.update()

    def paintEvent(self, event):
        if self.entrance <= 0.0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        alpha = int(150 * self.entrance)
        pen = QPen(QColor(62, 220, 255, alpha), 2)
        p.setPen(pen)
        margin, arm = 10, 28
        # Animated avionics/Jarvis corner brackets.
        for x1, y1, sx, sy in ((margin, margin, 1, 1), (w-margin, margin, -1, 1),
                               (margin, h-margin, 1, -1), (w-margin, h-margin, -1, -1)):
            p.drawLine(x1, y1, x1 + sx*arm, y1)
            p.drawLine(x1, y1, x1, y1 + sy*arm)
        # One subtle scanning band; no shader and no independent timer.
        y = int((h + 60) * self.phase) - 30
        grad = QLinearGradient(0, y - 18, 0, y + 18)
        grad.setColorAt(0.0, QColor(44, 208, 255, 0))
        grad.setColorAt(0.5, QColor(44, 208, 255, int(34 * self.entrance)))
        grad.setColorAt(1.0, QColor(44, 208, 255, 0))
        p.fillRect(QRectF(4, y - 18, max(0, w - 8), 36), grad)
        # Moving technical tick near the top edge.
        x = int(42 + (max(1, w - 84) * self.phase))
        p.setPen(QPen(QColor(111, 255, 210, int(105 * self.entrance)), 1))
        p.drawLine(x, 8, min(w - 12, x + 22), 8)


class _AnimatedMetric(QWidget):
    def __init__(self, name: str, value, suffix: str = "", digits: int = 0, parent=None):
        super().__init__(parent)
        self.target = value
        self.suffix = suffix
        self.digits = digits
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(2)
        self.name_label = QLabel(name); self.name_label.setObjectName("metricName")
        self.value_label = QLabel("—" if value is None else _fmt(0, suffix, digits)); self.value_label.setObjectName("metricValue")
        lay.addWidget(self.name_label); lay.addWidget(self.value_label)

    def set_progress(self, progress: float) -> None:
        if self.target is None:
            self.value_label.setText("—")
            return
        try:
            val = float(self.target) * max(0.0, min(1.0, progress))
            self.value_label.setText(_fmt(val, self.suffix, self.digits))
        except Exception:
            self.value_label.setText(str(self.target))


class WeatherHudPopup(QDialog):
    """Detailed weather surface with lightweight Jarvis-style motion.

    Animation intentionally stays in QWidget/QPainter land. The main AURA Orb
    remains the only OpenGL-heavy visual; this popup uses one bounded QTimer.
    """

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = dict(data or {})
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setModal(False)
        self.resize(800, 410)
        self.setStyleSheet(_POPUP_STYLE)
        self._motion_ticks = 0
        self._metric_widgets: list[_AnimatedMetric] = []
        self._glyph: _WeatherGlyph | None = None
        self._hero_temp: QLabel | None = None
        self._hero_target = None
        self._build()
        self._overlay = _HudMotionOverlay(self)
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()
        self._motion_timer = QTimer(self)
        fps = max(8, min(30, int(settings.WEATHER_HUD_ANIMATION_FPS)))
        self._motion_timer.setInterval(max(33, int(1000 / fps)))
        self._motion_timer.timeout.connect(self._advance_motion)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_overlay"):
            self._overlay.setGeometry(self.rect())
            self._overlay.raise_()

    def showEvent(self, event):
        super().showEvent(event)
        if settings.WEATHER_HUD_ANIMATIONS_ENABLED:
            self.setWindowOpacity(0.05)
            self._motion_ticks = 0
            self._motion_timer.start()
        else:
            self.setWindowOpacity(1.0)
            self._set_motion_progress(1.0, 0.0)

    def closeEvent(self, event):
        self._motion_timer.stop()
        super().closeEvent(event)

    def _advance_motion(self) -> None:
        self._motion_ticks += 1
        elapsed = self._motion_ticks * self._motion_timer.interval() / 1000.0
        entrance = min(1.0, elapsed / 0.85)
        # Smoothstep prevents the numerical counters from looking linear/robotic.
        eased = entrance * entrance * (3.0 - 2.0 * entrance)
        phase = (elapsed / 2.8) % 1.0
        self.setWindowOpacity(min(1.0, 0.08 + 0.92 * entrance))
        self._set_motion_progress(eased, phase)
        # After the reveal, reduce redraw frequency while preserving a subtle
        # holographic idle scan. One timer remains active at a low rate.
        if entrance >= 1.0 and self._motion_timer.interval() < 90:
            self._motion_timer.setInterval(90)

    def _set_motion_progress(self, progress: float, phase: float) -> None:
        if self._glyph is not None:
            self._glyph.set_phase(phase)
        if hasattr(self, "_overlay"):
            self._overlay.set_motion(phase, progress)
        for metric in self._metric_widgets:
            metric.set_progress(progress)
        if self._hero_temp is not None and self._hero_target is not None:
            try:
                self._hero_temp.setText(_fmt(float(self._hero_target) * progress, "°C", 0))
            except Exception:
                pass

    def _metric(self, name: str, value, suffix: str = "", digits: int = 0) -> _AnimatedMetric:
        widget = _AnimatedMetric(name, value, suffix, digits, self)
        self._metric_widgets.append(widget)
        return widget

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        surface = QFrame(); surface.setObjectName("hudSurface"); root.addWidget(surface)
        lay = QVBoxLayout(surface); lay.setContentsMargins(22, 18, 22, 18); lay.setSpacing(12)
        top = QHBoxLayout()
        titles = QVBoxLayout(); eyebrow = QLabel("◈ AURA WEATHER INTELLIGENCE // LIVE NODE"); eyebrow.setObjectName("eyebrow")
        title = QLabel("MÉTÉO ACTUELLE" if not self.data.get("tomorrow") else "PRÉVISION DEMAIN"); title.setObjectName("title")
        place = QLabel(str(self.data.get("place_label") or self.data.get("location") or "")); place.setObjectName("subtitle")
        titles.addWidget(eyebrow); titles.addWidget(title); titles.addWidget(place); top.addLayout(titles); top.addStretch()
        close = QPushButton("×"); close.setObjectName("close"); close.clicked.connect(self.close); top.addWidget(close); lay.addLayout(top)

        self._glyph = _WeatherGlyph(self.data.get("weather_code", 0), self)
        if self.data.get("tomorrow"):
            row = QHBoxLayout(); row.setSpacing(18); row.addWidget(self._glyph)
            block = QVBoxLayout(); t = QLabel(f"{_fmt(self.data.get('temp_min'),'°',0)}  →  {_fmt(self.data.get('temp_max'),'°',0)}"); t.setObjectName("bigTemp")
            c = QLabel(str(self.data.get("condition") or "")); c.setObjectName("condition"); block.addWidget(t); block.addWidget(c); row.addLayout(block); row.addStretch(); lay.addLayout(row)
            metrics = [
                ("RISQUE PLUIE MAX", self.data.get("precip_probability"), "%", 0),
                ("MIN", self.data.get("temp_min"), "°C", 0),
                ("MAX", self.data.get("temp_max"), "°C", 0),
            ]
        else:
            row = QHBoxLayout(); row.setSpacing(18); row.addWidget(self._glyph)
            self._hero_target = self.data.get("temperature")
            self._hero_temp = QLabel(_fmt(self.data.get("temperature"), "°C", 0)); self._hero_temp.setObjectName("bigTemp"); row.addWidget(self._hero_temp)
            block = QVBoxLayout(); c = QLabel(str(self.data.get("condition") or "").upper()); c.setObjectName("condition")
            feels = QLabel(f"RESSENTI  {_fmt(self.data.get('apparent'),'°C',0)}   ·   MAX  {_fmt(self.data.get('temp_max'),'°',0)}"); feels.setObjectName("subtitle")
            block.addWidget(c); block.addWidget(feels); row.addLayout(block); row.addStretch(); lay.addLayout(row)
            aqi = self.data.get("european_aqi")
            metrics = [
                ("HUMIDITÉ", self.data.get("humidity"), "%", 0),
                ("RISQUE PLUIE MAINT.", self.data.get("rain_probability_now"), "%", 0),
                ("RISQUE PLUIE JOURNÉE", self.data.get("rain_probability_today_max", self.data.get("precip_probability")), "%", 0),
                ("VENT", self.data.get("wind_speed"), " km/h", 0),
                ("VISIBILITÉ", self.data.get("visibility_km"), " km", 0),
                ("PRESSION", self.data.get("pressure"), " hPa", 0),
                ("QUALITÉ DE L’AIR", aqi, "", 0),
                ("POINT DE ROSÉE", self.data.get("dew_point"), "°", 0),
            ]
        grid = QGridLayout(); grid.setHorizontalSpacing(24); grid.setVerticalSpacing(10)
        columns = 4
        for i, (name, value, suffix, digits) in enumerate(metrics):
            grid.addWidget(self._metric(name, value, suffix, digits), i // columns, i % columns)
        lay.addLayout(grid)
        checked = str(self.data.get("checked_at") or "")
        footer = QLabel("SOURCE · OPEN-METEO" + (f"   ·   {checked[11:16]}" if len(checked) >= 16 else "")); footer.setObjectName("subtitle"); lay.addWidget(footer)


class MapsHudPopup(QDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent); self.data = dict(data or {})
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint); self.setAttribute(Qt.WA_TranslucentBackground, False); self.setModal(False)
        self.resize(980, 650); self.setStyleSheet(_POPUP_STYLE); self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        surface = QFrame(); surface.setObjectName("hudSurface"); root.addWidget(surface)
        lay = QVBoxLayout(surface); lay.setContentsMargins(20,16,20,18); lay.setSpacing(10)
        top = QHBoxLayout(); titles = QVBoxLayout()
        e=QLabel("⌖ AURA GEOLOCATION / ROUTING"); e.setObjectName("eyebrow")
        mode = str(self.data.get("mode") or "location")
        t=QLabel("ITINÉRAIRE" if mode=="directions" else "LOCALISATION"); t.setObjectName("title")
        s=QLabel(str(self.data.get("label") or self.data.get("destination") or self.data.get("query") or "")); s.setObjectName("subtitle")
        titles.addWidget(e); titles.addWidget(t); titles.addWidget(s); top.addLayout(titles); top.addStretch(); close=QPushButton("×"); close.setObjectName("close"); close.clicked.connect(self.close); top.addWidget(close); lay.addLayout(top)
        self.map_widget = AuraMapWidget(self.data, self); lay.addWidget(self.map_widget, 1)
        info=QHBoxLayout(); left=QVBoxLayout()
        rt=QLabel(str(self.data.get("label") or "Destination")); rt.setObjectName("routeTitle"); left.addWidget(rt)
        if mode=="directions":
            origin=str(self.data.get("origin_label") or "Position actuelle de l'appareil")
            destination=str(self.data.get("label") or self.data.get("destination") or "Destination")
            metrics=[]
            if self.data.get("distance_km") is not None:
                metrics.append(f"{_fmt(self.data.get('distance_km'),' km',1)}")
            if self.data.get("duration_min") is not None:
                metrics.append(f"≈ {format_duration_minutes(self.data.get('duration_min'))}")
            summary=("   ·   ".join(metrics) + "\n") if metrics else ""
            detail=QLabel(summary + f"ORIGINE  {origin}\nDESTINATION  {destination}\nMODE  {str(self.data.get('travelmode') or 'driving').upper()}")
        else:
            detail=QLabel(f"LAT  {_fmt(self.data.get('latitude'),'',5)}    LON  {_fmt(self.data.get('longitude'),'',5)}")
        detail.setObjectName("routeText"); left.addWidget(detail); info.addLayout(left); info.addStretch()
        fit_btn=QPushButton("CADRER LE TRAJET" if mode=="directions" else "RECENTRER"); fit_btn.clicked.connect(self.map_widget.fit_route); info.addWidget(fit_btn)
        open_btn=QPushButton("OUVRIR DANS GOOGLE MAPS"); open_btn.clicked.connect(self._open_google_maps); info.addWidget(open_btn); lay.addLayout(info)

    def _open_google_maps(self):
        url = str(self.data.get("google_maps_url") or "").strip()
        if url: QDesktopServices.openUrl(QUrl(url))


class AgentMapsWeatherHudPopup(QDialog):
    """Composite rich surface for Agent Kernel Maps/Route + Weather plans.

    The map remains the exact native AuraMapWidget used by the standalone Maps
    popup, so wheel zoom, drag-pan, recentering, fit-route, tile cache and route
    overlays are preserved. Weather is rendered from the structured observation
    instead of from the agent's aggregated text response.
    """

    def __init__(self, maps_data: dict, weather_data: dict, *, kind: str = "maps_weather", parent=None):
        super().__init__(parent)
        self.maps_data = dict(maps_data or {})
        self.weather_data = dict(weather_data or {})
        self.kind = str(kind or "maps_weather")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setModal(False)
        self.resize(1160, 700)
        self.setStyleSheet(_POPUP_STYLE)
        self._build()

    def _weather_metric(self, name: str, value: str) -> QWidget:
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        n = QLabel(name); n.setObjectName("metricName")
        v = QLabel(value); v.setObjectName("metricValue")
        box.addWidget(n); box.addWidget(v)
        holder = QWidget(); holder.setLayout(box)
        return holder

    def _build_weather_card(self) -> QFrame:
        data = self.weather_data
        card = QFrame(); card.setObjectName("weatherCard")
        lay = QVBoxLayout(card); lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(10)

        eyebrow = QLabel("◈ DESTINATION · MÉTÉO"); eyebrow.setObjectName("eyebrow")
        place = QLabel(str(data.get("place_label") or data.get("location") or self.maps_data.get("label") or ""))
        place.setObjectName("subtitle")
        lay.addWidget(eyebrow); lay.addWidget(place)

        hero = QHBoxLayout(); hero.setSpacing(10)
        hero.addWidget(_WeatherGlyph(data.get("weather_code", 0)))
        text = QVBoxLayout(); text.setSpacing(2)
        if data.get("tomorrow"):
            temp_text = f"{_fmt(data.get('temp_min'),'°',0)} → {_fmt(data.get('temp_max'),'°',0)}"
        else:
            temp_text = _fmt(data.get("temperature"), "°C", 0)
        temp = QLabel(temp_text); temp.setObjectName("miniTemp")
        condition = QLabel(str(data.get("condition") or "").upper()); condition.setObjectName("miniCondition")
        text.addWidget(temp); text.addWidget(condition)
        hero.addLayout(text); hero.addStretch()
        lay.addLayout(hero)

        if data.get("tomorrow"):
            rows = [
                ("PRÉCIPITATIONS", _fmt(data.get("precip_probability"), "%", 0)),
                ("MAX", _fmt(data.get("temp_max"), "°C", 0)),
                ("MIN", _fmt(data.get("temp_min"), "°C", 0)),
            ]
        else:
            rows = [
                ("RESSENTI", _fmt(data.get("apparent"), "°C", 0)),
                ("HUMIDITÉ", _fmt(data.get("humidity"), "%", 0)),
                ("VENT", _fmt(data.get("wind_speed"), " km/h", 0)),
                ("PRESSION", _fmt(data.get("pressure"), " hPa", 0)),
                ("VISIBILITÉ", _fmt(data.get("visibility_km"), " km", 0)),
                ("AQI", _fmt(data.get("european_aqi"), "", 0)),
            ]
        grid = QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(10)
        for i, (name, value) in enumerate(rows):
            grid.addWidget(self._weather_metric(name, value), i // 2, i % 2)
        lay.addLayout(grid)
        lay.addStretch()

        checked = str(data.get("checked_at") or "")
        stamp = checked[11:16] if len(checked) >= 16 else ""
        status = QLabel("DONNÉES VÉRIFIÉES" + (f" · {stamp}" if stamp else "")); status.setObjectName("statusOk")
        lay.addWidget(status)
        return card

    def _build_route_metrics(self) -> QFrame | None:
        if str(self.maps_data.get("mode") or "").casefold() != "directions":
            return None
        frame = QFrame(); frame.setObjectName("routeMetric")
        row = QHBoxLayout(frame); row.setContentsMargins(14, 10, 14, 10); row.setSpacing(24)
        metrics = [
            ("DISTANCE", _fmt(self.maps_data.get("distance_km"), " km", 1)),
            ("DURÉE", "≈ " + format_duration_minutes(self.maps_data.get("duration_min"))),
            ("MODE", str(self.maps_data.get("travelmode") or "driving").upper()),
        ]
        for name, value in metrics:
            row.addWidget(self._weather_metric(name, value))
        row.addStretch()
        return frame

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        surface = QFrame(); surface.setObjectName("hudSurface"); root.addWidget(surface)
        lay = QVBoxLayout(surface); lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(10)

        top = QHBoxLayout(); titles = QVBoxLayout()
        route_mode = str(self.maps_data.get("mode") or "location").casefold() == "directions"
        e = QLabel("⌖ AURA AGENT · VISUAL COMPOSITION"); e.setObjectName("eyebrow")
        title = QLabel("AURA ROUTE INTELLIGENCE" if route_mode else "AURA GEO + WEATHER"); title.setObjectName("title")
        subtitle = QLabel(str(self.maps_data.get("label") or self.weather_data.get("place_label") or "")); subtitle.setObjectName("subtitle")
        titles.addWidget(e); titles.addWidget(title); titles.addWidget(subtitle)
        top.addLayout(titles); top.addStretch()
        close = QPushButton("×"); close.setObjectName("close"); close.clicked.connect(self.close); top.addWidget(close)
        lay.addLayout(top)

        route_metrics = self._build_route_metrics()
        if route_metrics is not None:
            lay.addWidget(route_metrics)

        body = QHBoxLayout(); body.setSpacing(12)
        self.map_widget = AuraMapWidget(self.maps_data, self)
        body.addWidget(self.map_widget, 3)
        body.addWidget(self._build_weather_card(), 1)
        lay.addLayout(body, 1)

        bottom = QHBoxLayout()
        origin = str(self.maps_data.get("origin_label") or "").strip()
        destination = str(self.maps_data.get("label") or self.maps_data.get("destination") or "").strip()
        if route_mode and origin:
            route_text = QLabel(f"{origin}  →  {destination}"); route_text.setObjectName("routeText"); bottom.addWidget(route_text)
        else:
            pos = QLabel(destination or str(self.weather_data.get("place_label") or "")); pos.setObjectName("routeText"); bottom.addWidget(pos)
        bottom.addStretch()
        fit_btn = QPushButton("CADRER LE TRAJET" if route_mode else "RECENTRER")
        fit_btn.clicked.connect(self.map_widget.fit_route); bottom.addWidget(fit_btn)
        open_btn = QPushButton("OUVRIR DANS GOOGLE MAPS"); open_btn.clicked.connect(self._open_google_maps); bottom.addWidget(open_btn)
        lay.addLayout(bottom)

    def _open_google_maps(self):
        url = str(self.maps_data.get("google_maps_url") or "").strip()
        if url:
            QDesktopServices.openUrl(QUrl(url))
