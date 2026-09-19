from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEvent, QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget
)

from ui.map_widget import AuraMapWidget


# PATCH 02 — AURA Weather final visual target: Windy-inspired, AURA-native.
# Regression vocabulary retained from the prior weather workspace:
# ((0,"Maintenant"),(3,"+3 h"),(6,"+6 h"),(12,"+12 h"),(24,"+24 h"))
# map payload markers: "weather_field":field · "preserve_map_zoom":True
# No external font file is shipped. Windows' Bahnschrift is preferred and the
# normal Segoe UI families remain safe fallbacks.
_STYLE = """
QDialog { background:#010611; color:#e8f7ff; font-family:'Bahnschrift SemiCondensed','Bahnschrift','Segoe UI Variable Text','Segoe UI'; }
QFrame#weatherSurface { background:#010711; border:1px solid #0d2941; border-radius:18px; }
QFrame#weatherMapShell { background:#010712; border:1px solid #10334f; border-radius:15px; }
QFrame#weatherPanel { background:#030b17; border:1px solid #173751; border-radius:15px; }
QFrame#weatherGlass { background:rgba(3,15,29,222); border:1px solid #17415d; border-radius:11px; }
QFrame#forecastCard { background:#04111f; border:1px solid #15324b; border-radius:9px; }
QLabel#eyebrow { color:#5de5ff; font-size:9px; font-weight:600; letter-spacing:2px; }
QLabel#title { color:#eefaff; font-size:21px; font-weight:600; letter-spacing:1px; }
QLabel#hero { color:#ffffff; font-size:48px; font-weight:300; }
QLabel#condition { color:#bca4ff; font-size:13px; font-weight:600; letter-spacing:1px; }
QLabel#section { color:#728ca1; font-size:9px; font-weight:650; letter-spacing:1.5px; }
QLabel#muted { color:#7690a5; font-size:9px; }
QLabel#metric { color:#dff5ff; font-size:11px; font-weight:600; }
QLabel#metricValue { color:#62e0ff; font-size:11px; font-weight:650; }
QLabel#timelineTime { color:#d5f8ff; font-size:11px; font-weight:650; letter-spacing:.8px; }
QLineEdit { background:rgba(2,13,26,238); color:#eefbff; border:1px solid #1e6487; border-radius:10px; padding:9px 12px; selection-background-color:#6034bd; font-size:10px; }
QPushButton { background:#06172a; color:#89dff4; border:1px solid #1a4667; border-radius:8px; padding:7px 10px; font-size:9px; font-weight:600; letter-spacing:.4px; }
QPushButton:hover { border-color:#58ddff; background:#08233a; color:#e9fbff; }
QPushButton:checked { background:#26124f; color:#e1c9ff; border-color:#914cff; }
QPushButton#layerButton { min-width:44px; max-width:54px; min-height:42px; padding:5px; }
QPushButton#playButton { min-width:34px; max-width:34px; min-height:30px; max-height:30px; border-radius:15px; }
QPushButton#close { min-width:34px; max-width:34px; min-height:30px; max-height:30px; }
QSlider::groove:horizontal { height:3px; background:#14253b; border-radius:1px; }
QSlider::sub-page:horizontal { background:#44dfff; border-radius:1px; }
QSlider::handle:horizontal { width:11px; margin:-4px 0; background:#b35cff; border:1px solid #e1c8ff; border-radius:5px; }
QScrollArea { background:transparent; border:none; }
QScrollBar:vertical { background:transparent; width:5px; }
QScrollBar::handle:vertical { background:#1c405b; border-radius:2px; min-height:30px; }
"""


class _WeatherWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, aura_core, query: str):
        super().__init__()
        self.aura_core = aura_core
        self.query = str(query or "").strip()

    def run(self):
        try:
            plan = self.aura_core.internet_tools.plan(f"météo à {self.query}")
            if plan is None:
                self.failed.emit("Lieu météo non reconnu.")
                return
            result = self.aura_core.execute_internet_tool(plan)
            # Regional field stays supplemental: a point result must remain usable.
            if getattr(result, "ok", False):
                data = getattr(result, "data", None)
                if isinstance(data, dict) and data.get("latitude") is not None and data.get("longitude") is not None:
                    try:
                        field = self.aura_core.internet_tools.weather.fetch_map_field(
                            float(data["latitude"]), float(data["longitude"]),
                            rows=5, cols=5, lat_span=7.0, forecast_hours=25,
                        )
                        data["weather_field"] = field
                    except Exception as field_exc:
                        data["weather_field_error"] = str(field_exc)[:160]
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc) or "Recherche météo impossible.")


class WeatherWorkspaceDialog(QDialog):
    """Windy-like weather workspace using AURA's existing OSM/Open-Meteo core.

    Composition: ~76% map workspace, ~24% fixed details/forecast panel. The
    sampled Open-Meteo field is explicitly presented as a forecast field, never
    as a true radar product.
    """

    speak_requested = Signal(str)

    def __init__(
        self,
        aura_core,
        parent=None,
        *,
        initial_location: str = "Vidauban",
        initial_data: dict | None = None,
        auto_search: bool = True,
    ):
        super().__init__(parent)
        self.aura_core = aura_core
        self.data: dict = {}
        self._thread = None
        self._worker = None
        self._playing = False
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(900)
        self._play_timer.timeout.connect(self._advance_timeline)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(False)
        self.resize(1540, 900)
        self.setMinimumSize(1180, 700)
        self.setStyleSheet(_STYLE)
        self._build()
        self.search.setText(str(initial_location or ""))
        if initial_data:
            self.present_data(initial_data)
        if auto_search and (not initial_data or not initial_data.get("weather_field")):
            QTimer.singleShot(80, self._run_search)

    # ------------------------------------------------------------------ build
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        surface = QFrame(); surface.setObjectName("weatherSurface")
        root = QVBoxLayout(surface); root.setContentsMargins(12, 10, 12, 12); root.setSpacing(8)
        outer.addWidget(surface)

        # Header
        top = QHBoxLayout(); titles = QVBoxLayout(); titles.setSpacing(0)
        e = QLabel("◉ AURA // WEATHER INTELLIGENCE // LIVE"); e.setObjectName("eyebrow")
        t = QLabel("MÉTÉO EN DIRECT"); t.setObjectName("title")
        titles.addWidget(e); titles.addWidget(t); top.addLayout(titles); top.addStretch()
        self.status = QLabel("OPEN-METEO · PRÊT"); self.status.setObjectName("muted"); top.addWidget(self.status)
        close = QPushButton("×"); close.setObjectName("close"); close.setAutoDefault(False); close.setDefault(False); close.clicked.connect(self.close); top.addWidget(close)
        root.addLayout(top)

        body = QHBoxLayout(); body.setSpacing(10)
        root.addLayout(body, 1)

        # ----------------------------------------------------------- map 76%
        self.map_shell = QFrame(); self.map_shell.setObjectName("weatherMapShell")
        ml = QVBoxLayout(self.map_shell); ml.setContentsMargins(8, 8, 8, 8); ml.setSpacing(7)

        search_row = QHBoxLayout(); search_row.setSpacing(7)
        self.search = QLineEdit(); self.search.setPlaceholderText("Rechercher une ville, un pays ou une région…"); self.search.installEventFilter(self); self.search.setMaximumWidth(430); search_row.addWidget(self.search)
        b = QPushButton("RECHERCHER"); b.setAutoDefault(False); b.setDefault(False); b.clicked.connect(self._run_search); search_row.addWidget(b)
        self.map_source = QLabel("CARTE OSM · PRÉVISION OPEN-METEO"); self.map_source.setObjectName("muted"); search_row.addStretch(); search_row.addWidget(self.map_source)
        ml.addLayout(search_row)

        map_row = QHBoxLayout(); map_row.setSpacing(7)
        self.map_holder = QFrame(); self.map_holder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        mh = QVBoxLayout(self.map_holder); mh.setContentsMargins(0, 0, 0, 0)
        self.map_widget = AuraMapWidget({}, self.map_holder); mh.addWidget(self.map_widget)
        map_row.addWidget(self.map_holder, 1)

        layer_rail = QFrame(); layer_rail.setObjectName("weatherGlass"); layer_rail.setFixedWidth(62)
        lr = QVBoxLayout(layer_rail); lr.setContentsMargins(5, 7, 5, 7); lr.setSpacing(6)
        lbl = QLabel("COUCHES"); lbl.setObjectName("section"); lbl.setAlignment(Qt.AlignCenter); lr.addWidget(lbl)
        self.layer_buttons = {}
        for key, icon, label in (
            ("vent", "≋", "VENT"), ("pluie", "⋰", "PLUIE"),
            ("temperature", "°", "TEMP"), ("nuages", "☁", "NUAGES"),
        ):
            btn = QPushButton(f"{icon}\n{label}"); btn.setObjectName("layerButton"); btn.setCheckable(True); btn.setAutoExclusive(False)
            btn.clicked.connect(lambda checked=False, k=key: self._set_layer(k)); self.layer_buttons[key] = btn; lr.addWidget(btn)
        self.layer_buttons["vent"].setChecked(True); lr.addStretch(); map_row.addWidget(layer_rail)
        ml.addLayout(map_row, 1)

        # Windy-like timeline/playback embedded under the map.
        timeline = QFrame(); timeline.setObjectName("weatherGlass")
        tl = QVBoxLayout(timeline); tl.setContentsMargins(10, 7, 10, 7); tl.setSpacing(4)
        tr = QHBoxLayout(); tr.setSpacing(7)
        self.play = QPushButton("▶"); self.play.setObjectName("playButton"); self.play.clicked.connect(self._toggle_play); tr.addWidget(self.play)
        self.timeline_time = QLabel("MAINTENANT"); self.timeline_time.setObjectName("timelineTime"); self.timeline_time.setFixedWidth(92); tr.addWidget(self.timeline_time)
        self.timeline_slider = QSlider(Qt.Horizontal); self.timeline_slider.setRange(0, 24); self.timeline_slider.setValue(0); self.timeline_slider.valueChanged.connect(self._set_time_offset); tr.addWidget(self.timeline_slider, 1)
        self.timeline_label = QLabel("CHAMP PRÉVISIONNEL · EN ATTENTE"); self.timeline_label.setObjectName("muted"); tr.addWidget(self.timeline_label)
        tl.addLayout(tr)
        shortcuts = QHBoxLayout(); shortcuts.setSpacing(5)
        for offset, label in ((0,"MAINTENANT"),(3,"+3 H"),(6,"+6 H"),(12,"+12 H"),(24,"+24 H")):
            btn=QPushButton(label); btn.clicked.connect(lambda checked=False,o=offset:self.timeline_slider.setValue(o)); shortcuts.addWidget(btn)
        shortcuts.addStretch(); self.legend = QLabel("CARTE ANIMÉE · CHAMP PRÉVISIONNEL 5×5 · PAS UN RADAR"); self.legend.setObjectName("muted"); shortcuts.addWidget(self.legend)
        tl.addLayout(shortcuts); ml.addWidget(timeline)
        body.addWidget(self.map_shell, 3)

        # --------------------------------------------------------- right 24%
        panel = QFrame(); panel.setObjectName("weatherPanel"); panel.setMinimumWidth(330); panel.setMaximumWidth(390)
        pl = QVBoxLayout(panel); pl.setContentsMargins(13, 12, 13, 12); pl.setSpacing(8)
        h = QLabel("CONDITIONS ACTUELLES"); h.setObjectName("section"); pl.addWidget(h)
        self.place = QLabel("—"); self.place.setObjectName("metric"); self.place.setWordWrap(True); pl.addWidget(self.place)
        hero = QHBoxLayout(); self.temp=QLabel("—°C"); self.temp.setObjectName("hero"); hero.addWidget(self.temp); hero.addStretch(); self.condition=QLabel("EN ATTENTE"); self.condition.setObjectName("condition"); self.condition.setAlignment(Qt.AlignRight|Qt.AlignVCenter); self.condition.setWordWrap(True); hero.addWidget(self.condition); pl.addLayout(hero)
        self.feels = QLabel("RESSENTI —"); self.feels.setObjectName("muted"); pl.addWidget(self.feels)

        metrics = QFrame(); metrics.setObjectName("weatherGlass"); self.metrics_grid = QGridLayout(metrics); self.metrics_grid.setContentsMargins(9,8,9,8); self.metrics_grid.setHorizontalSpacing(10); self.metrics_grid.setVerticalSpacing(6); pl.addWidget(metrics)
        self.metric_values = {}
        for i, key in enumerate(("VENT","HUMIDITÉ","PRESSION","PLUIE","VISIBILITÉ","POINT ROSÉE")):
            lab=QLabel(key); lab.setObjectName("muted"); val=QLabel("—"); val.setObjectName("metricValue"); val.setAlignment(Qt.AlignRight); self.metrics_grid.addWidget(lab,i,0); self.metrics_grid.addWidget(val,i,1); self.metric_values[key]=val

        hh = QLabel("PROCHAINES HEURES"); hh.setObjectName("section"); pl.addWidget(hh)
        self.hourly_strip = QFrame(); self.hourly_strip.setObjectName("weatherGlass"); self.hourly_layout=QHBoxLayout(self.hourly_strip); self.hourly_layout.setContentsMargins(6,6,6,6); self.hourly_layout.setSpacing(4); pl.addWidget(self.hourly_strip)

        dh = QLabel("PRÉVISIONS · 8 JOURS"); dh.setObjectName("section"); pl.addWidget(dh)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); daily_host=QWidget(); self.daily_layout=QVBoxLayout(daily_host); self.daily_layout.setContentsMargins(0,0,0,0); self.daily_layout.setSpacing(5); scroll.setWidget(daily_host); pl.addWidget(scroll, 1)

        self.summary = QLabel(""); self.summary.setObjectName("muted"); self.summary.setWordWrap(True); self.summary.hide(); pl.addWidget(self.summary)
        speak=QPushButton("▶  LIRE LE RÉSUMÉ"); speak.setAutoDefault(False); speak.setDefault(False); speak.clicked.connect(self._speak); pl.addWidget(speak)
        body.addWidget(panel, 1)

    # ---------------------------------------------------------------- events
    def eventFilter(self, watched, event):
        if watched is self.search and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._run_search(); event.accept(); return True
        return super().eventFilter(watched, event)

    def accept(self):
        return None

    # --------------------------------------------------------------- retrieval
    def _run_search(self):
        query = self.search.text().strip()
        if not query or self._thread is not None:
            return
        self.status.setText("RECHERCHE MÉTÉO…")
        self._thread = QThread(self); self._worker = _WeatherWorker(self.aura_core, query); self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run); self._worker.finished.connect(self._on_result); self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit); self._worker.failed.connect(self._thread.quit); self._thread.finished.connect(self._cleanup_worker); self._thread.start()

    def _cleanup_worker(self):
        if self._worker: self._worker.deleteLater()
        if self._thread: self._thread.deleteLater()
        self._worker=None; self._thread=None

    def _on_failed(self, message):
        self.status.setText("ERREUR · " + str(message)[:90])

    def _on_result(self, result):
        if not getattr(result, "ok", False):
            self._on_failed(getattr(result, "answer", "Recherche impossible")); return
        data = dict(getattr(result, "data", {}) or {})
        spoken = str(getattr(result,"speech_response","") or getattr(result,"spoken","") or getattr(result,"response","") or getattr(result,"answer",""))
        self.present_data(data, spoken=spoken)

    # --------------------------------------------------------------- rendering
    def present_data(self, data: dict, *, spoken: str = "") -> None:
        self.data = dict(data or {})
        d = self.data
        label = str(d.get("place_label") or d.get("location") or "")
        if label: self.search.setText(label); self.place.setText(label)
        self.status.setText("OPEN-METEO · ACTUALISÉ " + datetime.now().strftime("%H:%M"))
        self.temp.setText(f"{_n(d.get('temperature'))}°C")
        self.condition.setText(str(d.get("condition") or "").upper() or "—")
        self.feels.setText(f"RESSENTI  {_n(d.get('apparent'))}°C")
        self.metric_values["VENT"].setText(f"{_n(d.get('wind_speed'))} km/h")
        self.metric_values["HUMIDITÉ"].setText(f"{_n(d.get('humidity'))}%")
        self.metric_values["PRESSION"].setText(f"{_n(d.get('pressure'))} hPa")
        self.metric_values["PLUIE"].setText(f"{_n(d.get('rain_probability_now'))}%")
        self.metric_values["VISIBILITÉ"].setText(f"{_n(d.get('visibility_km'))} km")
        self.metric_values["POINT ROSÉE"].setText(f"{_n(d.get('dew_point'))}°C")
        if spoken: self.summary.setText(spoken)

        old = self.map_widget; old.setParent(None); old.deleteLater()
        field = dict(d.get("weather_field") or {})
        map_data = {
            "latitude": d.get("latitude"), "longitude": d.get("longitude"),
            "destination_coordinates": (d.get("latitude"), d.get("longitude")),
            "map_zoom": 7, "preserve_map_zoom": True,
            "weather_data": d, "weather_layer": self._active_layer(),
            "weather_field": field, "weather_time_offset": self.timeline_slider.value(),
        }
        self.map_widget = AuraMapWidget(map_data, self.map_holder); self.map_holder.layout().addWidget(self.map_widget)
        self.timeline_slider.setEnabled(bool(field))
        if field:
            count = len(field.get("points") or [])
            self.timeline_label.setText(f"CHAMP {count} POINTS · OPEN-METEO")
            self.legend.setText(f"CARTE ANIMÉE · CHAMP PRÉVISIONNEL {count} POINTS · PAS UN RADAR")
            self.timeline_label.setToolTip("")
        else:
            error = str(d.get("weather_field_error") or "").strip()
            self.timeline_label.setText("CHAMP RÉGIONAL EN COURS / INDISPONIBLE")
            self.timeline_label.setToolTip(error)
            if error: self.status.setText("OPEN-METEO · CHAMP RÉGIONAL INDISPONIBLE")
        self._render_hourly(); self._render_daily(); self._set_time_offset(self.timeline_slider.value())

    def _active_layer(self):
        for key, btn in self.layer_buttons.items():
            if btn.isChecked(): return key
        return "vent"

    def _set_layer(self, key):
        for k,b in self.layer_buttons.items(): b.setChecked(k == key)
        self.map_widget.set_weather_layer(key, self.data)

    def _set_time_offset(self, offset: int):
        offset = max(0, min(24, int(offset)))
        if self.timeline_slider.value() != offset: self.timeline_slider.blockSignals(True); self.timeline_slider.setValue(offset); self.timeline_slider.blockSignals(False)
        try: self.map_widget.set_weather_time_offset(offset)
        except Exception: pass
        field = self.data.get("weather_field") or {}; times = field.get("times") or []
        stamp = times[offset] if offset < len(times) else ""
        suffix = str(stamp)[11:16] if stamp else ("Maintenant" if offset == 0 else f"+{offset} h")
        self.timeline_time.setText(suffix.upper())
        if field: self.timeline_label.setText(f"PRÉVISION T+{offset:02d}H · {suffix} · OPEN-METEO")

    def _toggle_play(self):
        self._playing = not self._playing
        self.play.setText("Ⅱ" if self._playing else "▶")
        if self._playing: self._play_timer.start()
        else: self._play_timer.stop()

    def _advance_timeline(self):
        nxt = self.timeline_slider.value() + 1
        if nxt > 24: nxt = 0
        self.timeline_slider.setValue(nxt)

    def _clear_layout(self, layout):
        while layout.count():
            item=layout.takeAt(0); w=item.widget()
            if w: w.deleteLater()

    def _render_hourly(self):
        self._clear_layout(self.hourly_layout)
        rows = list(self.data.get("hourly_forecast") or [])[:6]
        for row in rows:
            card=QFrame(); card.setObjectName("forecastCard"); lay=QVBoxLayout(card); lay.setContentsMargins(5,5,5,5); lay.setSpacing(1)
            tm=QLabel(str(row.get("time") or "")[11:16] or "—"); tm.setObjectName("muted"); tm.setAlignment(Qt.AlignCenter); lay.addWidget(tm)
            te=QLabel(f"{_n(row.get('temperature'))}°"); te.setObjectName("metric"); te.setAlignment(Qt.AlignCenter); lay.addWidget(te)
            ra=QLabel(f"☂ {_n(row.get('rain_probability'))}%"); ra.setObjectName("muted"); ra.setAlignment(Qt.AlignCenter); lay.addWidget(ra)
            self.hourly_layout.addWidget(card)
        self.hourly_layout.addStretch(1)

    def _render_daily(self):
        self._clear_layout(self.daily_layout)
        for row in list(self.data.get("daily_forecast") or [])[:8]:
            card=QFrame(); card.setObjectName("forecastCard"); lay=QHBoxLayout(card); lay.setContentsMargins(8,7,8,7); lay.setSpacing(7)
            date=QLabel(str(row.get("date") or "")[-5:] or "—"); date.setObjectName("muted"); date.setFixedWidth(40); lay.addWidget(date)
            temps=QLabel(f"{_n(row.get('temp_max'))}°  /  {_n(row.get('temp_min'))}°"); temps.setObjectName("metric"); lay.addWidget(temps,1)
            rain=QLabel(f"☂ {_n(row.get('rain_probability'))}%"); rain.setObjectName("metricValue"); lay.addWidget(rain)
            self.daily_layout.addWidget(card)
        self.daily_layout.addStretch(1)

    def _speak(self):
        text=self.summary.text().strip()
        if text: self.speak_requested.emit(text)


def _n(v):
    try: return str(int(round(float(v))))
    except Exception: return "—"


class ApplicationsDialog(QDialog):
    weather_requested = Signal()
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowFlags(Qt.Dialog|Qt.FramelessWindowHint); self.setModal(False); self.resize(650,360); self.setStyleSheet(_STYLE)
        root=QVBoxLayout(self); top=QHBoxLayout(); title=QLabel("APPLICATIONS AURA"); title.setObjectName("title"); top.addWidget(title); top.addStretch(); close=QPushButton("×"); close.clicked.connect(self.close); top.addWidget(close); root.addLayout(top)
        grid=QGridLayout(); weather=QPushButton("☁  MÉTÉO\nCarte · prévisions · recherche libre"); weather.setMinimumHeight(90); weather.clicked.connect(self.weather_requested.emit); grid.addWidget(weather,0,0)
        for i,(name,desc) in enumerate((("TÂCHES","Gestion locale"),("NOTES","Mémoire écrite"),("RAPPELS","Planification"),("RECHERCHE WEB","Internet contrôlé")),start=1):
            b=QPushButton(f"{name}\n{desc}"); b.setMinimumHeight(90); b.setEnabled(False); grid.addWidget(b,i//2,i%2)
        root.addLayout(grid); root.addStretch(1)
