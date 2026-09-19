from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QPushButton, QWidget

from config.settings import settings
from tools.map_projection import TILE_SIZE as _TILE_SIZE, clamp as _clamp, geo_to_world_xy, world_xy_to_geo


def geo_to_world(lat: float, lon: float, zoom: int) -> QPointF:
    x, y = geo_to_world_xy(lat, lon, zoom)
    return QPointF(x, y)


def world_to_geo(x: float, y: float, zoom: int) -> tuple[float, float]:
    return world_xy_to_geo(x, y, zoom)


def _fmt_map(value) -> str:
    try:
        return f"{float(value):.0f}"
    except Exception:
        return "—"


def _coerce_point(value) -> tuple[float, float] | None:
    try:
        if isinstance(value, dict):
            return float(value["lat"]), float(value["lon"])
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return float(value[0]), float(value[1])
    except Exception:
        return None
    return None


class AuraMapWidget(QWidget):
    """Native Qt slippy-map surface for AURA.

    The map uses fixed OpenStreetMap raster tile URLs through Qt's asynchronous
    network stack. Only the visible tiles are requested, and Qt's disk cache is
    enabled under AURA's temp directory. User text never becomes a tile URL.
    """

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = dict(data or {})
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._min_zoom = int(getattr(settings, "MAPS_MIN_ZOOM", 3))
        self._max_zoom = int(getattr(settings, "MAPS_MAX_ZOOM", 19))
        self.zoom = int(_clamp(self.data.get("map_zoom", 12), self._min_zoom, self._max_zoom))
        self.center_lat = float(self.data.get("latitude") or 43.5)
        self.center_lon = float(self.data.get("longitude") or 6.5)
        self._drag_last: QPoint | None = None
        self._tile_pixmaps: dict[tuple[int, int, int], QPixmap] = {}
        self._pending_tiles: set[tuple[int, int, int]] = set()
        self.weather_layer = str(self.data.get("weather_layer") or "temperature")
        self.weather_data = dict(self.data.get("weather_data") or {})
        self.weather_field = dict(self.data.get("weather_field") or {})
        self.weather_time_offset = max(0, int(self.data.get("weather_time_offset") or 0))

        self.route_points: list[tuple[float, float]] = []
        for item in self.data.get("route_points") or []:
            point = _coerce_point(item)
            if point is not None:
                self.route_points.append(point)
        self.origin_point = _coerce_point(self.data.get("origin_coordinates"))
        self.destination_point = _coerce_point(self.data.get("destination_coordinates"))
        if self.destination_point is None and self.data.get("latitude") is not None and self.data.get("longitude") is not None:
            self.destination_point = (float(self.data["latitude"]), float(self.data["longitude"]))

        self._network = QNetworkAccessManager(self)
        cache = QNetworkDiskCache(self._network)
        cache_dir = Path(settings.CACHE_DIR) / "map_tiles"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.setCacheDirectory(str(cache_dir))
        cache.setMaximumCacheSize(int(getattr(settings, "MAPS_TILE_CACHE_MB", 96)) * 1024 * 1024)
        self._network.setCache(cache)

        self._plus = self._make_control("+")
        self._minus = self._make_control("−")
        self._recenter = self._make_control("⌖")
        self._plus.clicked.connect(self.zoom_in)
        self._minus.clicked.connect(self.zoom_out)
        self._recenter.clicked.connect(self.fit_route)

        self._anim_phase = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(120)
        self._anim_timer.timeout.connect(self._advance_animation)
        self._anim_timer.start()

        QTimer.singleShot(0, self._initial_view)

    def _make_control(self, text: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setFixedSize(34, 34)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton{background:rgba(3,18,32,225);color:#dff9ff;border:1px solid #1685aa;"
            "border-radius:8px;font:600 16px 'Segoe UI';padding:0;}"
            "QPushButton:hover{background:#08334d;border-color:#40e3ff;}"
        )
        button.raise_()
        return button

    def _initial_view(self):
        if self.route_points or (self.origin_point and self.destination_point):
            self.fit_route()
        elif self.destination_point:
            self.center_lat, self.center_lon = self.destination_point
            if not bool(self.data.get("preserve_map_zoom", False)):
                self.zoom = int(_clamp(getattr(settings, "MAPS_LOCATION_ZOOM", 13), self._min_zoom, self._max_zoom))
            self.update()


    def set_weather_layer(self, layer: str, weather_data: dict | None = None):
        self.weather_layer = str(layer or "temperature").casefold()
        if weather_data is not None:
            self.weather_data = dict(weather_data or {})
            if isinstance(self.weather_data.get("weather_field"), dict):
                self.weather_field = dict(self.weather_data.get("weather_field") or {})
        self.update()

    def set_weather_field(self, field: dict | None):
        self.weather_field = dict(field or {})
        self.update()

    def set_weather_time_offset(self, offset: int):
        self.weather_time_offset = max(0, int(offset))
        self.update()

    def _advance_animation(self):
        self._anim_phase = (self._anim_phase + 0.18) % (math.tau * 4.0)
        if self.isVisible():
            self.update()

    def _interpolate_scalar(self, lat: float, lon: float, key: str):
        points = self.weather_field.get("points") or []
        weighted = 0.0
        total = 0.0
        exact = None
        for point in points:
            hour = self._field_hour(point)
            value = hour.get(key)
            if value is None:
                continue
            try:
                plat = float(point.get("latitude"))
                plon = float(point.get("longitude"))
                value_f = float(value)
            except Exception:
                continue
            dist = math.hypot((plat - lat) * 1.25, (plon - lon) * max(0.40, abs(math.cos(math.radians(lat)))))
            if dist < 1e-5:
                exact = value_f
                break
            weight = 1.0 / (dist * dist + 1e-6)
            weighted += value_f * weight
            total += weight
        if exact is not None:
            return exact
        if total <= 0.0:
            return None
        return weighted / total

    def _interpolate_wind(self, lat: float, lon: float) -> tuple[float | None, float | None]:
        points = self.weather_field.get("points") or []
        sum_u = 0.0
        sum_v = 0.0
        total = 0.0
        for point in points:
            hour = self._field_hour(point)
            speed = hour.get("wind_speed")
            direction = hour.get("wind_direction")
            if speed is None or direction is None:
                continue
            try:
                plat = float(point.get("latitude"))
                plon = float(point.get("longitude"))
                speed_f = float(speed)
                direction_f = float(direction)
            except Exception:
                continue
            dist = math.hypot((plat - lat) * 1.25, (plon - lon) * max(0.40, abs(math.cos(math.radians(lat)))))
            if dist < 1e-5:
                return speed_f, direction_f
            weight = 1.0 / (dist * dist + 1e-6)
            to_rad = math.radians((direction_f + 180.0) % 360.0)
            sum_u += math.sin(to_rad) * speed_f * weight
            sum_v += -math.cos(to_rad) * speed_f * weight
            total += weight
        if total <= 0.0:
            return None, None
        u = sum_u / total
        v = sum_v / total
        speed_f = math.hypot(u, v)
        if speed_f <= 1e-6:
            return 0.0, 0.0
        to_deg = (math.degrees(math.atan2(u, -v)) + 360.0) % 360.0
        from_deg = (to_deg - 180.0) % 360.0
        return speed_f, from_deg

    def _screen_to_geo(self, x: float, y: float) -> tuple[float, float]:
        center = geo_to_world(self.center_lat, self.center_lon, self.zoom)
        world = QPointF(center.x() + x - self.width() * 0.5, center.y() + y - self.height() * 0.5)
        return world_to_geo(world.x(), world.y(), self.zoom)

    @staticmethod
    def _temperature_color(value) -> QColor:
        try:
            v = float(value)
        except Exception:
            v = 15.0
        if v <= 0:
            return QColor(72, 95, 255, 100)
        if v <= 10:
            return QColor(52, 170, 255, 100)
        if v <= 20:
            return QColor(48, 224, 190, 100)
        if v <= 28:
            return QColor(255, 213, 69, 105)
        if v <= 35:
            return QColor(255, 132, 46, 110)
        return QColor(242, 69, 91, 118)

    def _field_hour(self, point: dict) -> dict:
        hours = point.get("hours") or []
        if not hours:
            return {}
        index = min(self.weather_time_offset, len(hours) - 1)
        return dict(hours[index] or {})

    def _draw_wind_arrow(self, painter: QPainter, pos: QPointF, speed, direction):
        try:
            speed_f = max(0.0, float(speed))
            direction_f = float(direction)
        except Exception:
            return
        # Open-Meteo uses meteorological direction (where wind comes FROM).
        # Convert it to a screen vector showing where the air is moving TO.
        to_rad = math.radians((direction_f + 180.0) % 360.0)
        dx = math.sin(to_rad); dy = -math.cos(to_rad)
        length = 12.0 + min(speed_f, 70.0) * 0.40
        start = QPointF(pos.x() - dx * length * 0.40, pos.y() - dy * length * 0.40)
        end = QPointF(pos.x() + dx * length * 0.60, pos.y() + dy * length * 0.60)
        color = QColor(91, 242, 224, 210)
        painter.setPen(QPen(QColor(0, 18, 28, 190), 5, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(start, end)
        painter.setPen(QPen(color, 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(start, end)
        head = 6.0
        perp_x, perp_y = -dy, dx
        back = QPointF(end.x() - dx * head, end.y() - dy * head)
        painter.drawLine(end, QPointF(back.x() + perp_x * 4.0, back.y() + perp_y * 4.0))
        painter.drawLine(end, QPointF(back.x() - perp_x * 4.0, back.y() - perp_y * 4.0))

    def _draw_weather_field(self, painter: QPainter) -> bool:
        """Render the sampled regional forecast field returned by Open-Meteo.

        The source remains a 5×5 sampled Open-Meteo forecast field, but the
        viewport is filled through inverse-distance interpolation so every
        visible area shows conditions. A lightweight animation layer gives the
        Weather Workspace a Windy-like sense of motion without claiming radar.
        """
        field = self.weather_field or {}
        points = field.get("points") or []
        if len(points) < 4:
            return False
        layer = self.weather_layer
        visible_values = []

        step = max(34, min(52, int(min(self.width(), self.height()) / 16)))
        painter.setPen(Qt.NoPen)
        for y in range(0, self.height() + step, step):
            for x in range(0, self.width() + step, step):
                lat, lon = self._screen_to_geo(x + step * 0.5, y + step * 0.5)
                pulse = 0.94 + 0.06 * math.sin(self._anim_phase + (x * 0.012) + (y * 0.007))
                if layer == "pluie":
                    value = self._interpolate_scalar(lat, lon, "rain_probability")
                    try:
                        pct = max(0.0, min(100.0, float(value)))
                    except Exception:
                        pct = 0.0
                    alpha = int((pct * 1.55) * pulse)
                    color = QColor(61, 103, 255, max(0, min(210, alpha)))
                    visible_values.append(pct)
                elif layer == "nuages":
                    value = self._interpolate_scalar(lat, lon, "cloud_cover")
                    try:
                        pct = max(0.0, min(100.0, float(value)))
                    except Exception:
                        pct = 0.0
                    alpha = int((pct * 1.15) * pulse)
                    color = QColor(170, 188, 210, max(0, min(175, alpha)))
                    visible_values.append(pct)
                elif layer == "vent":
                    speed, _direction = self._interpolate_wind(lat, lon)
                    try:
                        spd = max(0.0, float(speed))
                    except Exception:
                        spd = 0.0
                    alpha = int((30 + min(spd, 70.0) * 1.55) * pulse)
                    color = QColor(40, 214, 188, max(18, min(185, alpha)))
                    visible_values.append(spd)
                else:
                    value = self._interpolate_scalar(lat, lon, "temperature")
                    color = self._temperature_color(value)
                    color.setAlpha(max(118, min(172, int(148 * pulse))))
                    try:
                        visible_values.append(float(value))
                    except Exception:
                        pass
                painter.setBrush(color)
                painter.drawRect(QRectF(x, y, step + 1, step + 1))

        positions = [self._screen_point(float(p["latitude"]), float(p["longitude"])) for p in points]
        cols = max(2, int(field.get("cols") or 5))
        distances = []
        for i, pos in enumerate(positions):
            if (i % cols) + 1 < cols and i + 1 < len(positions):
                distances.append(abs(positions[i+1].x() - pos.x()))
            if i + cols < len(positions):
                distances.append(abs(positions[i+cols].y() - pos.y()))
        spacing = max([d for d in distances if d > 1.0] or [110.0])
        radius = max(48.0, min(240.0, spacing * 0.78))
        for point, pos in zip(points, positions):
            hour = self._field_hour(point)
            if not hour:
                continue
            if layer == "pluie":
                try: pct = max(0.0, min(100.0, float(hour.get("rain_probability"))))
                except Exception: pct = 0.0
                color = QColor(61, 103, 255, int(24 + pct * 0.55))
            elif layer == "nuages":
                try: pct = max(0.0, min(100.0, float(hour.get("cloud_cover"))))
                except Exception: pct = 0.0
                color = QColor(170, 188, 210, int(20 + pct * 0.40))
            elif layer == "vent":
                try: spd = max(0.0, float(hour.get("wind_speed")))
                except Exception: spd = 0.0
                color = QColor(40, 214, 188, int(18 + min(spd, 70.0) * 0.45))
            else:
                color = self._temperature_color(hour.get("temperature"))
                color.setAlpha(72)
            grad = QRadialGradient(pos, radius)
            grad.setColorAt(0.0, color)
            grad.setColorAt(0.75, QColor(color.red(), color.green(), color.blue(), int(color.alpha() * 0.38)))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(grad)
            painter.drawEllipse(pos, radius, radius)

        if layer == "vent":
            for point, pos in zip(points, positions):
                hour = self._field_hour(point)
                self._draw_wind_arrow(painter, pos, hour.get("wind_speed"), hour.get("wind_direction"))
            painter.setPen(QPen(QColor(225, 250, 255, 145), 1.2, Qt.SolidLine, Qt.RoundCap))
            for idx in range(64):
                seed_x = (idx * 97) % max(1, self.width())
                seed_y = (idx * 53) % max(1, self.height())
                lat, lon = self._screen_to_geo(seed_x, seed_y)
                speed, direction = self._interpolate_wind(lat, lon)
                if speed is None or direction is None:
                    continue
                to_rad = math.radians((float(direction) + 180.0) % 360.0)
                speed_norm = min(1.0, max(0.0, float(speed) / 45.0))
                drift = (self._anim_phase * (18.0 + speed_norm * 42.0) + idx * 11.0) % 80.0
                x = (seed_x + math.sin(to_rad) * drift) % max(1.0, float(self.width()))
                y = (seed_y - math.cos(to_rad) * drift) % max(1.0, float(self.height()))
                end = QPointF(x + math.sin(to_rad) * (10.0 + speed_norm * 14.0), y - math.cos(to_rad) * (10.0 + speed_norm * 14.0))
                painter.drawLine(QPointF(x, y), end)
        elif layer == "pluie":
            painter.setPen(QPen(QColor(208, 232, 255, 130), 1.0, Qt.SolidLine, Qt.RoundCap))
            for idx in range(130):
                seed_x = (idx * 71) % max(1, self.width())
                seed_y = (idx * 47) % max(1, self.height())
                lat, lon = self._screen_to_geo(seed_x, seed_y)
                pct = self._interpolate_scalar(lat, lon, "rain_probability")
                try:
                    prob = max(0.0, min(100.0, float(pct)))
                except Exception:
                    prob = 0.0
                if prob < 12.0:
                    continue
                speed, direction = self._interpolate_wind(lat, lon)
                direction = float(direction or 200.0)
                to_rad = math.radians((direction + 180.0) % 360.0)
                fall = 26.0 + prob * 0.08
                drift = (self._anim_phase * (22.0 + prob * 0.05) + idx * 9.0) % max(24.0, float(self.height()) + 20.0)
                x = (seed_x + math.sin(to_rad) * (drift * 0.25)) % max(1.0, float(self.width()))
                y = (seed_y + drift) % max(1.0, float(self.height()))
                dx = math.sin(to_rad) * 3.5
                dy = min(16.0, fall * 0.32)
                painter.drawLine(QPointF(x, y), QPointF(x + dx, y + dy))
        elif layer == "nuages":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(240, 247, 255, 18))
            for idx in range(36):
                base_x = (idx * 131) % max(1, self.width())
                base_y = (idx * 79) % max(1, self.height())
                lat, lon = self._screen_to_geo(base_x, base_y)
                cover = self._interpolate_scalar(lat, lon, "cloud_cover")
                try:
                    pct = max(0.0, min(100.0, float(cover)))
                except Exception:
                    pct = 0.0
                if pct < 8.0:
                    continue
                speed, direction = self._interpolate_wind(lat, lon)
                direction = float(direction or 260.0)
                to_rad = math.radians((direction + 180.0) % 360.0)
                drift = (self._anim_phase * (4.0 + (float(speed or 0.0) * 0.08)) + idx * 6.0) % max(36.0, float(self.width()) + 120.0)
                x = (base_x + math.sin(to_rad) * drift) % max(1.0, float(self.width()))
                y = (base_y - math.cos(to_rad) * drift * 0.22) % max(1.0, float(self.height()))
                rx = 22.0 + pct * 0.22
                ry = 12.0 + pct * 0.10
                painter.setBrush(QColor(236, 243, 252, min(62, int(10 + pct * 0.30))))
                painter.drawEllipse(QPointF(x, y), rx, ry)
                painter.drawEllipse(QPointF(x + rx * 0.45, y + 2.0), rx * 0.72, ry * 0.82)
        else:
            painter.setPen(QPen(QColor(255, 250, 230, 36), 1.0))
            for idx in range(44):
                seed_x = (idx * 89) % max(1, self.width())
                seed_y = (idx * 61) % max(1, self.height())
                wave = math.sin(self._anim_phase + idx * 0.4)
                painter.drawLine(QPointF(seed_x, seed_y + wave * 3.0), QPointF(seed_x + 18.0, seed_y - wave * 3.0))

        names = {"temperature":"TEMPÉRATURE", "pluie":"PLUIE", "nuages":"NUAGES", "vent":"VENT"}
        unit = "°C" if layer == "temperature" else ("km/h" if layer == "vent" else "%")
        if visible_values:
            lo, hi = min(visible_values), max(visible_values)
            metric = f"{lo:.0f}–{hi:.0f} {unit}"
        else:
            metric = "—"
        times = field.get("times") or []
        stamp = times[min(self.weather_time_offset, len(times)-1)] if times else ""
        when = str(stamp)[11:16] if stamp else f"T+{self.weather_time_offset}H"
        box = QRectF(self.width()-308, self.height()-78, 290, 56)
        painter.setBrush(QColor(2, 13, 25, 220)); painter.setPen(QPen(QColor(37, 147, 186, 220), 1)); painter.drawRoundedRect(box, 9, 9)
        painter.setPen(QColor(220, 248, 255)); painter.drawText(QRectF(box.x()+10, box.y()+7, box.width()-20, 18), Qt.AlignLeft|Qt.AlignVCenter, f"{names.get(layer, layer.upper())} · {metric}")
        painter.setPen(QColor(115, 169, 190)); painter.drawText(QRectF(box.x()+10, box.y()+27, box.width()-20, 18), Qt.AlignLeft|Qt.AlignVCenter, f"CARTE ANIMÉE · CHAMP 5×5 · {when} · OPEN-METEO")
        return True

    def _draw_weather_focus(self, painter: QPainter):
        """Draw the selected local weather metric around the searched place.

        This deliberately does not pretend to be a meteorological raster field:
        it is a location-focused overlay based on the verified point forecast.
        Spatial forecast fields can later be layered without changing the UI API.
        """
        if not self.weather_data or not self.destination_point:
            return
        world_center = geo_to_world(self.center_lat, self.center_lon, self.zoom)
        target_world = geo_to_world(self.destination_point[0], self.destination_point[1], self.zoom)
        x = target_world.x() - world_center.x() + self.width() * 0.5
        y = target_world.y() - world_center.y() + self.height() * 0.5
        layer = self.weather_layer
        d = self.weather_data
        if layer == "pluie":
            value = d.get("rain_probability_now")
            color = QColor(55, 105, 255, 105)
            label = f"PLUIE {int(value) if value is not None else 0}%"
        elif layer == "vent":
            value = d.get("wind_speed")
            color = QColor(80, 235, 205, 100)
            label = f"VENT {_fmt_map(value)} km/h"
        elif layer == "nuages":
            rows = d.get("hourly_forecast") or []
            value = rows[0].get("cloud_cover") if rows else None
            color = QColor(165, 184, 205, 92)
            label = f"NUAGES {int(value) if value is not None else 0}%"
        else:
            value = d.get("temperature")
            try:
                v = float(value)
            except Exception:
                v = 20.0
            if v >= 30: color = QColor(255, 142, 45, 100)
            elif v >= 20: color = QColor(255, 205, 65, 92)
            elif v >= 10: color = QColor(65, 210, 210, 90)
            else: color = QColor(80, 120, 255, 95)
            label = f"TEMPÉRATURE {_fmt_map(value)}°C"
        radius = max(70.0, min(160.0, self.width() * 0.13))
        grad = QRadialGradient(QPointF(x, y), radius)
        grad.setColorAt(0.0, color)
        c2 = QColor(color); c2.setAlpha(0)
        grad.setColorAt(1.0, c2)
        painter.setPen(Qt.NoPen); painter.setBrush(grad); painter.drawEllipse(QPointF(x, y), radius, radius)
        painter.setBrush(QColor(2, 15, 28, 220)); painter.setPen(QPen(QColor(71, 221, 255, 220), 1))
        box = QRectF(x + 18, y - 46, 150, 28); painter.drawRoundedRect(box, 7, 7)
        painter.setPen(QColor(224, 249, 255)); painter.drawText(box, Qt.AlignCenter, label)
    # ---------------------------------------------------------- map navigation
    def zoom_in(self):
        self._set_zoom(self.zoom + 1)

    def zoom_out(self):
        self._set_zoom(self.zoom - 1)

    def _set_zoom(self, new_zoom: int, *, anchor: QPointF | None = None):
        new_zoom = int(_clamp(new_zoom, self._min_zoom, self._max_zoom))
        if new_zoom == self.zoom:
            return
        if anchor is None:
            anchor = QPointF(self.width() * 0.5, self.height() * 0.5)
        old_center = geo_to_world(self.center_lat, self.center_lon, self.zoom)
        old_anchor_world = QPointF(
            old_center.x() + anchor.x() - self.width() * 0.5,
            old_center.y() + anchor.y() - self.height() * 0.5,
        )
        anchor_lat, anchor_lon = world_to_geo(old_anchor_world.x(), old_anchor_world.y(), self.zoom)
        self.zoom = new_zoom
        new_anchor_world = geo_to_world(anchor_lat, anchor_lon, self.zoom)
        new_center_world = QPointF(
            new_anchor_world.x() - anchor.x() + self.width() * 0.5,
            new_anchor_world.y() - anchor.y() + self.height() * 0.5,
        )
        self.center_lat, self.center_lon = world_to_geo(new_center_world.x(), new_center_world.y(), self.zoom)
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            steps = 1 if delta > 0 else -1
            self._set_zoom(self.zoom + steps, anchor=event.position())
            event.accept()
            return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._set_zoom(self.zoom + 1, anchor=event.position())
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_last = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_last is not None and (event.buttons() & Qt.LeftButton):
            current = event.position().toPoint()
            delta = current - self._drag_last
            self._drag_last = current
            center = geo_to_world(self.center_lat, self.center_lon, self.zoom)
            center -= QPointF(delta.x(), delta.y())
            self.center_lat, self.center_lon = world_to_geo(center.x(), center.y(), self.zoom)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_last = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        margin = 12
        x = max(0, self.width() - self._plus.width() - margin)
        base_y = max(0, self.height() - margin - self._recenter.height())
        self._recenter.move(x, base_y)
        self._minus.move(x, base_y - self._minus.height() - 6)
        self._plus.move(x, base_y - (self._minus.height() + 6) * 2)
        super().resizeEvent(event)

    def fit_route(self):
        points = list(self.route_points)
        if not points:
            if self.origin_point:
                points.append(self.origin_point)
            if self.destination_point:
                points.append(self.destination_point)
        if not points:
            return
        if len(points) == 1:
            self.center_lat, self.center_lon = points[0]
            self.zoom = int(_clamp(getattr(settings, "MAPS_LOCATION_ZOOM", 13), self._min_zoom, self._max_zoom))
            self.update()
            return

        available_w = max(160.0, self.width() - 120.0)
        available_h = max(140.0, self.height() - 110.0)
        chosen = self._min_zoom
        chosen_center = (points[0][0], points[0][1])
        for zoom in range(self._max_zoom, self._min_zoom - 1, -1):
            worlds = [geo_to_world(lat, lon, zoom) for lat, lon in points]
            min_x = min(p.x() for p in worlds); max_x = max(p.x() for p in worlds)
            min_y = min(p.y() for p in worlds); max_y = max(p.y() for p in worlds)
            if max_x - min_x <= available_w and max_y - min_y <= available_h:
                chosen = zoom
                chosen_center = world_to_geo((min_x + max_x) * 0.5, (min_y + max_y) * 0.5, zoom)
                break
        self.zoom = int(chosen)
        self.center_lat, self.center_lon = chosen_center
        self.update()

    # --------------------------------------------------------------- tile I/O
    def _request_tile(self, z: int, x: int, y: int):
        n = 1 << z
        if y < 0 or y >= n:
            return
        wrapped_x = x % n
        key = (z, wrapped_x, y)
        if key in self._tile_pixmaps or key in self._pending_tiles:
            return
        # Avoid a burst when the user drags very quickly. Missing tiles stay as
        # dark placeholders and are requested on the next paint cycle.
        if len(self._pending_tiles) >= int(getattr(settings, "MAPS_MAX_PENDING_TILES", 18)):
            return
        self._pending_tiles.add(key)
        url = QUrl(f"https://tile.openstreetmap.org/{z}/{wrapped_x}/{y}.png")
        request = QNetworkRequest(url)
        request.setRawHeader(b"User-Agent", b"AURA/0.7.0.15.6.12.2 (+local Qt map)")
        request.setRawHeader(b"Accept", b"image/png,image/*;q=0.8")
        reply = self._network.get(request)
        reply.finished.connect(lambda r=reply, k=key: self._tile_finished(r, k))

    def _tile_finished(self, reply: QNetworkReply, key: tuple[int, int, int]):
        self._pending_tiles.discard(key)
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                raw = bytes(reply.readAll())
                pixmap = QPixmap()
                if raw and pixmap.loadFromData(raw):
                    self._tile_pixmaps[key] = pixmap
        finally:
            reply.deleteLater()
            self.update()

    # --------------------------------------------------------------- rendering
    def _screen_point(self, lat: float, lon: float) -> QPointF:
        center = geo_to_world(self.center_lat, self.center_lon, self.zoom)
        point = geo_to_world(lat, lon, self.zoom)
        return QPointF(
            point.x() - center.x() + self.width() * 0.5,
            point.y() - center.y() + self.height() * 0.5,
        )

    def _draw_tiles(self, painter: QPainter):
        center = geo_to_world(self.center_lat, self.center_lon, self.zoom)
        top_left = QPointF(center.x() - self.width() * 0.5, center.y() - self.height() * 0.5)
        first_x = math.floor(top_left.x() / _TILE_SIZE)
        first_y = math.floor(top_left.y() / _TILE_SIZE)
        last_x = math.floor((top_left.x() + self.width()) / _TILE_SIZE)
        last_y = math.floor((top_left.y() + self.height()) / _TILE_SIZE)
        n = 1 << self.zoom
        for tile_y in range(first_y, last_y + 1):
            if tile_y < 0 or tile_y >= n:
                continue
            for tile_x in range(first_x, last_x + 1):
                draw_x = tile_x * _TILE_SIZE - top_left.x()
                draw_y = tile_y * _TILE_SIZE - top_left.y()
                wrapped_x = tile_x % n
                key = (self.zoom, wrapped_x, tile_y)
                pixmap = self._tile_pixmaps.get(key)
                target = QRectF(draw_x, draw_y, _TILE_SIZE + 1, _TILE_SIZE + 1)
                if pixmap is not None:
                    painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
                else:
                    painter.fillRect(target, QColor("#061522"))
                    self._request_tile(self.zoom, tile_x, tile_y)

    def _draw_route(self, painter: QPainter):
        points = self.route_points
        if len(points) >= 2:
            path = QPainterPath()
            first = self._screen_point(*points[0]); path.moveTo(first)
            for point in points[1:]:
                path.lineTo(self._screen_point(*point))
            painter.setPen(QPen(QColor(0, 10, 18, 210), 9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
            painter.setPen(QPen(QColor("#35d7ff"), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)

        if self.origin_point:
            self._draw_marker(painter, self.origin_point, QColor("#27e8ff"), "A")
        if self.destination_point:
            self._draw_marker(painter, self.destination_point, QColor("#e85cff"), "B" if self.origin_point else "")

    def _draw_marker(self, painter: QPainter, point: tuple[float, float], color: QColor, label: str):
        pos = self._screen_point(*point)
        painter.setBrush(QColor(3, 11, 22, 235)); painter.setPen(QPen(color, 3))
        painter.drawEllipse(pos, 12, 12)
        painter.setBrush(color); painter.setPen(Qt.NoPen); painter.drawEllipse(pos, 5, 5)
        if label:
            painter.setPen(QColor("#effcff")); painter.drawText(QRectF(pos.x()-10, pos.y()-28, 20, 16), Qt.AlignCenter, label)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#03101b"))
        self._draw_tiles(painter)

        # AURA tint: preserve geographical readability while keeping the map in
        # the dark cyan visual language of the shell.
        painter.fillRect(self.rect(), QColor(0, 20, 38, 72))
        if not self._draw_weather_field(painter):
            self._draw_weather_focus(painter)
        self._draw_route(painter)

        painter.setPen(QColor(126, 211, 235, 220))
        painter.drawText(16, 23, f"AURA MAP · OSM · Z{self.zoom}")
        if self.weather_field.get("points"):
            painter.setPen(QColor(83, 201, 225, 205))
            painter.drawText(16, 42, f"MÉTÉO · CHAMP PRÉVISIONNEL · T+{self.weather_time_offset}H")
        painter.setPen(QColor(126, 154, 173, 210))
        attribution = "© OpenStreetMap contributors · Météo: Open-Meteo · MOLETTE: ZOOM · GLISSER: DÉPLACER" if self.weather_field.get("points") else "© OpenStreetMap contributors · MOLETTE: ZOOM · GLISSER: DÉPLACER"
        painter.drawText(16, self.height() - 12, attribution)
