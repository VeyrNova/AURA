from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import subprocess
import random
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# AURA_WEATHER_NATIVE_R20
from weather_bridge import WeatherBridge

def parse_args():
    p = argparse.ArgumentParser(description="AURA Native UI POC 6G — Chromium Fidelity")
    p.add_argument("--backend", choices=("auto","d3d11","opengl","vulkan"), default="auto")
    p.add_argument("--windowed", action="store_true")
    p.add_argument("--orb-fps", type=int, default=40)
    p.add_argument("--core-mode", choices=("legacy", "native"), default="native")
    p.add_argument("--state-dir", help="Required explicit state directory for --core-mode native")
    p.add_argument("--qml-self-check", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--voice-transcript-probe", help=argparse.SUPPRESS)
    return p.parse_args()

args = parse_args()
if args.backend != "auto":
    os.environ["QSG_RHI_BACKEND"] = args.backend

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot, QPointF, QRectF, Qt, QAbstractListModel, QModelIndex
from PySide6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient, QTransform
)
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtWidgets import QApplication
from PySide6.QtQuick import QQuickPaintedItem

try:
    import psutil
except Exception:
    psutil = None


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))

def lerp(a, b, t):
    return a + (b-a)*t

def mix_color(a, b, t):
    return (
        lerp(a[0], b[0], t),
        lerp(a[1], b[1], t),
        lerp(a[2], b[2], t),
    )

def smooth(a, b, x):
    t = clamp((x-a)/max(1e-6, b-a))
    return t*t*(3.0-2.0*t)


class NeuralOrbItem(QQuickPaintedItem):
    stateChanged = Signal()
    lightModeChanged = Signal()
    targetFpsChanged = Signal()
    pcmLevelChanged = Signal()

    TAU = math.pi * 2.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAntialiasing(True)
        self.setFillColor(QColor(0,0,0,0))

        self._state = "IDLE"
        self._light_mode = False
        self._target_fps = max(15, min(60, int(args.orb_fps)))
        self._last = time.perf_counter()
        self._rot = 0.0
        self._pcm = 0.0
        self._prev_pcm = 0.0
        self._accent = 0.0
        self._external_pcm = 0.0
        self._nodes = []
        self._edges = []
        self._stars = []
        self._build_model()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._sync_timer()
        self._timer.start()

    def _sync_timer(self):
        self._timer.setInterval(max(16, int(round(1000.0/self._target_fps))))

    @Property(str, notify=stateChanged)
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        value = str(value or "IDLE").upper()
        if value != self._state:
            self._state = value
            self.stateChanged.emit()
            self.update()

    @Property(bool, notify=lightModeChanged)
    def lightMode(self):
        return self._light_mode

    @lightMode.setter
    def lightMode(self, value):
        value = bool(value)
        if value != self._light_mode:
            self._light_mode = value
            self.lightModeChanged.emit()
            self.update()

    @Property(int, notify=targetFpsChanged)
    def targetFps(self):
        return self._target_fps

    @targetFps.setter
    def targetFps(self, value):
        value = max(15, min(60, int(value)))
        if value != self._target_fps:
            self._target_fps = value
            self._sync_timer()
            self.targetFpsChanged.emit()


    @Property(float, notify=pcmLevelChanged)
    def pcmLevel(self):
        return self._external_pcm

    @pcmLevel.setter
    def pcmLevel(self, value):
        value = clamp(float(value or 0.0))
        if abs(value - self._external_pcm) >= 0.002:
            self._external_pcm = value
            self.pcmLevelChanged.emit()
            self.update()

    def _palette(self):
        if self._light_mode:
            return {
                "cyan": (42,181,193),
                "cyan2": (58,139,165),
                "blue": (58,139,165),
                "violet": (103,188,194),
                "magenta": (66,166,180),
                "white": (238,250,250),
            }
        return {
            "cyan": (99,243,255),
            "cyan2": (59,187,255),
            "blue": (98,135,255),
            "violet": (155,92,255),
            "magenta": (218,92,255),
            "white": (243,250,255),
        }

    @staticmethod
    def _qcolor(rgb, alpha):
        return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(clamp(alpha)*255))

    def _build_model(self):
        # Exact deterministic PRNG from the production P0436 JavaScript:
        # seed=(seed*1664525+1013904223)>>>0; return seed/4294967296
        seed = 0xA0436

        def rnd():
            nonlocal seed
            seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
            return seed / 4294967296.0

        node_count = 348
        golden = math.pi * (3.0 - math.sqrt(5.0))

        nodes = []
        for i in range(node_count):
            u = (i + .5) / node_count
            y = 1.0 - 2.0 * u
            rr = math.sqrt(max(0.0, 1.0 - y*y))
            a = i * golden + (rnd() - .5) * .20
            shell = .72 + rnd() * .27
            nodes.append({
                "x": math.cos(a) * rr * shell,
                "y": y * shell,
                "z": math.sin(a) * rr * shell,
                "size": .55 + rnd() * 1.55,
                "phase": rnd() * self.TAU,
                "birth": .08 + rnd() * .80,
                "color": rnd(),
            })
        self._nodes = nodes

        candidates = []
        for i in range(node_count):
            a = nodes[i]
            for j in range(i + 1, node_count):
                b = nodes[j]
                dx = a["x"] - b["x"]
                dy = a["y"] - b["y"]
                dz = a["z"] - b["z"]
                d = math.sqrt(dx*dx + dy*dy + dz*dz)
                if d < .228:
                    candidates.append((d, i, j, rnd()))
        candidates.sort(key=lambda x: x[0])

        deg = [0] * node_count
        edges = []
        for _d, i, j, p in candidates:
            if len(edges) >= 860:
                break
            if deg[i] >= 7 or deg[j] >= 7:
                continue
            deg[i] += 1
            deg[j] += 1
            edges.append({
                "i": i,
                "j": j,
                "phase": p,
                "birth": .12 + p * .74,
                "speed": .12 + rnd() * .34,
            })
        self._edges = edges

        stars = []
        for _ in range(190):
            stars.append({
                "x": (rnd() - .5) * 2.35,
                "y": (rnd() - .5) * 2.05,
                "r": .25 + rnd() * 1.25,
                "phase": rnd() * self.TAU,
                "color": rnd(),
                "birth": rnd() * .55,
            })
        self._stars = stars

    @staticmethod
    def _rotate_point(p, ry, rx):
        cy=math.cos(ry); sy=math.sin(ry)
        x=p["x"]*cy+p["z"]*sy
        z=-p["x"]*sy+p["z"]*cy
        cx=math.cos(rx); sx=math.sin(rx)
        y=p["y"]*cx-z*sx
        z=p["y"]*sx+z*cx
        return x,y,z

    @staticmethod
    def _project(p, cx, cy, radius):
        x,y,z=p
        s=1.0/(1.0+z*.10)
        return cx+x*radius*s, cy+y*radius*s, z, s

    def _paint_gradient_circle(self, painter, cx, cy, radius, stops):
        grad=QRadialGradient(QPointF(cx,cy), radius)
        for pos,color,alpha in stops:
            grad.setColorAt(pos, self._qcolor(color, alpha))
        painter.setPen(QPen(QColor(0,0,0,0)))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(cx,cy), radius, radius)

    def _draw_background_particles(self,p,t,cx,cy,R,C):
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for s in self._stars:
            x=cx+s["x"]*R+math.sin(t*.14+s["phase"])*R*.009
            y=cy+s["y"]*R*.76+math.cos(t*.12+s["phase"])*R*.006
            col=C["cyan2"] if s["color"]<.42 else C["violet"] if s["color"]<.76 else C["magenta"]
            a=.060+.115*(.5+.5*math.sin(t*.9+s["phase"]))
            p.setPen(QPen(self._qcolor(col,a)))
            p.setBrush(QBrush(self._qcolor(col,a)))
            p.drawEllipse(QPointF(x,y),s["r"],s["r"])
        p.restore()

    def _draw_waveform(self,p,t,cx,cy,R,C,energy):
        voice=max(.24,energy) if self._state=="SPEAKING" else energy
        width=R*1.78
        amp=R*(.013+(voice*.150 if self._state=="SPEAKING" else .0065))
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)

        haze=QLinearGradient(cx-width,cy,cx+width,cy)
        haze.setColorAt(0,QColor(218,92,255,0))
        haze.setColorAt(.18,self._qcolor(C["magenta"],.055+voice*.035))
        haze.setColorAt(.50,self._qcolor(C["violet"],.025+voice*.020))
        haze.setColorAt(.82,self._qcolor(C["cyan"],.060+voice*.040))
        haze.setColorAt(1,QColor(99,243,255,0))
        p.setPen(QPen(QBrush(haze),5+voice*5))
        p.drawLine(QPointF(cx-width,cy),QPointF(cx+width,cy))

        grad=QLinearGradient(cx-width,cy,cx+width,cy)
        grad.setColorAt(0,QColor(218,92,255,0))
        grad.setColorAt(.12,self._qcolor(C["magenta"],.32+voice*.18))
        grad.setColorAt(.42,self._qcolor(C["violet"],.16+voice*.12))
        grad.setColorAt(.58,self._qcolor(C["cyan"],.16+voice*.12))
        grad.setColorAt(.88,self._qcolor(C["cyan"],.34+voice*.20))
        grad.setColorAt(1,QColor(99,243,255,0))

        path=QPainterPath()
        N=240
        for i in range(N+1):
            u=i/N
            x=cx-width+u*width*2
            dist=abs(u-.5)*2
            side=.22+1.12*smooth(.06,.94,dist)
            m=(math.sin(u*self.TAU*17-t*(1.55+voice*3.0))*.50+
               math.sin(u*self.TAU*31+t*.78)*.30+
               math.sin(u*self.TAU*53-t*.36)*.18)
            y=cy+m*amp*side
            if i==0:path.moveTo(x,y)
            else:path.lineTo(x,y)
        p.setPen(QPen(QBrush(grad),1.0+voice*1.20))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.restore()

    def _draw_pedestal(self,p,t,cx,cy,R,C,energy):
        y=cy+R*1.095
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)

        floor=QRadialGradient(QPointF(cx,y),R*1.22)
        floor.setColorAt(0,self._qcolor(C["white"],.030+energy*.018))
        floor.setColorAt(.22,self._qcolor(C["violet"],.085+energy*.040))
        floor.setColorAt(.50,self._qcolor(C["blue"],.048+energy*.032))
        floor.setColorAt(.74,self._qcolor(C["magenta"],.030+energy*.024))
        floor.setColorAt(1,QColor(0,0,0,0))
        p.setPen(QPen(QColor(0,0,0,0)))
        p.setBrush(QBrush(floor))
        p.save()
        p.translate(cx,y); p.scale(1,.15); p.translate(-cx,-y)
        p.drawEllipse(QPointF(cx,y),R*1.22,R*1.22)
        p.restore()

        for i in range(18):
            rr=R*(.24+i*.058)
            hh=R*(.018+i*.0018)
            pulse=.5+.5*math.sin(t*.31+i*.43)
            col=C["cyan"] if i%5==0 else C["magenta"] if i%3==0 else C["violet"]
            p.setPen(QPen(self._qcolor(col,.052+.052*pulse+energy*.026),.52+(i%4)*.12))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx,y),rr,hh)

        for rr,hh,col in (
            (.42,.038,C["violet"]),
            (.62,.047,C["magenta"]),
            (.86,.060,C["cyan"]),
        ):
            p.setPen(QPen(self._qcolor(col,.15+energy*.052),1.0))
            p.drawEllipse(QPointF(cx,y),R*rr,R*hh)
        p.restore()

    def _draw_halo(self,p,cx,cy,R,C,energy):
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        self._paint_gradient_circle(p,cx,cy,R*1.30,[
            (0.0,C["white"],.020+energy*.018),
            (.24,C["violet"],.055+energy*.040),
            (.58,C["blue"],.025+energy*.025),
            (.88,C["magenta"],.010+energy*.014),
            (1.0,(0,0,0),0),
        ])
        self._paint_gradient_circle(p,cx,cy,R*.60,[
            (0.0,C["violet"],.065+energy*.050),
            (.38,C["blue"],.020+energy*.024),
            (1.0,(0,0,0),0),
        ])
        p.restore()

    def _draw_globe(self,p,t,cx,cy,R,C,energy):
        rx=-.055+math.sin(t*.14)*.018
        pts=[
            self._project(self._rotate_point(n,self._rot,rx),cx,cy,R)
            for n in self._nodes
        ]
        p.save()
        p.setCompositionMode(QPainter.CompositionMode_Plus)

        # Topology edges. Low-alpha glow pass + crisp pass approximates the
        # Chromium CSS drop-shadow/filter applied to the whole P0436 canvas.
        for e in self._edges:
            a=pts[e["i"]]; b=pts[e["j"]]
            depth=clamp(.42+(a[2]+b[2])*.38,.10,1)
            pulse=.5+.5*math.sin(t*(.72+e["speed"])+e["phase"]*self.TAU)
            state_boost=.060*pulse if self._state in ("THINKING","ANALYZING","SEARCHING") else 0
            midx=(a[0]+b[0])*.5; midy=(a[1]+b[1])*.5
            center_boost=1+max(0,1-math.hypot(midx-cx,midy-cy)/(R*.95))*.38
            alpha=depth*center_boost*(.095+energy*(.082+.092*pulse)+state_boost*1.20)
            col=mix_color(C["magenta"],C["cyan"],clamp((midx-cx)/(R*1.55)*.5+.5))
            width=.64+depth*.88+energy*.34

            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self._qcolor(col,alpha),width))
            p.drawLine(QPointF(a[0],a[1]),QPointF(b[0],b[1]))

            if energy>.04:
                q=(t*(.10+e["speed"]*.14)+e["phase"])%1
                if q<.30:
                    qq=q/.30
                    px=lerp(a[0],b[0],qq); py=lerp(a[1],b[1],qq)
                    c=C["white"] if energy>.08 else C["magenta"] if e["phase"]>.5 else C["cyan"]
                    p.setPen(QPen(self._qcolor(c,depth*(.08+energy*.18))))
                    p.setBrush(QBrush(self._qcolor(c,depth*(.08+energy*.18))))
                    p.drawEllipse(QPointF(px,py),.65+energy,.65+energy)

        # Nodes
        for i,n in enumerate(self._nodes):
            pp=pts[i]
            depth=clamp(.48+pp[2]*.52,.15,1)
            f=.5+.5*math.sin(t*.65+n["phase"])
            col=C["cyan"] if n["color"]<.42 else C["violet"] if n["color"]<.74 else C["magenta"]
            radial=1+max(0,1-math.hypot(pp[0]-cx,pp[1]-cy)/(R*.94))*.34
            a=depth*radial*(.19+.15*f+energy*.14)
            rr=(.82+n["size"]*.70)*pp[3]*(1+energy*.16)

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(self._qcolor(col,a)))
            p.drawEllipse(QPointF(pp[0],pp[1]),rr,rr)
            if depth>.74 and f>.82:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(self._qcolor(C["white"],.18)))
                p.drawEllipse(QPointF(pp[0],pp[1]),2.35,2.35)

        # Soft continuous shell
        for k,col in enumerate((C["cyan"],C["violet"],C["magenta"])):
            rr=R*(.958+k*.010)
            p.setPen(QPen(self._qcolor(col,.072+energy*.036),.72+k*.18))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx,cy),rr,rr)

        # Electric fragmented membrane
        for k in range(42):
            phase=k*self.TAU/42+math.sin(k*2.37)*.052+self._rot*.08
            span=.040+(k%6)*.019
            rr=R*(.975+(k%4)*.005)
            pulse=.54+.46*math.sin(t*(.52+(k%5)*.055)+k*.83)
            col=C["white"] if k%7==0 else C["magenta"] if k%4==0 else C["cyan"] if k%3==0 else C["violet"]
            start=-math.degrees(phase)*16
            span16=-math.degrees(span)*16
            rect=QRectF(cx-rr,cy-rr,rr*2,rr*2)

            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self._qcolor(col,.085+.090*pulse+energy*.065),3.0+(k%3)*.50+energy*.70))
            p.drawArc(rect,int(start),int(span16))
            p.setPen(QPen(self._qcolor(col,.25+.18*pulse+energy*.13),.85+(k%3)*.24+energy*.25))
            p.drawArc(rect,int(start),int(span16))

            aa=phase+span*.52
            hx=cx+math.cos(aa)*rr; hy=cy+math.sin(aa)*rr
            hot=1.3+(k%5)*.30+energy*.55
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(self._qcolor(C["white"],.12+.16*pulse+energy*.08)))
            p.drawEllipse(QPointF(hx,hy),hot*1.8,hot*1.8)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(self._qcolor(col,.32+.22*pulse+energy*.12)))
            p.drawEllipse(QPointF(hx,hy),hot,hot)

        # Interior curved traces
        for k in range(16):
            angle=k*self.TAU/16+self._rot*.26
            col=C["magenta"] if k%4==0 else C["cyan"] if k%3==0 else C["violet"]
            p.save()
            p.translate(cx,cy)
            p.rotate(math.degrees(angle*.15))
            p.scale(1,(.115+.041*(k%8))/.945)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self._qcolor(col,.040+energy*.020),.50+(k%3)*.07))
            p.drawEllipse(QPointF(0,0),R*.945,R*.945)
            p.restore()

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(self._qcolor(C["white"],.080+energy*.050),1.05+energy*.35))
        p.drawEllipse(QPointF(cx,cy),R*.994,R*.994)
        p.restore()

    def paint(self, painter: QPainter):
        w=float(self.width()); h=float(self.height())
        if w<10 or h<10:
            return

        painter.setRenderHint(QPainter.Antialiasing,True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform,True)

        now=time.perf_counter()
        dt=clamp(now-self._last,0,.05)
        self._last=now
        t=now
        simulated=.42 if self._state=="SPEAKING" else .10 if self._state=="LISTENING" else 0.0
        raw=max(simulated, self._external_pcm)

        tau=.040 if raw>self._pcm else .19
        k=1-math.exp(-dt/tau) if tau>0 else 1
        self._pcm+=(raw-self._pcm)*k
        self._accent=max(self._accent*math.exp(-dt/.12),max(0,raw-self._prev_pcm)*1.8)
        self._prev_pcm=raw
        energy=max(.24,self._pcm) if self._state=="SPEAKING" else self._pcm

        self._rot+=dt*(.025+(.042 if self._state in ("THINKING","ANALYZING","SEARCHING") else 0)+energy*.010)

        cx=w*.50
        cy=h*.455
        R=min(w,h)*.305
        C=self._palette()

        self._draw_background_particles(painter,t,cx,cy,R,C)
        # AURA_ORB_CLEANUP_FIX5: horizontal waveform disabled on HOME
        # self._draw_waveform(painter,t,cx,cy,R,C,energy)
        self._draw_pedestal(painter,t,cx,cy,R,C,energy)
        # AURA_ORB_CLEANUP_FIX5: oversized spherical halo disabled
        # self._draw_halo(painter,cx,cy,R,C,energy)
        self._draw_globe(painter,t,cx,cy,R,C,energy)

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        self._paint_gradient_circle(painter,cx,cy,R*1.09,[
            (0.0,(255,255,255),0),
            (.72,C["violet"],.018),
            (.94,C["cyan"],.050),
            (1.0,(0,0,0),0),
        ])
        painter.restore()





class CoreDataListModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2
    ContentRole = Qt.UserRole + 3
    StatusRole = Qt.UserRole + 4
    DueDateRole = Qt.UserRole + 5
    TriggerAtRole = Qt.UserRole + 6
    CreatedAtRole = Qt.UserRole + 7
    TypeRole = Qt.UserRole + 8
    ImportanceRole = Qt.UserRole + 9
    SourceLabelRole = Qt.UserRole + 10
    SensitiveRole = Qt.UserRole + 11
    DescriptionRole = Qt.UserRole + 12
    AccessCountRole = Qt.UserRole + 13
    ExternalIdRole = Qt.UserRole + 14
    EndAtRole = Qt.UserRole + 15

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    def roleNames(self):
        return {
            self.IdRole: b"itemId",
            self.TitleRole: b"title",
            self.ContentRole: b"content",
            self.StatusRole: b"status",
            self.DueDateRole: b"dueDate",
            self.TriggerAtRole: b"triggerAt",
            self.CreatedAtRole: b"createdAt",
            self.TypeRole: b"memoryType",
            self.ImportanceRole: b"importance",
            self.SourceLabelRole: b"sourceLabel",
            self.SensitiveRole: b"isSensitive",
            self.DescriptionRole: b"description",
            self.AccessCountRole: b"accessCount",
            self.ExternalIdRole: b"externalId",
            self.EndAtRole: b"endAt",
        }

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        item = self._items[row]

        if role == self.IdRole:
            return int(item.get("id") or 0)
        if role == self.TitleRole:
            return str(item.get("title") or "")
        if role == self.ContentRole:
            return str(item.get("content") or "")
        if role == self.StatusRole:
            return str(item.get("status") or "")
        if role == self.DueDateRole:
            return str(item.get("due_date") or "")
        if role == self.TriggerAtRole:
            return str(item.get("trigger_at") or "")
        if role == self.CreatedAtRole:
            return str(item.get("created_at") or "")
        if role == self.TypeRole:
            return str(item.get("type") or "")
        if role == self.ImportanceRole:
            return int(item.get("importance") or 0)
        if role == self.SourceLabelRole:
            return str(item.get("source_label") or item.get("source") or "")
        if role == self.SensitiveRole:
            return bool(item.get("is_sensitive"))
        if role == self.DescriptionRole:
            return str(item.get("description") or "")
        if role == self.AccessCountRole:
            return int(item.get("access_count") or 0)
        if role == self.ExternalIdRole:
            return str(
                item.get("external_id")
                or item.get("task_id")
                or item.get("event_id")
                or ""
            )
        if role == self.EndAtRole:
            return str(item.get("end_at") or "")
        return None

    def replace_items(self, items):
        clean = []
        for raw in list(items or []):
            if isinstance(raw, dict):
                clean.append(dict(raw))
        self.beginResetModel()
        self._items = clean
        self.endResetModel()

    def clear(self):
        self.replace_items([])



class AgendaCalendarModel(QAbstractListModel):
    DayNumberRole = Qt.UserRole + 1
    DateKeyRole = Qt.UserRole + 2
    InMonthRole = Qt.UserRole + 3
    TodayRole = Qt.UserRole + 4
    CountRole = Qt.UserRole + 5
    FirstRole = Qt.UserRole + 6
    SecondRole = Qt.UserRole + 7
    ThirdRole = Qt.UserRole + 8
    FirstPayloadRole = Qt.UserRole + 9
    SecondPayloadRole = Qt.UserRole + 10
    ThirdPayloadRole = Qt.UserRole + 11

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    def roleNames(self):
        return {
            self.DayNumberRole: b"dayNumber",
            self.DateKeyRole: b"dateKey",
            self.InMonthRole: b"inMonth",
            self.TodayRole: b"isToday",
            self.CountRole: b"eventCount",
            self.FirstRole: b"firstEvent",
            self.SecondRole: b"secondEvent",
            self.ThirdRole: b"thirdEvent",
            self.FirstPayloadRole: b"firstEventPayload",
            self.SecondPayloadRole: b"secondEventPayload",
            self.ThirdPayloadRole: b"thirdEventPayload",
        }

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    @staticmethod
    def _payload(item, index):
        events = item.get("events", [])
        if 0 <= index < len(events):
            return dict(events[index])
        return {}

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]

        if role == self.DayNumberRole:
            return item["day"]
        if role == self.DateKeyRole:
            return item["key"]
        if role == self.InMonthRole:
            return item["in_month"]
        if role == self.TodayRole:
            return item["today"]
        if role == self.CountRole:
            return item["count"]

        if role == self.FirstRole:
            return self._payload(item, 0).get("label", "")
        if role == self.SecondRole:
            return self._payload(item, 1).get("label", "")
        if role == self.ThirdRole:
            return self._payload(item, 2).get("label", "")

        if role == self.FirstPayloadRole:
            return self._payload(item, 0)
        if role == self.SecondPayloadRole:
            return self._payload(item, 1)
        if role == self.ThirdPayloadRole:
            return self._payload(item, 2)

        return None

    def rebuild(self, year, month, reminders, google_events=None):
        year = int(year)
        month = int(month)
        by_day = {}

        for item in list(reminders or []):
            if not isinstance(item, dict):
                continue
            raw = str(item.get("trigger_at") or "").strip()
            if len(raw) < 10:
                continue

            key = raw[:10]
            title = str(
                item.get("content")
                or item.get("title")
                or "Rappel"
            )
            by_day.setdefault(key, []).append(
                {
                    "label": title,
                    "source": "aura",
                    "external_id": "",
                    "title": title,
                    "start_at": raw,
                    "end_at": "",
                    "description": str(item.get("description") or ""),
                }
            )

        for item in list(google_events or []):
            if not isinstance(item, dict):
                continue

            raw = str(item.get("trigger_at") or "").strip()
            if len(raw) < 10:
                continue

            key = raw[:10]
            title = str(
                item.get("title")
                or "Événement Google"
            )
            by_day.setdefault(key, []).append(
                {
                    "label": "G · " + title,
                    "source": "google",
                    "external_id": str(
                        item.get("external_id")
                        or item.get("event_id")
                        or ""
                    ),
                    "title": title,
                    "start_at": raw,
                    "end_at": str(item.get("end_at") or ""),
                    "description": str(item.get("description") or ""),
                }
            )

        cal = calendar.Calendar(firstweekday=0)
        dates = list(cal.itermonthdates(year, month))
        while len(dates) < 42:
            dates.append(
                dates[-1]
                + __import__("datetime").timedelta(days=1)
            )
        if len(dates) > 42:
            dates = dates[:42]

        today = datetime.now().date()
        items = []

        for d in dates:
            key = d.isoformat()
            events = by_day.get(key, [])

            items.append(
                {
                    "day": d.day,
                    "key": key,
                    "in_month": d.month == month,
                    "today": d == today,
                    "count": len(events),
                    "events": events[:3],
                }
            )

        self.beginResetModel()
        self._items = items
        self.endResetModel()


class ConversationModel(QAbstractListModel):
    SideRole = Qt.UserRole + 1
    TextRole = Qt.UserRole + 2
    TimestampRole = Qt.UserRole + 3
    SourceRole = Qt.UserRole + 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    def roleNames(self):
        return {
            self.SideRole: b"side",
            self.TextRole: b"text",
            self.TimestampRole: b"timestamp",
            self.SourceRole: b"source",
        }

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        item = self._items[row]
        if role == self.SideRole:
            return item.get("side", "")
        if role == self.TextRole:
            return item.get("text", "")
        if role == self.TimestampRole:
            return item.get("timestamp", "")
        if role == self.SourceRole:
            return item.get("source", "")
        return None

    def append_message(self, side, text, source="core"):
        text = str(text or "").strip()
        if not text:
            return
        item = {
            "side": str(side or "system"),
            "text": text,
            "timestamp": datetime.now().strftime("%H:%M"),
            "source": str(source or "core"),
        }
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()

    def clear(self):
        if not self._items:
            return
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()


# AURA_GOOGLE_PRODUCTIVITY_QT_FIX19
# AURA_GOOGLE_ACCOUNT_CONNECT_FIX20
# AURA_GOOGLE_BIDIRECTIONAL_FIX21
# AURA_GOOGLE_TASKS_WRITE_REPAIR_FIX22
# AURA_PRODUCTIVITY_EDIT_ACTIONS_FIX23
# AURA_CALENDAR_SELECTABLE_EDIT_FIX24
class AuraCoreBridge(QObject):
    connectedChanged = Signal()
    interactionReadyChanged = Signal()
    providerChanged = Signal()
    modelChanged = Signal()
    voiceStatusChanged = Signal()
    voiceAmplitudeChanged = Signal()
    lastErrorChanged = Signal()
    sessionChanged = Signal()
    messageAdded = Signal()
    lastAuraCharsChanged = Signal()
    lastAuraPreviewChanged = Signal()
    lastEventTypeChanged = Signal()
    productivityChanged = Signal()
    memoryChanged = Signal()
    agendaChanged = Signal()
    dataStatusChanged = Signal()
    diagnosticsChanged = Signal()
    localeChanged = Signal()
    uiStateRequested = Signal(str)

    _statusReceived = Signal(dict)
    _eventReceived = Signal(dict)
    _connectionError = Signal(str)
    _productivityReceived = Signal(dict)
    _googleTasksReceived = Signal(dict)
    _googleCalendarReceived = Signal(dict)
    _googleConnectReceived = Signal(dict)
    _googleMutationReceived = Signal(dict)
    _memoryReceived = Signal(dict)
    _diagnosticsReceived = Signal(dict)
    _localeReceived = Signal(dict)
    _actionCompleted = Signal(str, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._interaction_ready = False
        self._provider = ""
        self._model = ""
        self._voice_status = "standby"
        self._voice_amplitude = 0.0
        self._last_error = ""
        self._last_aura_chars = 0
        self._last_aura_preview = ""
        self._last_event_type = ""
        self._operation_depth = 0
        self._session_label = "AURA Headless Core"
        self._diag_root = Path(__file__).resolve().parents[1] / "runtime"
        self._diag_root.mkdir(parents=True, exist_ok=True)
        self._diag_path = self._diag_root / "poc6c_conversation_events.jsonl"
        self._session = None
        self._checking = False
        self._sse_thread = None
        self._sse_stop = threading.Event()
        self._sse_key = None
        self._last_event_seq = 0
        self._last_event_session_key = None
        self._heartbeat_failures = 0
        self._pending_user = []
        self.messages = ConversationModel(self)
        self.tasks_model = CoreDataListModel(self)
        self.reminders_model = CoreDataListModel(self)
        self.notes_model = CoreDataListModel(self)
        self.google_tasks_model = CoreDataListModel(self)
        self.google_calendar_model = CoreDataListModel(self)
        self.memories_model = CoreDataListModel(self)
        self.memory_context_model = CoreDataListModel(self)
        self.agenda_calendar_model = AgendaCalendarModel(self)

        now = datetime.now()
        self._agenda_year = now.year
        self._agenda_month = now.month
        self._agenda_month_label = ""
        self._last_reminders_snapshot = []
        self._last_google_calendar_snapshot = []

        self._task_count = 0
        self._reminder_count = 0
        self._note_count = 0
        self._google_tasks_count = 0
        self._google_calendar_count = 0
        self._google_sync_active = False
        self._google_tasks_status = "Google Tasks · en attente"
        self._google_calendar_status = "Google Calendar · en attente"
        self._google_connecting = False
        self._last_google_tasks_refresh = 0.0
        self._last_google_calendar_refresh = 0.0
        self._memory_count = 0
        self._sensitive_memory_count = 0
        self._memory_private = False
        self._memory_auto_capture = False
        self._show_sensitive_memories = False
        self._data_status = ""
        self._data_status_ok = True
        self._data_fetch_productivity = False
        self._data_fetch_google_tasks = False
        self._data_fetch_google_calendar = False
        self._data_fetch_memory = False
        self._diagnostics_fetching = False
        self._locale_fetching = False
        self._locale = "fr-FR"
        self._diag_ready = False
        self._diag_cpu_percent = 0.0
        self._diag_ram_percent = 0.0
        self._diag_vram_percent = 0.0
        self._diag_disk_percent = 0.0
        self._diag_temp_percent = 0.0
        self._diag_health = 0
        self._diag_cpu_text = "—"
        self._diag_ram_text = "—"
        self._diag_vram_text = "—"
        self._diag_disk_text = "—"
        self._diag_temp_text = "—"
        self._diag_download_text = "—"
        self._diag_upload_text = "—"
        self._diag_cpu_model = "—"
        self._diag_gpu_model = "—"
        self._diag_topology = "—"
        self._diag_profile = "—"
        self._diag_generated_at = "—"

        self._statusReceived.connect(self._apply_status)
        self._eventReceived.connect(self._handle_event)
        self._connectionError.connect(self._handle_connection_error)
        self._productivityReceived.connect(self._apply_productivity)
        self._googleTasksReceived.connect(self._apply_google_tasks)
        self._googleCalendarReceived.connect(self._apply_google_calendar)
        self._googleConnectReceived.connect(self._apply_google_connect)
        self._googleMutationReceived.connect(self._apply_google_mutation)
        self._memoryReceived.connect(self._apply_memory)
        self._diagnosticsReceived.connect(self._apply_diagnostics)
        self._localeReceived.connect(self._apply_locale)
        self._actionCompleted.connect(self._handle_action_completed)

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(2500)
        self._reconnect_timer.timeout.connect(self._ensure_connection)
        self._reconnect_timer.start()

        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.setInterval(5000)
        self._heartbeat_timer.timeout.connect(self._heartbeat)
        self._heartbeat_timer.start()

        self._data_refresh_timer = QTimer(self)
        self._data_refresh_timer.setInterval(4500)
        self._data_refresh_timer.timeout.connect(self.refreshAllData)
        self._data_refresh_timer.start()

        QTimer.singleShot(80, self._ensure_connection)

    @Property(bool, notify=connectedChanged)
    def connected(self):
        return self._connected

    @Property(bool, notify=interactionReadyChanged)
    def interactionReady(self):
        return self._interaction_ready

    @Property(str, notify=providerChanged)
    def provider(self):
        return self._provider

    @Property(str, notify=modelChanged)
    def model(self):
        return self._model

    @Property(str, notify=voiceStatusChanged)
    def voiceStatus(self):
        return self._voice_status

    @Property(float, notify=voiceAmplitudeChanged)
    def voiceAmplitude(self):
        return self._voice_amplitude

    @Property(str, notify=lastErrorChanged)
    def lastError(self):
        return self._last_error

    @Property(str, notify=sessionChanged)
    def sessionLabel(self):
        return self._session_label

    @Property(int, notify=lastAuraCharsChanged)
    def lastAuraChars(self):
        return self._last_aura_chars

    @Property(str, notify=lastAuraPreviewChanged)
    def lastAuraPreview(self):
        return self._last_aura_preview

    @Property(str, notify=lastEventTypeChanged)
    def lastEventType(self):
        return self._last_event_type

    @Property(int, notify=productivityChanged)
    def taskCount(self):
        return self._task_count

    @Property(int, notify=productivityChanged)
    def reminderCount(self):
        return self._reminder_count

    @Property(int, notify=productivityChanged)
    def noteCount(self):
        return self._note_count

    @Property(int, notify=productivityChanged)
    def googleTasksCount(self):
        return self._google_tasks_count

    @Property(int, notify=productivityChanged)
    def googleCalendarCount(self):
        return self._google_calendar_count

    @Property(bool, notify=productivityChanged)
    def googleSyncActive(self):
        return self._google_sync_active

    @Property(str, notify=productivityChanged)
    def googleTasksStatus(self):
        return self._google_tasks_status

    @Property(str, notify=productivityChanged)
    def googleCalendarStatus(self):
        return self._google_calendar_status

    @Property(bool, notify=productivityChanged)
    def googleConnecting(self):
        return self._google_connecting

    @Property(str, notify=productivityChanged)
    def googleConnectButtonLabel(self):
        if self._google_connecting:
            return "CONNEXION…"
        if "réautorisation" in self._google_tasks_status.casefold() or "oauth" in self._google_tasks_status.casefold():
            return "RÉAUTORISER GOOGLE"
        return "CONNECTER GOOGLE"

    @Property(int, notify=memoryChanged)
    def memoryCount(self):
        return self._memory_count

    @Property(int, notify=memoryChanged)
    def sensitiveMemoryCount(self):
        return self._sensitive_memory_count

    @Property(bool, notify=memoryChanged)
    def memoryPrivateMode(self):
        return self._memory_private

    @Property(bool, notify=memoryChanged)
    def memoryAutoCapture(self):
        return self._memory_auto_capture

    @Property(bool, notify=memoryChanged)
    def showSensitiveMemories(self):
        return self._show_sensitive_memories

    @Property(str, notify=agendaChanged)
    def agendaMonthLabel(self):
        return self._agenda_month_label

    @Property(str, notify=dataStatusChanged)
    def dataStatus(self):
        return self._data_status

    @Property(bool, notify=dataStatusChanged)
    def dataStatusOk(self):
        return self._data_status_ok

    # AURA_DIAG_SETTINGS_FIX6
    @Property(str, notify=localeChanged)
    def locale(self):
        return self._locale

    @Property(bool, notify=diagnosticsChanged)
    def diagReady(self):
        return self._diag_ready

    @Property(float, notify=diagnosticsChanged)
    def diagCpuPercent(self):
        return self._diag_cpu_percent

    @Property(float, notify=diagnosticsChanged)
    def diagRamPercent(self):
        return self._diag_ram_percent

    @Property(float, notify=diagnosticsChanged)
    def diagVramPercent(self):
        return self._diag_vram_percent

    @Property(float, notify=diagnosticsChanged)
    def diagDiskPercent(self):
        return self._diag_disk_percent

    @Property(float, notify=diagnosticsChanged)
    def diagTempPercent(self):
        return self._diag_temp_percent

    @Property(int, notify=diagnosticsChanged)
    def diagHealth(self):
        return self._diag_health

    @Property(str, notify=diagnosticsChanged)
    def diagCpuText(self):
        return self._diag_cpu_text

    @Property(str, notify=diagnosticsChanged)
    def diagRamText(self):
        return self._diag_ram_text

    @Property(str, notify=diagnosticsChanged)
    def diagVramText(self):
        return self._diag_vram_text

    @Property(str, notify=diagnosticsChanged)
    def diagDiskText(self):
        return self._diag_disk_text

    @Property(str, notify=diagnosticsChanged)
    def diagTempText(self):
        return self._diag_temp_text

    @Property(str, notify=diagnosticsChanged)
    def diagDownloadText(self):
        return self._diag_download_text

    @Property(str, notify=diagnosticsChanged)
    def diagUploadText(self):
        return self._diag_upload_text

    @Property(str, notify=diagnosticsChanged)
    def diagCpuModel(self):
        return self._diag_cpu_model

    @Property(str, notify=diagnosticsChanged)
    def diagGpuModel(self):
        return self._diag_gpu_model

    @Property(str, notify=diagnosticsChanged)
    def diagTopology(self):
        return self._diag_topology

    @Property(str, notify=diagnosticsChanged)
    def diagProfile(self):
        return self._diag_profile

    @Property(str, notify=diagnosticsChanged)
    def diagGeneratedAt(self):
        return self._diag_generated_at

    @Property(str, notify=providerChanged)
    def providerLabel(self):
        provider = str(self._provider or "").strip()
        model = str(self._model or "").strip()
        if provider and model:
            prefix = provider.casefold() + "/"
            if model.casefold().startswith(prefix):
                model = model[len(provider) + 1:]
            return f"{provider} · {model}"
        if provider:
            return provider
        return "LOCAL RUNTIME" if self._connected else "CORE OFFLINE"

    def _write_diag(self, kind, payload=None):
        try:
            record = {
                "ts": datetime.now().isoformat(timespec="milliseconds"),
                "kind": str(kind or ""),
                "payload": payload if isinstance(payload, dict) else {},
            }
            # Never persist the ephemeral RC4.2 authentication token.
            for key in ("token", "auth_token", "session_token"):
                record["payload"].pop(key, None)
            with self._diag_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    def _set_last_event(self, value):
        value = str(value or "")
        if value != self._last_event_type:
            self._last_event_type = value
            self.lastEventTypeChanged.emit()

    def _set_last_aura_payload(self, text, data):
        text = str(text or "")
        chars = len(text)
        preview = text.replace("\r", " ").replace("\n", " ").strip()[:180]
        if chars != self._last_aura_chars:
            self._last_aura_chars = chars
            self.lastAuraCharsChanged.emit()
        if preview != self._last_aura_preview:
            self._last_aura_preview = preview
            self.lastAuraPreviewChanged.emit()
        self._write_diag(
            "aura_message",
            {
                "chars": chars,
                "text": text,
                "source": str((data or {}).get("source") or "core"),
                "data_keys": sorted(str(k) for k in (data or {}).keys()),
            },
        )

    def _voice_busy(self):
        folded = str(self._voice_status or "").casefold()
        return any(x in folded for x in ("speak", "play", "listen", "record"))

    def _restore_idle_if_safe(self):
        if self._operation_depth <= 0 and not self._voice_busy():
            self.uiStateRequested.emit("IDLE")

    def _set_data_status(self, text, ok=True):
        text = str(text or "")
        ok = bool(ok)
        changed = text != self._data_status or ok != self._data_status_ok
        self._data_status = text
        self._data_status_ok = ok
        if changed:
            self.dataStatusChanged.emit()

    @Slot()
    def clearDataStatus(self):
        self._set_data_status("", True)

    @staticmethod
    def _fix6_float(value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default)

    @staticmethod
    def _fix6_text(value, fallback="—"):
        text = str(value or "").strip()
        return text if text else fallback

    # AURA_CHROMIUM_PARITY_FIX7
    def _fix7_local_hardware_profile(self, session):
        import importlib.util
        candidates=[]
        root_text=str((session or {}).get("root") or os.environ.get("AURA_ROOT") or "").strip()
        if root_text:
            base=Path(root_text)
            candidates.append(base/"ui/chromium/v0.7.2.2-rc4.2/tools/hardware_profile_p0851.py")
            try:
                candidates.extend(sorted(base.glob("ui/chromium/*/tools/hardware_profile_p0851.py"),reverse=True))
            except Exception:
                pass
        if os.name=="nt": candidates.append(Path(r"C:\AURA GPT version")/"ui/chromium/v0.7.2.2-rc4.2/tools/hardware_profile_p0851.py")
        seen=set()
        for fp in candidates:
            try:
                fp=Path(fp); key=str(fp).casefold()
                if key in seen: continue
                seen.add(key)
                if not fp.is_file(): continue
                spec=importlib.util.spec_from_file_location("aura_qt_hw_p0851",str(fp))
                if spec is None or spec.loader is None: continue
                mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
                fn=getattr(mod,"build_hardware_profile",None)
                if callable(fn):
                    data=fn(None,force=True)
                    if isinstance(data,dict):
                        data["_qt_fallback"]=str(fp); return data
            except Exception:
                continue
        raise RuntimeError("hardware_profile_p0851_not_found")

    @Slot()
    def refreshDiagnostics(self):
        if not self._connected or not self._session or self._diagnostics_fetching: return
        self._diagnostics_fetching=True
        session=dict(self._session)
        def worker():
            try:
                payload=self._request_json(session,"/api/hardware-profile?refresh=1",timeout=5.0)
                if not isinstance(payload,dict): payload={}
                self._diagnosticsReceived.emit(payload); self._set_data_status("",True)
            except Exception:
                try:
                    payload=self._fix7_local_hardware_profile(session)
                    self._diagnosticsReceived.emit(payload); self._set_data_status("",True)
                except Exception as fallback_exc:
                    self._set_data_status("Diagnostics indisponibles: "+type(fallback_exc).__name__,False)
            finally:
                self._diagnostics_fetching=False
        threading.Thread(target=worker,daemon=True,name="AuraQtHardwareDiagnostics").start()

    @Slot(dict)
    def _apply_diagnostics(self, payload):
        # AURA_DIAGNOSTICS_FINAL_POLISH_FIX12
        state = dict(payload.get("system_state") or {})

        # Preserve the last known-good snapshot during transient refreshes.
        # Empty/incomplete samples must never reset visible metrics to zero.
        has_live_metrics = any(
            key in state
            for key in (
                "cpu_percent",
                "ram_percent",
                "ram_total_gib",
                "temperature_c",
                "storage",
            )
        )
        if not state or not has_live_metrics:
            return

        inventory = dict(payload.get("inventory") or {})
        gpu = dict(inventory.get("compute_gpu") or {})
        cpu = dict(inventory.get("cpu") or {})
        storage = dict(state.get("storage") or {})
        network = dict(state.get("network") or {})
        topo = dict(payload.get("topology") or {})
        profile = dict(payload.get("recommended_profile") or {})

        cpu_pct = self._fix6_float(state.get("cpu_percent"))
        ram_pct = self._fix6_float(state.get("ram_percent"))
        vram_pct = self._fix6_float(state.get("vram_percent"))
        disk_pct = self._fix6_float(storage.get("used_percent"))
        temp = state.get("temperature_c")
        temp_num = self._fix6_float(temp)

        weighted = (
            ram_pct * 0.45
            + cpu_pct * 0.20
            + vram_pct * 0.15
            + disk_pct * 0.20
        )
        self._diag_health = int(round(max(0.0, min(100.0, 100.0 - weighted))))
        self._diag_cpu_percent = max(0.0, min(100.0, cpu_pct))
        self._diag_ram_percent = max(0.0, min(100.0, ram_pct))
        self._diag_vram_percent = max(0.0, min(100.0, vram_pct))
        self._diag_disk_percent = max(0.0, min(100.0, disk_pct))
        self._diag_temp_percent = max(0.0, min(100.0, temp_num))
        self._diag_cpu_text = f"{self._diag_cpu_percent:.0f}%"

        ram_used = state.get("ram_used_gib")
        ram_total = state.get("ram_total_gib")
        vram_used = state.get("vram_used_gib")
        vram_total = state.get("vram_total_gib")
        disk_used = storage.get("used_gb")
        disk_total = storage.get("total_gb")

        self._diag_ram_text = (
            f"{self._fix6_float(ram_used):.1f} / {self._fix6_float(ram_total):.1f} Gio"
            if ram_total is not None else "—"
        )
        self._diag_vram_text = (
            f"{self._fix6_float(vram_used):.1f} / {self._fix6_float(vram_total):.1f} Gio"
            if vram_total is not None else "—"
        )
        self._diag_disk_text = (
            f"{self._fix6_float(disk_used):.0f} / {self._fix6_float(disk_total):.0f} GB"
            if disk_total is not None else "—"
        )
        self._diag_temp_text = f"{temp_num:.0f} °C" if temp is not None else "—"
        self._diag_download_text = (
            f"{self._fix6_float(network.get('download_mbps')):.1f} Mbps"
            if network.get("download_mbps") is not None else "—"
        )
        self._diag_upload_text = (
            f"{self._fix6_float(network.get('upload_mbps')):.1f} Mbps"
            if network.get("upload_mbps") is not None else "—"
        )
        self._diag_cpu_model = self._fix6_text(cpu.get("model"))
        self._diag_gpu_model = self._fix6_text(gpu.get("name"))
        self._diag_topology = self._fix6_text(topo.get("kind"))
        self._diag_profile = self._fix6_text(profile.get("label"))
        self._diag_generated_at = self._fix6_text(payload.get("generated_at"))
        self._diag_ready = True
        # A valid live state snapshot is authoritative for the native UI.
        self.diagnosticsChanged.emit()

    @Slot()
    def refreshLocale(self):
        if not self._connected or not self._session or self._locale_fetching:
            return
        self._locale_fetching = True
        session = dict(self._session)

        def worker():
            try:
                payload = self._request_json(
                    session,
                    "/api/locale",
                    timeout=3.0,
                )
                if not isinstance(payload, dict):
                    payload = {}
                self._localeReceived.emit(payload)
            except Exception as exc:
                self._set_data_status("Langue indisponible: " + type(exc).__name__, False)
            finally:
                self._locale_fetching = False

        threading.Thread(
            target=worker,
            daemon=True,
            name="AuraQtLocaleRead",
        ).start()

    @Slot(dict)
    def _apply_locale(self, payload):
        locale = str(payload.get("locale") or "fr-FR").strip()
        if locale not in {"fr-FR", "en-US"}:
            locale = "fr-FR"
        changed = locale != self._locale
        self._locale = locale
        if changed:
            self.localeChanged.emit()

    @Slot(str, result=bool)
    def setLocale(self, locale):
        locale = str(locale or "").strip()
        if locale not in {"fr-FR", "en-US"}:
            self._set_data_status("Langue non supportée", False)
            return False
        if not self._connected or not self._session:
            self._set_data_status("Core indisponible", False)
            return False

        session = dict(self._session)

        def worker():
            try:
                payload = self._request_json(
                    session,
                    "/api/locale",
                    method="POST",
                    payload={"action": "set", "locale": locale},
                    timeout=4.0,
                )
                if not bool(payload.get("ok")):
                    raise RuntimeError(str(payload.get("error") or "locale_rejected"))
                self._localeReceived.emit(payload)
                self._set_data_status(
                    "Langue appliquée" if locale == "fr-FR" else "Language applied",
                    True,
                )
            except Exception as exc:
                self._set_data_status("Impossible de changer la langue: " + type(exc).__name__, False)

        threading.Thread(
            target=worker,
            daemon=True,
            name="AuraQtLocaleWrite",
        ).start()
        return True

    @Slot()
    def refreshAllData(self):
        if not self._connected or not self._session:
            return
        self.refreshProductivity()
        now = time.monotonic()
        if now - self._last_google_tasks_refresh > 60.0:
            self.refreshGoogleTasks()
        if now - self._last_google_calendar_refresh > 60.0:
            self.refreshGoogleCalendar()
        self.refreshMemory()

    @Slot()
    def refreshProductivity(self):
        if not self._connected or not self._session or self._data_fetch_productivity:
            return
        self._data_fetch_productivity = True
        session = dict(self._session)

        def worker():
            try:
                payload = self._request_json(
                    session,
                    "/api/productivity",
                    timeout=3.0,
                )
                if not isinstance(payload, dict):
                    payload = {}
                self._productivityReceived.emit(payload)
            except Exception as exc:
                self._actionCompleted.emit(
                    "refresh_productivity",
                    False,
                    type(exc).__name__,
                )
            finally:
                self._data_fetch_productivity = False

        threading.Thread(
            target=worker,
            daemon=True,
            name="AuraQtProductivitySnapshot",
        ).start()


    @Slot(str, result=bool)
    def connectGoogle(self, file_url):
        if not self._connected or not self._session or self._google_connecting:
            return False

        raw = str(file_url or "").strip()
        if not raw:
            self._set_data_status("Sélectionne le fichier OAuth Google JSON.", False)
            return False

        local_path = QUrl(raw).toLocalFile() if raw.startswith("file:") else raw
        path = Path(local_path).expanduser()
        if not path.is_file() or path.suffix.casefold() != ".json":
            self._set_data_status("Fichier OAuth Google JSON invalide.", False)
            return False

        self._google_connecting = True
        self._google_tasks_status = "Google · autorisation en cours…"
        self._google_calendar_status = "Google · autorisation en cours…"
        self.productivityChanged.emit()
        self._set_data_status("Autorisation Google ouverte dans le navigateur…", True)

        session = dict(self._session)
        client_file = str(path.resolve())

        def worker():
            try:
                result = self._request_json(
                    session,
                    "/api/qt/google/connect",
                    method="POST",
                    payload={"client_file": client_file},
                    timeout=600.0,
                )
                if not isinstance(result, dict):
                    result = {}
                self._googleConnectReceived.emit(result)
            except Exception as exc:
                self._googleConnectReceived.emit({
                    "ok": False,
                    "error": type(exc).__name__,
                    "detail": str(exc)[:240],
                })

        threading.Thread(target=worker, daemon=True, name="AuraQtGoogleConnect").start()
        return True

    @Slot(dict)
    def _apply_google_connect(self, payload):
        self._google_connecting = False
        if bool(payload.get("ok")):
            status = dict(payload.get("status") or {})
            label = str(status.get("account_label") or payload.get("account_label") or "Google").strip()
            self._google_sync_active = True
            self._google_tasks_status = "Google Tasks · connecté · " + label
            self._google_calendar_status = "Google Calendar · connecté · " + label
            self._set_data_status("Compte Google connecté à AURA.", True)
            self.productivityChanged.emit()
            QTimer.singleShot(150, self.refreshGoogleTasks)
            QTimer.singleShot(300, self.refreshGoogleCalendar)
            return

        error = str(payload.get("error") or "google_connect_failed").strip()
        detail = str(payload.get("detail") or "").strip()
        self._google_tasks_status = "Connexion Google échouée · " + error
        self._google_calendar_status = "Connexion Google échouée · " + error
        self._set_data_status(
            "Connexion Google impossible" + ((" · " + detail) if detail else (" · " + error)),
            False,
        )
        self.productivityChanged.emit()

    @Slot()
    def refreshGoogleTasks(self):
        if not self._connected or not self._session or self._data_fetch_google_tasks:
            return
        self._data_fetch_google_tasks = True
        self._last_google_tasks_refresh = time.monotonic()
        self._google_tasks_status = "Google Tasks · synchronisation…"
        self.productivityChanged.emit()
        session = dict(self._session)

        def worker():
            result = {"status": {}, "data": {}}
            try:
                status = self._request_json(session, "/api/qt/google/status", timeout=8.0)
                result["status"] = status if isinstance(status, dict) else {}
                if not bool(result["status"].get("connected")):
                    self._googleTasksReceived.emit(result)
                    return
                if not bool(result["status"].get("tasks_supported")):
                    result["data"] = {"ok": False, "error": "tasks_reconsent_required"}
                    self._googleTasksReceived.emit(result)
                    return
                data = self._request_json(session, "/api/qt/google/tasks", timeout=12.0)
                result["data"] = data if isinstance(data, dict) else {}
                self._googleTasksReceived.emit(result)
            except Exception as exc:
                self._googleTasksReceived.emit({
                    "status": {},
                    "data": {"ok": False, "error": type(exc).__name__},
                })
            finally:
                self._data_fetch_google_tasks = False

        threading.Thread(target=worker, daemon=True, name="AuraQtGoogleTasks").start()

    @Slot()
    def refreshGoogleCalendar(self):
        if not self._connected or not self._session or self._data_fetch_google_calendar:
            return
        self._data_fetch_google_calendar = True
        self._last_google_calendar_refresh = time.monotonic()
        self._google_calendar_status = "Google Calendar · synchronisation…"
        self.productivityChanged.emit()
        session = dict(self._session)
        year = int(self._agenda_year)
        month = int(self._agenda_month)

        def worker():
            result = {"status": {}, "data": {}}
            try:
                status = self._request_json(session, "/api/qt/google/status", timeout=8.0)
                result["status"] = status if isinstance(status, dict) else {}
                if not bool(result["status"].get("connected")):
                    self._googleCalendarReceived.emit(result)
                    return
                if not bool(result["status"].get("calendar_supported")):
                    result["data"] = {"ok": False, "error": "calendar_not_enabled"}
                    self._googleCalendarReceived.emit(result)
                    return
                data = self._request_json(
                    session,
                    f"/api/qt/google/calendar?year={year}&month={month}",
                    timeout=12.0,
                )
                result["data"] = data if isinstance(data, dict) else {}
                self._googleCalendarReceived.emit(result)
            except Exception as exc:
                self._googleCalendarReceived.emit({
                    "status": {},
                    "data": {"ok": False, "error": type(exc).__name__},
                })
            finally:
                self._data_fetch_google_calendar = False

        threading.Thread(target=worker, daemon=True, name="AuraQtGoogleCalendar").start()

    @Slot()
    def refreshMemory(self):
        if not self._connected or not self._session or self._data_fetch_memory:
            return
        self._data_fetch_memory = True
        session = dict(self._session)

        def worker():
            try:
                payload = self._request_json(
                    session,
                    "/api/memory?sensitive=" + ("1" if self._show_sensitive_memories else "0"),
                    timeout=3.0,
                )
                if not isinstance(payload, dict):
                    payload = {}
                self._memoryReceived.emit(payload)
            except Exception as exc:
                self._actionCompleted.emit(
                    "refresh_memory",
                    False,
                    type(exc).__name__,
                )
            finally:
                self._data_fetch_memory = False

        threading.Thread(
            target=worker,
            daemon=True,
            name="AuraQtMemorySnapshot",
        ).start()

    @Slot(dict)
    def _apply_productivity(self, payload):
        tasks = list(payload.get("tasks") or [])
        reminders = list(payload.get("reminders") or [])
        notes = list(payload.get("notes") or [])
        self._last_reminders_snapshot = reminders
        self.tasks_model.replace_items(tasks)
        self.reminders_model.replace_items(reminders)
        self.notes_model.replace_items(notes)
        self._task_count = len(tasks)
        self._reminder_count = len(reminders)
        self._note_count = len(notes)
        self._rebuild_agenda_calendar()
        self.productivityChanged.emit()


    @Slot(dict)
    def _apply_google_tasks(self, payload):
        status = dict(payload.get("status") or {})
        data = dict(payload.get("data") or {})
        connected = bool(status.get("connected"))
        self._google_sync_active = connected
        rows = []
        if connected and bool(data.get("ok")):
            for raw in list(data.get("items") or []):
                if not isinstance(raw, dict):
                    continue
                rows.append({
                    "id": 0,
                    "external_id": str(
                        raw.get("external_id")
                        or raw.get("task_id")
                        or ""
                    ),
                    "title": str(raw.get("title") or "Tâche Google"),
                    "status": str(raw.get("status") or ""),
                    "due_date": str(raw.get("due_date") or raw.get("due") or ""),
                    "description": str(raw.get("description") or raw.get("notes") or ""),
                    "source": "GOOGLE",
                    "source_label": "GOOGLE TASKS",
                })
            label = str(status.get("account_label") or "Google").strip()
            self._google_tasks_status = f"Google Tasks · synchronisé · {label}"
        else:
            error = str(data.get("error") or status.get("error") or "").strip()
            if error in {"tasks_reconsent_required", "google_tasks_reconsent_required"}:
                self._google_tasks_status = "Google Tasks · réautorisation OAuth requise"
            elif connected:
                self._google_tasks_status = "Google Tasks · indisponible" + (f" · {error}" if error else "")
            else:
                self._google_tasks_status = "Compte Google non connecté"
        self.google_tasks_model.replace_items(rows)
        self._google_tasks_count = len(rows)
        self.productivityChanged.emit()

    @Slot(dict)
    def _apply_google_calendar(self, payload):
        status = dict(payload.get("status") or {})
        data = dict(payload.get("data") or {})
        connected = bool(status.get("connected"))
        self._google_sync_active = connected
        rows = []
        if connected and bool(data.get("ok")):
            for raw in list(data.get("items") or []):
                if not isinstance(raw, dict):
                    continue
                rows.append({
                    "id": 0,
                    "external_id": str(
                        raw.get("external_id")
                        or raw.get("event_id")
                        or ""
                    ),
                    "title": str(raw.get("title") or "Événement Google"),
                    "trigger_at": str(raw.get("trigger_at") or raw.get("start_time") or raw.get("start") or ""),
                    "end_at": str(raw.get("end_at") or raw.get("end_time") or raw.get("end") or ""),
                    "description": str(raw.get("description") or raw.get("location") or ""),
                    "source": "GOOGLE",
                    "source_label": "GOOGLE CALENDAR",
                })
            label = str(status.get("account_label") or "Google").strip()
            self._google_calendar_status = f"Google Calendar · synchronisé · {label}"
        else:
            error = str(data.get("error") or status.get("error") or "").strip()
            self._google_calendar_status = (
                "Google Calendar · indisponible" + (f" · {error}" if error else "")
                if connected else "Compte Google non connecté"
            )
        self.google_calendar_model.replace_items(rows)
        self._last_google_calendar_snapshot = rows
        self._google_calendar_count = len(rows)
        self._rebuild_agenda_calendar()
        self.productivityChanged.emit()


    @Slot(dict)
    def _apply_memory(self, payload):
        records = list(payload.get("records") or [])
        context = list(payload.get("context") or [])
        self.memories_model.replace_items(records)
        self.memory_context_model.replace_items(context)
        self._memory_count = int(payload.get("count") or len(records))
        self._sensitive_memory_count = int(payload.get("sensitive_count") or 0)
        self._memory_private = bool(payload.get("private_mode"))
        self._memory_auto_capture = bool(payload.get("auto_capture"))
        self.memoryChanged.emit()

    def _post_google_mutation(
        self,
        path,
        payload,
        success_text,
        refresh_kind,
    ):
        if (
            not self._connected
            or not self._interaction_ready
            or not self._session
        ):
            self._set_data_status("Core indisponible", False)
            return False
        if not self._google_sync_active:
            self._set_data_status("Compte Google non connecté", False)
            return False

        session = dict(self._session)

        def worker():
            try:
                result = self._request_json(
                    session,
                    path,
                    method="POST",
                    payload=dict(payload or {}),
                    timeout=15.0,
                )
                if not isinstance(result, dict):
                    result = {}
                result["_success_text"] = str(success_text or "")
                result["_refresh_kind"] = str(refresh_kind or "")
                self._googleMutationReceived.emit(result)
            except Exception as exc:
                self._googleMutationReceived.emit(
                    {
                        "ok": False,
                        "error": type(exc).__name__,
                        "_success_text": str(success_text or ""),
                        "_refresh_kind": str(refresh_kind or ""),
                    }
                )

        threading.Thread(
            target=worker,
            daemon=True,
            name="AuraQtGoogleMutation",
        ).start()
        return True

    @Slot(dict)
    def _apply_google_mutation(self, payload):
        ok = bool(payload.get("ok"))
        success_text = str(payload.get("_success_text") or "").strip()
        refresh_kind = str(payload.get("_refresh_kind") or "").strip()

        if ok:
            self._set_data_status(
                success_text or "Google synchronisé",
                True,
            )
            if refresh_kind in {"tasks", "all"}:
                QTimer.singleShot(180, self.refreshGoogleTasks)
            if refresh_kind in {"calendar", "all"}:
                QTimer.singleShot(220, self.refreshGoogleCalendar)
            return

        error = str(
            payload.get("error")
            or "google_action_failed"
        ).strip()
        detail = str(payload.get("detail") or "").strip()
        message = error
        if detail and detail != error:
            message += " · " + detail
        self._set_data_status(
            "Action Google impossible · " + message,
            False,
        )

    def _post_data_action(self, action, payload, success_text):
        if not self._connected or not self._interaction_ready or not self._session:
            self._set_data_status("Core indisponible", False)
            return False

        body = {"action": str(action)}
        body.update(dict(payload or {}))
        session = dict(self._session)

        def worker():
            try:
                result = self._request_json(
                    session,
                    "/api/action",
                    method="POST",
                    payload=body,
                    timeout=4.0,
                )
                ok = bool(result.get("ok"))
                error = "" if ok else str(result.get("error") or "action_rejected")
                self._actionCompleted.emit(
                    str(action) + "|" + str(success_text or ""),
                    ok,
                    error,
                )
            except Exception as exc:
                self._actionCompleted.emit(
                    str(action) + "|" + str(success_text or ""),
                    False,
                    type(exc).__name__,
                )

        threading.Thread(
            target=worker,
            daemon=True,
            name=f"AuraQtDataAction-{action}",
        ).start()
        return True

    def _rebuild_agenda_calendar(self):
        self.agenda_calendar_model.rebuild(
            self._agenda_year,
            self._agenda_month,
            self._last_reminders_snapshot,
            self._last_google_calendar_snapshot,
        )
        labels = [
            "JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN",
            "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE",
        ]
        self._agenda_month_label = f"{labels[self._agenda_month - 1]} {self._agenda_year}"
        self.agendaChanged.emit()

    @Slot()
    def agendaPreviousMonth(self):
        self._agenda_month -= 1
        if self._agenda_month < 1:
            self._agenda_month = 12
            self._agenda_year -= 1
        self._rebuild_agenda_calendar()

    @Slot()
    def agendaNextMonth(self):
        self._agenda_month += 1
        if self._agenda_month > 12:
            self._agenda_month = 1
            self._agenda_year += 1
        self._rebuild_agenda_calendar()

    @Slot()
    def agendaToday(self):
        now = datetime.now()
        self._agenda_year = now.year
        self._agenda_month = now.month
        self._rebuild_agenda_calendar()

    @Slot(bool)
    def setShowSensitiveMemories(self, enabled):
        enabled = bool(enabled)
        if enabled != self._show_sensitive_memories:
            self._show_sensitive_memories = enabled
            self.memoryChanged.emit()
            self.refreshMemory()

    @Slot(str, result=bool)
    def clearMemoryProfile(self, confirm_text):
        if str(confirm_text or "").strip().upper() != "EFFACER":
            self._set_data_status("Confirmation EFFACER requise", False)
            return False
        return self._post_data_action(
            "memory_clear_profile",
            {"confirm": "EFFACER"},
            "Profil mémoire effacé",
        )

    @Slot(str, str, result=bool)
    def createGoogleTask(self, title, due_date=""):
        title = str(title or "").strip()[:280]
        due_date = str(due_date or "").strip()[:80]
        if not title:
            self._set_data_status("Titre Google Task requis", False)
            return False
        return self._post_google_mutation(
            "/api/qt/google/task/create",
            {"title": title, "due": due_date},
            "Google Task créée",
            "tasks",
        )

    @Slot(str, str, str, result=bool)
    def updateGoogleTask(self, task_id, title, due_date=""):
        task_id = str(task_id or "").strip()
        title = str(title or "").strip()[:280]
        due_date = str(due_date or "").strip()[:80]
        if not task_id or not title:
            self._set_data_status(
                "Google Task : identifiant et titre requis",
                False,
            )
            return False
        return self._post_google_mutation(
            "/api/qt/google/task/update",
            {
                "task_id": task_id,
                "title": title,
                "due": due_date,
            },
            "Google Task modifiée",
            "tasks",
        )

    @Slot(str, result=bool)
    def completeGoogleTask(self, task_id):
        task_id = str(task_id or "").strip()
        if not task_id:
            return False
        return self._post_google_mutation(
            "/api/qt/google/task/complete",
            {"task_id": task_id},
            "Google Task terminée",
            "tasks",
        )

    @Slot(str, result=bool)
    def deleteGoogleTask(self, task_id):
        task_id = str(task_id or "").strip()
        if not task_id:
            return False
        return self._post_google_mutation(
            "/api/qt/google/task/delete",
            {"task_id": task_id},
            "Google Task supprimée",
            "tasks",
        )

    @Slot(str, str, str, str, result=bool)
    def createGoogleEvent(self, title, start_at, end_at="", description=""):
        title = str(title or "").strip()[:280]
        start_at = str(start_at or "").strip()[:80]
        end_at = str(end_at or "").strip()[:80]
        description = str(description or "").strip()[:4000]
        if not title or not start_at:
            self._set_data_status(
                "Titre et début Google Calendar requis",
                False,
            )
            return False
        return self._post_google_mutation(
            "/api/qt/google/calendar/create",
            {
                "title": title,
                "start": start_at,
                "end": end_at,
                "description": description,
            },
            "Événement Google Calendar créé",
            "calendar",
        )

    @Slot(str, str, str, str, str, result=bool)
    def updateGoogleEvent(
        self,
        event_id,
        title,
        start_at,
        end_at="",
        description="",
    ):
        event_id = str(event_id or "").strip()
        title = str(title or "").strip()[:280]
        start_at = str(start_at or "").strip()[:80]
        end_at = str(end_at or "").strip()[:80]
        description = str(description or "").strip()[:4000]

        if not event_id or not title or not start_at:
            self._set_data_status(
                "Google Calendar : événement, titre et début requis",
                False,
            )
            return False

        return self._post_google_mutation(
            "/api/qt/google/calendar/update",
            {
                "event_id": event_id,
                "title": title,
                "start": start_at,
                "end": end_at,
                "description": description,
            },
            "Événement Google Calendar modifié",
            "calendar",
        )

    @Slot(str, result=bool)
    def deleteGoogleEvent(self, event_id):
        event_id = str(event_id or "").strip()
        if not event_id:
            return False
        return self._post_google_mutation(
            "/api/qt/google/calendar/delete",
            {"event_id": event_id},
            "Événement Google Calendar supprimé",
            "calendar",
        )

    @Slot(str, str, result=bool)
    def createTask(self, title, due_date=""):
        title = str(title or "").strip()[:280]
        due_date = str(due_date or "").strip()[:64]
        if not title:
            self._set_data_status("Titre de tâche requis", False)
            return False
        return self._post_data_action(
            "task_create",
            {"title": title, "due_date": due_date},
            "Tâche créée",
        )

    @Slot(str, result=bool)
    def completeTask(self, identifier):
        identifier = str(identifier or "").strip()[:280]
        if not identifier:
            return False
        return self._post_data_action(
            "task_complete",
            {"identifier": identifier},
            "Tâche terminée",
        )

    @Slot(str, str, result=bool)
    def createReminder(self, content, trigger_at):
        content = str(content or "").strip()[:500]
        trigger_at = str(trigger_at or "").strip()[:80]
        if not content or not trigger_at:
            self._set_data_status("Texte et échéance requis", False)
            return False
        return self._post_data_action(
            "reminder_create",
            {"content": content, "trigger_at": trigger_at},
            "Rappel créé",
        )

    @Slot(int, result=bool)
    def deleteReminder(self, reminder_id):
        try:
            rid = int(reminder_id)
        except Exception:
            return False
        if rid <= 0:
            return False
        return self._post_data_action(
            "reminder_delete",
            {"id": rid},
            "Rappel supprimé",
        )

    @Slot(str, str, result=bool)
    def createNote(self, title, content):
        title = str(title or "").strip()[:220]
        content = str(content or "").replace("\x00", " ").strip()[:8000]
        if not content:
            self._set_data_status("Contenu de note requis", False)
            return False
        return self._post_data_action(
            "note_create",
            {"title": title, "content": content},
            "Note enregistrée",
        )

    @Slot(int, result=bool)
    def deleteNote(self, note_id):
        try:
            nid = int(note_id)
        except Exception:
            return False
        if nid <= 0:
            return False
        return self._post_data_action(
            "note_delete",
            {"id": nid},
            "Note supprimée",
        )

    @Slot(str, str, int, result=bool)
    def createMemory(self, content, memory_type="fact", importance=3):
        content = str(content or "").strip()[:1800]
        memory_type = str(memory_type or "fact").strip().casefold()[:40]
        allowed = {"fact", "preference", "project", "goal", "habit"}
        if memory_type not in allowed:
            memory_type = "fact"
        importance = max(1, min(5, int(importance or 3)))
        if not content:
            self._set_data_status("Contenu mémoire requis", False)
            return False
        return self._post_data_action(
            "memory_create",
            {
                "content": content,
                "memory_type": memory_type,
                "importance": importance,
            },
            "Mémoire enregistrée",
        )

    @Slot(int, result=bool)
    def deleteMemory(self, memory_id):
        try:
            mid = int(memory_id)
        except Exception:
            return False
        if mid <= 0:
            return False
        return self._post_data_action(
            "memory_delete",
            {"id": mid},
            "Mémoire supprimée",
        )

    @Slot(bool, result=bool)
    def setMemoryPrivate(self, enabled):
        return self._post_data_action(
            "memory_private",
            {"enabled": bool(enabled)},
            "Mode mémoire mis à jour",
        )

    @Slot(str, bool, str)
    def _handle_action_completed(self, action_tag, ok, error):
        action_tag = str(action_tag or "")
        action, _, success_text = action_tag.partition("|")
        if ok:
            if success_text:
                self._set_data_status(success_text, True)
            if action.startswith(("task_", "reminder_", "note_", "refresh_productivity")):
                QTimer.singleShot(260, self.refreshProductivity)
            if action.startswith(("memory_", "refresh_memory")):
                QTimer.singleShot(260, self.refreshMemory)
        else:
            # Do not spam the UI for periodic refresh failures while reconnecting.
            if not action.startswith("refresh_"):
                self._set_data_status(
                    str(error or "Action refusée"),
                    False,
                )

    def _set_connected(self, value):
        value = bool(value)
        if value != self._connected:
            self._connected = value
            self.connectedChanged.emit()

    def _set_ready(self, value):
        value = bool(value)
        if value != self._interaction_ready:
            self._interaction_ready = value
            self.interactionReadyChanged.emit()

    def _set_error(self, value):
        value = str(value or "")
        if value != self._last_error:
            self._last_error = value
            self.lastErrorChanged.emit()

    def _session_candidates(self):
        out = []
        local = os.environ.get("LOCALAPPDATA")
        if local:
            out.append(Path(local) / "AURA" / "ui" / "runtime" / "rc4_2_session.json")

        ui_root = os.environ.get("AURA_UI_ROOT")
        if ui_root:
            p = Path(ui_root).expanduser()
            out.append(p.parent / "runtime" / "rc4_2_session.json")

        root = os.environ.get("AURA_ROOT")
        if root:
            p = Path(root).expanduser()
            out.append(p / "ui" / "runtime" / "rc4_2_session.json")

        # Stable Windows fallback used by the validated RC4.2 deployment.
        if os.name == "nt":
            local_guess = Path.home() / "AppData" / "Local" / "AURA" / "ui" / "runtime" / "rc4_2_session.json"
            out.append(local_guess)

        seen = set()
        unique = []
        for p in out:
            key = str(p).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

    def _load_session(self):
        candidates = self._session_candidates()
        existing = [p for p in candidates if p.is_file()]
        existing.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for path in existing:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                port = int(raw.get("port") or 0)
                token = str(raw.get("token") or "").strip()
                pid = int(raw.get("pid") or 0)
                if not (1 <= port <= 65535):
                    continue
                if len(token) < 24:
                    continue
                return {
                    "path": str(path),
                    "port": port,
                    "token": token,
                    "pid": pid,
                    "release": str(raw.get("release") or ""),
                    "root": str(raw.get("root") or ""),
                }
            except Exception:
                continue
        return None

    @staticmethod
    def _request_json(session, path, method="GET", payload=None, timeout=2.5):
        token = urllib.parse.quote(str(session["token"]), safe="")
        separator = "&" if "?" in str(path) else "?"
        url = f"http://127.0.0.1:{int(session['port'])}{path}{separator}token={token}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(1024 * 1024)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

    @Slot()
    def reconnect(self):
        self._set_connected(False)
        self._set_ready(False)
        self._ensure_connection()

    @Slot()
    def clearConversation(self):
        self.messages.clear()

    def _ensure_connection(self):
        if self._checking:
            return
        if self._connected and self._session is not None:
            if self._sse_thread is None or not self._sse_thread.is_alive():
                self._start_sse(self._session)
            return

        self._checking = True

        def worker():
            try:
                session = self._load_session()
                if session is None:
                    self._connectionError.emit("session_not_found")
                    return
                status = self._request_json(session, "/api/status", timeout=2.0)
                if not bool(status.get("ok")):
                    self._connectionError.emit("status_not_ok")
                    return
                status["_session"] = session
                self._statusReceived.emit(status)
            except urllib.error.HTTPError as exc:
                self._connectionError.emit(f"core_http_{getattr(exc, 'code', 0)}")
            except Exception as exc:
                self._connectionError.emit(type(exc).__name__)
            finally:
                self._checking = False

        threading.Thread(target=worker, daemon=True, name="AuraQtCoreProbe").start()

    @Slot(dict)
    def _apply_status(self, status):
        session = dict(status.get("_session") or {})
        if not session:
            return

        previous_key = None
        if self._session:
            previous_key = (self._session.get("port"), self._session.get("token"))
        new_key = (session.get("port"), session.get("token"))

        self._session = session
        self._write_diag(
            "core_status",
            {
                "pid": session.get("pid"),
                "port": session.get("port"),
                "release": status.get("release") or session.get("release"),
                "interaction_ready": bool(status.get("interaction_ready")),
                "voice_state": status.get("voice_state"),
            },
        )
        self._set_connected(True)
        self._set_ready(bool(status.get("interaction_ready")))
        self._set_error("")

        voice = str(status.get("voice_state") or "standby")
        if voice != self._voice_status:
            self._voice_status = voice
            self.voiceStatusChanged.emit()

        label = "AURA RC4.2 Core"
        release = str(status.get("release") or session.get("release") or "").strip()
        if release:
            label += f" · {release}"
        if label != self._session_label:
            self._session_label = label
            self.sessionChanged.emit()

        if previous_key != new_key or self._sse_thread is None or not self._sse_thread.is_alive():
            self._start_sse(session)

        if self._interaction_ready:
            self.uiStateRequested.emit("IDLE")
            QTimer.singleShot(120, self.refreshAllData)

    def _start_sse(self, session):
        key = (session.get("port"), session.get("token"))
        if self._sse_thread is not None and self._sse_thread.is_alive() and self._sse_key == key:
            return

        if self._last_event_session_key != key:
            self._last_event_seq = 0
            self._last_event_session_key = key

        self._sse_stop.set()
        self._sse_stop = threading.Event()
        stop_event = self._sse_stop
        self._sse_key = key
        snapshot = dict(session)

        def worker():
            token = urllib.parse.quote(str(snapshot["token"]), safe="")
            failures = 0

            while not stop_event.is_set():
                try:
                    since = max(0, int(self._last_event_seq))
                    url = (
                        f"http://127.0.0.1:{int(snapshot['port'])}/api/events"
                        f"?token={token}&since={since}"
                    )
                    req = urllib.request.Request(
                        url,
                        headers={"Accept": "text/event-stream"},
                        method="GET",
                    )
                    with urllib.request.urlopen(req, timeout=28.0) as response:
                        failures = 0
                        for raw_line in response:
                            if stop_event.is_set():
                                return
                            try:
                                line = raw_line.decode("utf-8", "replace").strip()
                            except Exception:
                                continue
                            if not line.startswith("data:"):
                                continue
                            body = line[5:].strip()
                            if not body:
                                continue
                            try:
                                event = json.loads(body)
                            except Exception:
                                continue
                            if not isinstance(event, dict):
                                continue
                            try:
                                seq = int(event.get("seq") or 0)
                            except Exception:
                                seq = 0
                            if seq > 0:
                                if seq <= int(self._last_event_seq):
                                    continue
                                self._last_event_seq = seq
                            self._eventReceived.emit(event)
                except Exception:
                    # RC4.2 server explicitly treats ConnectionAbortedError
                    # as a normal SSE client disconnect on Windows. SSE loss
                    # must never flip Core readiness; heartbeat owns liveness.
                    failures += 1
                    if stop_event.wait(min(3.0, 0.35 * failures)):
                        return

        self._sse_thread = threading.Thread(
            target=worker,
            daemon=True,
            name="AuraQtCoreSSE",
        )
        self._sse_thread.start()

    @Slot(str, result=bool)
    def sendMessage(self, text):
        text = str(text or "").replace("\x00", "").strip()[:4000]
        if not text or not self._connected or not self._interaction_ready or not self._session:
            return False

        self.messages.append_message("user", text, "qt-native")
        self.messageAdded.emit()
        self._pending_user.append((text, time.monotonic()))
        self._pending_user = self._pending_user[-12:]
        self.uiStateRequested.emit("THINKING")

        session = dict(self._session)

        def worker():
            try:
                result = self._request_json(
                    session,
                    "/api/action",
                    method="POST",
                    payload={"action": "send_message", "text": text},
                    timeout=4.0,
                )
                if not bool(result.get("ok")):
                    self._connectionError.emit(str(result.get("error") or "send_rejected"))
            except Exception as exc:
                self._connectionError.emit(type(exc).__name__)

        threading.Thread(target=worker, daemon=True, name="AuraQtSendMessage").start()
        return True

    def _post_action(self, action, extra=None):
        if not self._connected or not self._interaction_ready or not self._session:
            return
        payload = {"action": str(action)}
        if extra:
            payload.update(dict(extra))
        session = dict(self._session)

        def worker():
            try:
                result = self._request_json(
                    session,
                    "/api/action",
                    method="POST",
                    payload=payload,
                    timeout=3.0,
                )
                if not bool(result.get("ok")):
                    self._connectionError.emit(str(result.get("error") or "command_rejected"))
            except Exception as exc:
                self._connectionError.emit(type(exc).__name__)

        threading.Thread(target=worker, daemon=True, name=f"AuraQtAction-{action}").start()

    @Slot()
    def micStart(self):
        self.uiStateRequested.emit("LISTENING")
        self._post_action("mic_start")

    @Slot()
    def micStop(self):
        self._post_action("mic_stop")

    @Slot()
    def stopSpeaking(self):
        self._post_action("stop_speaking")

    def _heartbeat(self):
        if not self._connected or not self._session:
            return
        session = dict(self._session)

        def worker():
            try:
                result = self._request_json(
                    session,
                    "/api/heartbeat",
                    method="POST",
                    payload={},
                    timeout=2.2,
                )
                if not bool(result.get("ok")):
                    raise RuntimeError("heartbeat_rejected")
                self._heartbeat_failures = 0
                if not self._connected:
                    self._set_connected(True)
                    self._ensure_connection()
            except Exception as exc:
                self._heartbeat_failures += 1
                if self._heartbeat_failures >= 3:
                    self._connectionError.emit(
                        "heartbeat:" + type(exc).__name__
                    )

        threading.Thread(target=worker, daemon=True, name="AuraQtHeartbeat").start()

    @Slot(dict)
    def _handle_event(self, event):
        event_type = str(event.get("type") or "")
        data = event.get("data")
        if not isinstance(data, dict):
            data = {}

        self._set_connected(True)
        self._set_last_event(event_type)

        if event_type.startswith(("task.", "reminder.", "note.", "productivity.")):
            QTimer.singleShot(180, self.refreshProductivity)
        if event_type.startswith("memory."):
            QTimer.singleShot(180, self.refreshMemory)

        if event_type in {
            "startup_ready",
            "bridge.ready",
            "state",
            "provider",
            "operation_started",
            "operation_finished",
            "voice_status",
            "voice_transcription",
            "user_message",
            "error",
        }:
            safe_data = dict(data)
            self._write_diag(event_type, safe_data)

        if event_type == "startup_ready":
            self._set_ready(bool(data.get("interaction_ready", data.get("ready", True))))
            if self._interaction_ready:
                self._restore_idle_if_safe()
            return

        if event_type == "bridge.ready":
            self._set_connected(True)
            return

        if event_type == "state":
            raw_state = str(data.get("state") or "IDLE").strip().upper()
            # Accept both "IDLE" and Enum string forms such as "AuraState.IDLE".
            state = raw_state.rsplit(".", 1)[-1]
            aliases = {
                "PROCESSING": "THINKING",
                "ANALYZING": "THINKING",
                "EXECUTING": "THINKING",
                "ACTING": "THINKING",
            }
            state = aliases.get(state, state)
            if state in {"IDLE", "THINKING", "LISTENING", "SPEAKING", "ERROR"}:
                self.uiStateRequested.emit(state)
            return

        if event_type == "provider":
            provider = str(data.get("provider") or "").strip()
            model = str(data.get("model") or "").strip()
            if provider != self._provider:
                self._provider = provider
                self.providerChanged.emit()
            if model != self._model:
                self._model = model
                self.modelChanged.emit()
                self.providerChanged.emit()
            return

        if event_type == "operation_started":
            self._operation_depth += 1
            self.uiStateRequested.emit("THINKING")
            return

        if event_type == "operation_finished":
            self._operation_depth = max(0, self._operation_depth - 1)
            self._restore_idle_if_safe()
            return

        if event_type == "voice_status":
            status = str(data.get("status") or "").strip()
            if status != self._voice_status:
                self._voice_status = status
                self.voiceStatusChanged.emit()

            folded = status.casefold()
            if any(x in folded for x in ("listen", "record")):
                self.uiStateRequested.emit("LISTENING")
            elif any(x in folded for x in ("speak", "play")):
                self.uiStateRequested.emit("SPEAKING")
            elif any(x in folded for x in ("process", "transcrib", "recogn")):
                self.uiStateRequested.emit("THINKING")
            elif any(x in folded for x in ("idle", "ready", "standby", "stopped", "stop")):
                self._restore_idle_if_safe()
            return

        if event_type == "voice_amplitude":
            try:
                value = max(0.0, min(1.0, float(data.get("level") or 0.0)))
            except Exception:
                value = 0.0
            if abs(value - self._voice_amplitude) >= 0.002:
                self._voice_amplitude = value
                self.voiceAmplitudeChanged.emit()
            return

        if event_type == "user_message":
            text = str(data.get("text") or data.get("message") or data.get("content") or "").strip()
            if not text:
                return
            now = time.monotonic()
            matched = False
            remaining = []
            for pending_text, ts in self._pending_user:
                if now - ts > 12.0:
                    continue
                if not matched and pending_text == text:
                    matched = True
                    continue
                remaining.append((pending_text, ts))
            self._pending_user = remaining
            if not matched:
                self.messages.append_message("user", text, str(data.get("source") or "core"))
                self.messageAdded.emit()
            self.uiStateRequested.emit("THINKING")
            return

        if event_type == "aura_message":
            # shell_host.py publishes the canonical Core response in data["text"].
            text = str(data.get("text") or data.get("message") or data.get("content") or "")
            self._set_last_aura_payload(text, data)
            clean = text.strip()
            if clean:
                self.messages.append_message("assistant", clean, str(data.get("source") or "core"))
                self.messageAdded.emit()

            if self._voice_busy():
                folded = str(self._voice_status or "").casefold()
                if any(x in folded for x in ("speak", "play")):
                    self.uiStateRequested.emit("SPEAKING")
            else:
                self._restore_idle_if_safe()
            return

        if event_type == "voice_transcription":
            text = str(data.get("text") or "").strip()
            if text:
                self._set_error(f"Transcription: {text[:180]}")
                QTimer.singleShot(1800, lambda: self._set_error(""))
            return

        if event_type == "error":
            text = str(data.get("text") or data.get("message") or "Core error").strip()
            self._set_error(text[:500])
            self.messages.append_message("system", text[:1000], "core-error")
            self.messageAdded.emit()
            self.uiStateRequested.emit("ERROR")
            QTimer.singleShot(1600, self._restore_idle_if_safe)
            return

    @Slot(result=str)
    def diagnosticPath(self):
        return str(self._diag_path)

    @Slot()
    def clearDiagnostics(self):
        try:
            self._diag_path.unlink(missing_ok=True)
        except Exception:
            pass
        self._last_aura_chars = 0
        self._last_aura_preview = ""
        self._last_event_type = ""
        self.lastAuraCharsChanged.emit()
        self.lastAuraPreviewChanged.emit()
        self.lastEventTypeChanged.emit()

    @Slot(str)
    def _handle_connection_error(self, reason):
        reason = str(reason or "core_unavailable")
        self._write_diag("connection_error", {"reason": reason})

        # Only verified liveness failures may take the Core offline.
        if reason.startswith("heartbeat:") or reason in {
            "session_not_found", "status_not_ok"
        } or reason.startswith("core_http_"):
            self._set_error("Core temporairement indisponible")
            self._set_connected(False)
            self._set_ready(False)
            self.uiStateRequested.emit("IDLE")
            QTimer.singleShot(700, self._ensure_connection)
            return

        # Command/provider errors remain visible without lying about Core state.
        self._set_error(reason)
        QTimer.singleShot(1800, lambda: self._set_error(""))



# AURA_MUSIC_CENTER_PARITY_FIX35
class MusicPlaylistModel(QAbstractListModel):
    IdRole = Qt.UserRole + 1
    TitleRole = Qt.UserRole + 2
    ArtistRole = Qt.UserRole + 3
    AlbumRole = Qt.UserRole + 4
    DurationRole = Qt.UserRole + 5
    ExtensionRole = Qt.UserRole + 6
    MediaTypeRole = Qt.UserRole + 7
    YearRole = Qt.UserRole + 8
    TrackRole = Qt.UserRole + 9
    CoverRole = Qt.UserRole + 10
    MetadataSourceRole = Qt.UserRole + 11
    FavoriteRole = Qt.UserRole + 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    def roleNames(self):
        return {
            self.IdRole: b"itemId", self.TitleRole: b"title", self.ArtistRole: b"artist",
            self.AlbumRole: b"album", self.DurationRole: b"durationLabel",
            self.ExtensionRole: b"extension", self.MediaTypeRole: b"mediaType",
            self.YearRole: b"year", self.TrackRole: b"track", self.CoverRole: b"coverDataUri",
            self.MetadataSourceRole: b"metadataSource", self.FavoriteRole: b"favorite",
        }

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() < 0 or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        if role == self.IdRole: return str(item.get("id") or "")
        if role == self.TitleRole: return str(item.get("title") or "Media")
        if role == self.ArtistRole: return str(item.get("artist") or "")
        if role == self.AlbumRole: return str(item.get("album") or "")
        if role == self.DurationRole:
            sec = int(float(item.get("duration_seconds") or 0))
            return "--:--" if sec <= 0 else f"{sec//60}:{sec%60:02d}"
        if role == self.ExtensionRole: return str(item.get("extension") or "").replace(".", "")
        if role == self.MediaTypeRole: return str(item.get("media_type") or "")
        if role == self.YearRole: return str(item.get("year") or "")[:4]
        if role == self.TrackRole: return str(item.get("track") or "")
        if role == self.CoverRole: return str(item.get("cover_data_uri") or "")
        if role == self.MetadataSourceRole: return str(item.get("metadata_source") or "")
        if role == self.FavoriteRole: return bool(item.get("__favorite"))
        return None

    def replace_items(self, rows):
        self.beginResetModel()
        self._items = [dict(x) for x in list(rows or []) if isinstance(x, dict)]
        self.endResetModel()

    def items(self):
        return [dict(x) for x in self._items]


class MusicQtBridge(QObject):
    availableChanged = Signal(); stateChanged = Signal(); trackChanged = Signal(); volumeChanged = Signal()
    playlistChanged = Signal(); libraryChanged = Signal(); collectionsChanged = Signal(); resumeChanged = Signal()
    modesChanged = Signal(); systemMediaChanged = Signal(); lastErrorChanged = Signal()
    _snapshotReceived = Signal(dict); _errorReceived = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = MusicPlaylistModel(self)
        self.libraryModel = MusicPlaylistModel(self)
        self._source_items=[]; self._available=False; self._playing=False; self._paused=False
        self._current_id=""; self._current_title=""; self._current_artist=""; self._current_album=""
        self._current_cover=""; self._current_extension=""; self._current_year=""; self._current_metadata_source=""
        self._volume=80; self._position=0.0; self._duration=0.0; self._last_error=""
        self._favorites=set(); self._history=[]; self._collections=[]; self._resume={}
        self._hotkeys_label="NON DÉTECTÉ"; self._smtc_label="NON DÉTECTÉ"
        self._library_query=""; self._library_sort="playlist"; self._library_favorites_only=False; self._library_duplicates_only=False
        self._repeat_mode="off"; self._shuffle=False; self._auto_advancing=False; self._last_ended_id=""
        self._busy=False; self._last_full_fetch=0.0; self._last_start_attempt=0.0; self._base="http://127.0.0.1:18180"
        self._prefs_path=Path(__file__).resolve().parents[1]/"data"/"music_qt_preferences_v35.json"
        self._load_modes()
        self._snapshotReceived.connect(self._apply_snapshot); self._errorReceived.connect(self._apply_error)
        self._poll=QTimer(self); self._poll.setInterval(700); self._poll.timeout.connect(self.refresh); self._poll.start()
        self._heartbeat=QTimer(self); self._heartbeat.setInterval(1600); self._heartbeat.timeout.connect(self._send_heartbeat); self._heartbeat.start()
        QTimer.singleShot(120,self.ensureAvailable)

    @Property(bool, notify=availableChanged)
    def available(self): return self._available
    @Property(bool, notify=stateChanged)
    def playing(self): return self._playing
    @Property(bool, notify=stateChanged)
    def paused(self): return self._paused
    @Property(str, notify=trackChanged)
    def currentId(self): return self._current_id
    @Property(str, notify=trackChanged)
    def currentTitle(self): return self._current_title
    @Property(str, notify=trackChanged)
    def currentArtist(self): return self._current_artist
    @Property(str, notify=trackChanged)
    def currentAlbum(self): return self._current_album
    @Property(str, notify=trackChanged)
    def currentCover(self): return self._current_cover
    @Property(str, notify=trackChanged)
    def currentExtension(self): return self._current_extension.replace(".","")
    @Property(str, notify=trackChanged)
    def currentYear(self): return self._current_year[:4]
    @Property(str, notify=trackChanged)
    def currentMetadataSource(self): return self._current_metadata_source
    @Property(bool, notify=libraryChanged)
    def currentFavorite(self): return bool(self._current_id and self._current_id in self._favorites)
    @Property(int, notify=volumeChanged)
    def volume(self): return self._volume
    @Property(float, notify=stateChanged)
    def progress(self): return 0.0 if self._duration<=0 else max(0.0,min(1.0,self._position/self._duration))
    @Property(str, notify=stateChanged)
    def positionLabel(self): return self._fmt(self._position)
    @Property(str, notify=stateChanged)
    def durationLabel(self): return "--:--" if self._duration<=0 else self._fmt(self._duration)
    @Property(int, notify=playlistChanged)
    def playlistCount(self): return len(self._source_items)
    @Property(str, notify=lastErrorChanged)
    def lastError(self): return self._last_error
    @Property(str, notify=modesChanged)
    def repeatMode(self): return self._repeat_mode
    @Property(bool, notify=modesChanged)
    def shuffle(self): return self._shuffle
    @Property("QVariantList", notify=libraryChanged)
    def history(self): return list(self._history)
    @Property("QVariantList", notify=collectionsChanged)
    def collections(self): return list(self._collections)
    @Property(bool, notify=resumeChanged)
    def resumeEligible(self):
        rid=str(self._resume.get("item_id") or ""); pos=float(self._resume.get("position_seconds") or 0); dur=float(self._resume.get("duration_seconds") or 0)
        return bool(rid and pos>=10 and dur>20 and dur-pos>=10 and any(str(x.get("id") or "")==rid for x in self._source_items) and not self._playing)
    @Property(str, notify=resumeChanged)
    def resumeTitle(self): return str(self._resume.get("title") or "Morceau")
    @Property(str, notify=resumeChanged)
    def resumePositionLabel(self): return f"{self._fmt(self._resume.get('position_seconds') or 0)} / {self._fmt(self._resume.get('duration_seconds') or 0)}"
    @Property(str, notify=systemMediaChanged)
    def hotkeysLabel(self): return self._hotkeys_label
    @Property(str, notify=systemMediaChanged)
    def smtcLabel(self): return self._smtc_label

    def _fmt(self,s):
        sec=max(0,int(float(s or 0))); return f"{sec//60}:{sec%60:02d}"

    def _request(self,path,method="GET",payload=None,timeout=1.6):
        data=json.dumps(payload).encode("utf-8") if payload is not None else None
        req=urllib.request.Request(self._base+path,data=data,headers={"Content-Type":"application/json"},method=method)
        with urllib.request.urlopen(req,timeout=timeout) as resp: raw=resp.read()
        result=json.loads(raw.decode("utf-8") or "{}")
        if isinstance(result,dict) and result.get("ok") is False: raise RuntimeError(str(result.get("error") or result.get("reason") or "music_bridge_rejected"))
        return result if isinstance(result,dict) else {}

    def _candidate_roots(self):
        roots=[]; env_root=str(os.environ.get("AURA_ROOT") or "").strip()
        if env_root: roots.append(Path(env_root))
        roots.append(Path(r"C:\AURA GPT version"))
        try: roots.append(Path(__file__).resolve().parents[1])
        except Exception: pass
        seen=set()
        for root in roots:
            try: resolved=root.resolve()
            except Exception: resolved=root
            key=str(resolved).casefold()
            if key in seen: continue
            seen.add(key); yield resolved

    def _try_start_service(self):
        now=time.monotonic()
        if now-self._last_start_attempt<8.0: return
        self._last_start_attempt=now
        for root in self._candidate_roots():
            bat=root/"runtime"/"start_aura_music_premium_bridge_v180.bat"
            if bat.is_file():
                try:
                    subprocess.Popen(["cmd.exe","/c",str(bat)],cwd=str(root),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)); return
                except Exception: pass

    def _load_modes(self):
        try:
            if self._prefs_path.is_file():
                d=json.loads(self._prefs_path.read_text(encoding="utf-8")); r=str(d.get("repeat_mode") or "off")
                if r in {"off","all","one"}: self._repeat_mode=r
                self._shuffle=bool(d.get("shuffle"))
        except Exception: pass

    def _save_modes(self):
        try:
            self._prefs_path.parent.mkdir(parents=True,exist_ok=True)
            self._prefs_path.write_text(json.dumps({"repeat_mode":self._repeat_mode,"shuffle":self._shuffle},indent=2),encoding="utf-8")
        except Exception: pass

    def _decorate(self,rows):
        out=[]
        for row in list(rows or []):
            if isinstance(row,dict):
                x=dict(row); x["__favorite"]=str(x.get("id") or "") in self._favorites; out.append(x)
        return out

    def _refresh_models(self):
        self.model.replace_items(self._decorate(self._source_items)); self._apply_library_view(); self.playlistChanged.emit()

    def _normalize(self,v):
        import unicodedata
        raw=unicodedata.normalize("NFD",str(v or "")); raw="".join(c for c in raw if unicodedata.category(c)!="Mn")
        return " ".join("".join(c.lower() if c.isalnum() else " " for c in raw).split())

    def _apply_library_view(self):
        rows=self._decorate(self._source_items); q=self._normalize(self._library_query)
        if q: rows=[x for x in rows if q in self._normalize(" ".join([str(x.get("title") or ""),str(x.get("artist") or ""),str(x.get("album") or ""),str(x.get("year") or "")]))]
        if self._library_favorites_only: rows=[x for x in rows if x.get("__favorite")]
        if self._library_duplicates_only:
            buckets={}
            for x in rows:
                k=(self._normalize(x.get("artist")),self._normalize(x.get("title")))
                if all(k): buckets.setdefault(k,[]).append(str(x.get("id") or ""))
            dup={i for ids in buckets.values() if len(ids)>1 for i in ids}; rows=[x for x in rows if str(x.get("id") or "") in dup]
        recent={}
        for idx,row in enumerate(self._history):
            rid=str(row.get("id") or "")
            if rid and rid not in recent: recent[rid]=len(self._history)-idx
        m=self._library_sort
        if m=="title": rows.sort(key=lambda x:(self._normalize(x.get("title")),self._normalize(x.get("artist"))))
        elif m=="artist": rows.sort(key=lambda x:(self._normalize(x.get("artist")),self._normalize(x.get("title"))))
        elif m=="album": rows.sort(key=lambda x:(self._normalize(x.get("album")),self._normalize(x.get("track")),self._normalize(x.get("title"))))
        elif m=="year":
            def ky(x):
                try:y=int(str(x.get("year") or "")[:4])
                except Exception:y=-1
                return(-y,self._normalize(x.get("artist")),self._normalize(x.get("title")))
            rows.sort(key=ky)
        elif m=="recent": rows.sort(key=lambda x:(-recent.get(str(x.get("id") or ""),0),self._normalize(x.get("title"))))
        self.libraryModel.replace_items(rows)

    def _source_index(self,item_id):
        wanted=str(item_id or "")
        for i,row in enumerate(self._source_items):
            if str(row.get("id") or "")==wanted:return i
        return -1

    @Slot()
    def ensureAvailable(self):
        def worker():
            try:self._request("/health",timeout=.7);self._snapshotReceived.emit({"available":True});self.refreshAll()
            except Exception:
                self._try_start_service();time.sleep(.75)
                try:self._request("/health",timeout=.9);self._snapshotReceived.emit({"available":True});self.refreshAll()
                except Exception:self._errorReceived.emit("VLC bridge hors ligne")
        threading.Thread(target=worker,daemon=True).start()

    @Slot()
    def refresh(self):
        if self._busy:return
        self._busy=True; full=(time.monotonic()-self._last_full_fetch)>4.0
        def worker():
            try:
                h=self._request("/health",timeout=.7); s=self._request("/status",timeout=.9); snap={"available":bool(h.get("ok",True)),"status":s}
                if full:
                    p=self._request("/playlist",timeout=1.4); l=self._request("/library/state",timeout=1.0); c=self._request("/collections",timeout=1.0); r=self._request("/resume",timeout=1.0); hk=self._request("/media/hotkeys",timeout=.9); sm=self._request("/media/smtc",timeout=.9)
                    snap.update({"playlist":(p.get("playlist") or {}).get("items") or [],"library":l.get("library") or {},"collections":(c.get("collections") or {}).get("items") or [],"resume":r.get("resume") or {},"hotkeys":hk.get("hotkeys") or {},"smtc":sm.get("smtc") or {}})
                self._snapshotReceived.emit(snap)
            except Exception:self._snapshotReceived.emit({"available":False})
            finally:self._busy=False
        threading.Thread(target=worker,daemon=True).start()

    @Slot()
    def refreshAll(self): self._last_full_fetch=0.0;self.refresh()
    @Slot()
    def refreshCollections(self): self.refreshAll()

    def _send_heartbeat(self):
        if not self._available:return
        threading.Thread(target=lambda: self._safe_heartbeat(),daemon=True).start()
    def _safe_heartbeat(self):
        try:self._request("/heartbeat",method="POST",payload={},timeout=.7)
        except Exception:pass

    def _apply_snapshot(self,snap):
        a=bool(snap.get("available"))
        if a!=self._available:self._available=a;self.availableChanged.emit()
        if a and self._last_error:self._last_error="";self.lastErrorChanged.emit()
        lib=snap.get("library")
        if isinstance(lib,dict):self._favorites={str(x) for x in(lib.get("favorites") or []) if str(x)};self._history=[dict(x) for x in(lib.get("history") or []) if isinstance(x,dict)];self.libraryChanged.emit()
        rows=snap.get("playlist")
        if isinstance(rows,list):self._source_items=[dict(x) for x in rows if isinstance(x,dict)];self._refresh_models();self._last_full_fetch=time.monotonic()
        cols=snap.get("collections")
        if isinstance(cols,list):self._collections=[dict(x) for x in cols if isinstance(x,dict)];self.collectionsChanged.emit()
        res=snap.get("resume")
        if isinstance(res,dict):self._resume=dict(res);self.resumeChanged.emit()
        hk=snap.get("hotkeys")
        if isinstance(hk,dict):
            reg=hk.get("registered") or {};self._hotkeys_label=f"{len(reg) if isinstance(reg,dict) else 0} touche(s) · {'ACTIF' if hk.get('thread_alive') else 'INACTIF'}";self.systemMediaChanged.emit()
        sm=snap.get("smtc")
        if isinstance(sm,dict):self._smtc_label="ACTIF" if bool(sm.get("alive") or sm.get("running") or sm.get("ok")) else "DISPONIBLE";self.systemMediaChanged.emit()
        st=snap.get("status")
        if not isinstance(st,dict):return
        pl=bool(st.get("playing"));pa=bool(st.get("paused"))
        if pl!=self._playing or pa!=self._paused:self._playing=pl;self._paused=pa;self.stateChanged.emit()
        nid=str(st.get("current_id") or "");item=next((x for x in self._source_items if str(x.get("id") or "")==nid),{})
        vals=(nid,str(item.get("title") or st.get("current_title") or ""),str(item.get("artist") or ""),str(item.get("album") or ""),str(item.get("cover_data_uri") or ""),str(item.get("extension") or ""),str(item.get("year") or ""),str(item.get("metadata_source") or ""))
        cur=(self._current_id,self._current_title,self._current_artist,self._current_album,self._current_cover,self._current_extension,self._current_year,self._current_metadata_source)
        if vals!=cur:self._current_id,self._current_title,self._current_artist,self._current_album,self._current_cover,self._current_extension,self._current_year,self._current_metadata_source=vals;self.trackChanged.emit();self.libraryChanged.emit()
        v=max(0,min(100,int(float(st.get("volume_percent") or self._volume))))
        if v!=self._volume:self._volume=v;self.volumeChanged.emit()
        p=float(st.get("position_seconds") or 0);d=float(st.get("duration_seconds") or 0)
        if abs(p-self._position)>=.03 or abs(d-self._duration)>=.03:self._position=max(0,p);self._duration=max(0,d);self.stateChanged.emit()
        ended=bool(st.get("ended"));eid=str(st.get("current_id") or "")
        if ended and eid and eid!=self._last_ended_id and not self._auto_advancing:self._last_ended_id=eid;self._auto_advance(eid)

    def _apply_error(self,msg):
        m=str(msg or "Pont audio indisponible")
        if m!=self._last_error:self._last_error=m;self.lastErrorChanged.emit()
        if self._available:self._available=False;self.availableChanged.emit()

    def _post(self,path,payload=None,timeout=2.5,refresh_after=True):
        def worker():
            try:self._request(path,method="POST",payload=payload or {},timeout=timeout);time.sleep(.12) if refresh_after else None;setattr(self,"_last_full_fetch",0.0) if refresh_after else None;self.refresh() if refresh_after else None
            except Exception as exc:self._errorReceived.emit(str(exc)[:160])
        threading.Thread(target=worker,daemon=True).start()

    @Slot()
    def togglePlay(self):
        if not self._available:self.ensureAvailable();return
        if self._current_id:self._post("/control",{"action":"pause" if self._playing else "resume"});return
        if self._source_items:self.playId(str(self._source_items[0].get("id") or ""))
    @Slot()
    def stop(self): self._post("/control",{"action":"stop"}) if self._available else None
    @Slot(int)
    def setVolume(self,v):self._volume=max(0,min(100,int(v)));self.volumeChanged.emit();self._post("/control",{"action":"volume_percent","value":self._volume},refresh_after=False) if self._available else None
    @Slot(float)
    def seekPercent(self,v):self._post("/control",{"action":"seek_percent","value":max(0.0,min(100.0,float(v)))}) if self._available and self._duration>0 else None
    @Slot(str)
    def playId(self,item_id):
        iid=str(item_id or "")
        if iid:self._last_ended_id="";self._post("/play",{"id":iid})
    @Slot(int)
    def playIndex(self,i):
        if 0<=i<len(self._source_items):self.playId(str(self._source_items[i].get("id") or ""))
    def _current_index(self):return self._source_index(self._current_id)
    @Slot()
    def next(self):
        if not self._source_items:return
        idx=self._current_index();target=random.choice([i for i in range(len(self._source_items)) if i!=idx]) if self._shuffle and len(self._source_items)>1 else(0 if idx<0 else(idx+1)%len(self._source_items));self.playIndex(target)
    @Slot()
    def previous(self):
        if not self._source_items:return
        idx=self._current_index();self.playIndex(len(self._source_items)-1 if idx<=0 else idx-1)
    def _auto_advance(self,eid):
        if not self._source_items:return
        self._auto_advancing=True
        try:
            idx=self._source_index(eid)
            if self._repeat_mode=="one" and idx>=0:self.playIndex(idx);return
            if self._shuffle and len(self._source_items)>1:self.playIndex(random.choice([i for i in range(len(self._source_items)) if i!=idx]));return
            if idx+1<len(self._source_items):self.playIndex(idx+1);return
            if self._repeat_mode=="all":self.playIndex(0)
        finally:QTimer.singleShot(350,lambda:setattr(self,"_auto_advancing",False))
    @Slot()
    def toggleShuffle(self):self._shuffle=not self._shuffle;self._save_modes();self.modesChanged.emit()
    @Slot()
    def cycleRepeat(self):self._repeat_mode={"off":"all","all":"one","one":"off"}.get(self._repeat_mode,"off");self._save_modes();self.modesChanged.emit()
    @Slot(str)
    def playNext(self,item_id):
        iid=str(item_id or "");ti=self._source_index(iid);ci=self._current_index()
        if not iid or iid==self._current_id or ti<0:return
        if ci<0:ci=0
        rows=list(self._source_items);item=rows.pop(ti);ci-=1 if ti<ci else 0;rows.insert(min(len(rows),ci+1),item);self._source_items=rows;self._refresh_models();self._post("/playlist/reorder",{"ids":[str(x.get("id") or "") for x in rows]})
    @Slot(str,int)
    def moveItem(self,item_id,delta):
        i=self._source_index(item_id);j=i+int(delta)
        if i<0 or j<0 or j>=len(self._source_items):return
        rows=list(self._source_items);rows[i],rows[j]=rows[j],rows[i];self._source_items=rows;self._refresh_models();self._post("/playlist/reorder",{"ids":[str(x.get("id") or "") for x in rows]})
    @Slot(str)
    def removeItem(self,item_id):self._post("/playlist/remove",{"id":str(item_id or "")})
    @Slot()
    def clearPlaylist(self):self._post("/playlist/clear",{})
    @Slot()
    def pickTrack(self):self._post("/pick",{"kind":"track"},timeout=120.0)
    @Slot()
    def pickFolder(self):self._post("/pick",{"kind":"folder"},timeout=120.0)
    @Slot()
    def importM3U(self):self._post("/playlist/import-m3u8",{},timeout=120.0)
    @Slot()
    def exportM3U(self):self._post("/playlist/export-m3u8",{},timeout=120.0,refresh_after=False)
    @Slot()
    def refreshMetadata(self):self._post("/metadata/refresh",{},timeout=60.0)
    @Slot(str)
    def saveCollection(self,name):
        n=str(name or "").strip()
        if n:self._post("/collections/save",{"name":n})
    @Slot(str)
    def loadCollection(self,cid):self._post("/collections/load",{"id":str(cid or "")})
    @Slot(str,str)
    def renameCollection(self,cid,name):
        n=str(name or "").strip()
        if n:self._post("/collections/rename",{"id":str(cid or ""),"name":n})
    @Slot(str)
    def deleteCollection(self,cid):self._post("/collections/delete",{"id":str(cid or "")})
    @Slot(str,bool)
    def setFavorite(self,item_id,enabled):
        iid=str(item_id or "")
        if not iid:return
        self._favorites.add(iid) if enabled else self._favorites.discard(iid);self._refresh_models();self.libraryChanged.emit();self._post("/library/favorite",{"id":iid,"enabled":bool(enabled)})
    @Slot()
    def clearHistory(self):self._post("/library/clear-history",{})
    @Slot(str,str,bool,bool)
    def setLibraryView(self,q,sort,fav,dup):self._library_query=str(q or "");self._library_sort=str(sort or "playlist");self._library_favorites_only=bool(fav);self._library_duplicates_only=bool(dup);self._apply_library_view()
    @Slot()
    def resumePlayback(self):
        rid=str(self._resume.get("item_id") or "");pos=float(self._resume.get("position_seconds") or 0);dur=float(self._resume.get("duration_seconds") or 0)
        if not rid or dur<=0:return
        def worker():
            try:self._request("/play",method="POST",payload={"id":rid},timeout=2.5);time.sleep(.22);self._request("/control",method="POST",payload={"action":"seek_percent","value":max(0.0,min(100.0,pos*100.0/dur))},timeout=1.5);self.refreshAll()
            except Exception as exc:self._errorReceived.emit(str(exc)[:160])
        threading.Thread(target=worker,daemon=True).start()
    @Slot()
    def clearResume(self):self._post("/resume/clear",{"id":str(self._resume.get("item_id") or "")})
    @Slot()
    def shutdown(self):
        if not self._available:return
        threading.Thread(target=lambda:self._shutdown_worker(),daemon=True).start()
    def _shutdown_worker(self):
        try:self._request("/lifecycle/close",method="POST",payload={},timeout=.7)
        except Exception:pass


class AuraBridge(QObject):
    cpuChanged=Signal()
    memoryChanged=Signal()
    systemCpuChanged=Signal()
    fpsChanged=Signal()
    themeChanged=Signal()
    stateChanged=Signal()
    workspaceChanged=Signal()
    navigationContextChanged=Signal()
    clockChanged=Signal()
    dockExpandedChanged=Signal()

    def __init__(self,backend):
        super().__init__()
        self._cpu=0.0; self._memory=0.0; self._system_cpu=0.0; self._fps=0
        self._theme="dark"; self._state="IDLE"; self._workspace="home"; self._clock=""; self._navigation_context={}
        self._dock_expanded=False
        self._backend=backend.upper() if backend!="auto" else "AUTO · QT RHI"
        self._proc=psutil.Process() if psutil else None
        self._cpu_count=max(1,psutil.cpu_count(logical=True) or 1) if psutil else 1
        if self._proc:
            self._proc.cpu_percent(None); psutil.cpu_percent(None)
        self._timer=QTimer(self); self._timer.setInterval(1000); self._timer.timeout.connect(self._tick); self._timer.start()
        self._tick()

    @Property(float,notify=cpuChanged)
    def cpuPercent(self): return self._cpu
    @Property(float,notify=memoryChanged)
    def memoryMb(self): return self._memory
    @Property(float,notify=systemCpuChanged)
    def systemCpu(self): return self._system_cpu
    @Property(int,notify=fpsChanged)
    def fps(self): return self._fps
    @Property(str,notify=themeChanged)
    def theme(self): return self._theme
    @Property(str,notify=stateChanged)
    def state(self): return self._state
    @Property(str,notify=workspaceChanged)
    def workspace(self): return self._workspace
    @Property(object,notify=navigationContextChanged)
    def navigationContext(self): return dict(self._navigation_context)
    @Property(str,notify=clockChanged)
    def clockText(self): return self._clock
    @Property(bool,notify=dockExpandedChanged)
    def dockExpanded(self): return self._dock_expanded
    @Property(str,constant=True)
    def backendLabel(self): return self._backend
    @Property(bool,constant=True)
    def windowedMode(self): return bool(args.windowed)
    @Property(int,constant=True)
    def orbTargetFps(self): return max(15,min(60,int(args.orb_fps)))

    @Slot(int)
    def reportFps(self,v):
        v=max(0,min(999,int(v)))
        if v!=self._fps:self._fps=v;self.fpsChanged.emit()
    @Slot()
    def toggleTheme(self):
        self._theme="light" if self._theme=="dark" else "dark";self.themeChanged.emit()
    @Slot(str)
    def setWorkspace(self,v):
        v=str(v or "home").lower()
        if v!=self._workspace:self._workspace=v;self.workspaceChanged.emit()
    @Slot("QVariantMap")
    def setNavigationContext(self,value):
        self._navigation_context=dict(value or {})
        self.navigationContextChanged.emit()
    @Slot(str)
    def setState(self,v):
        v=str(v or "IDLE").upper()
        if v!=self._state:self._state=v;self.stateChanged.emit()
    @Slot(bool)
    def setDockExpanded(self,v):
        v=bool(v)
        if v!=self._dock_expanded:self._dock_expanded=v;self.dockExpandedChanged.emit()

    def _tick(self):
        clock=datetime.now().strftime("%H:%M  ·  %d/%m/%Y")
        if clock!=self._clock:self._clock=clock;self.clockChanged.emit()
        if not self._proc:return
        try:
            cpu=float(self._proc.cpu_percent(None))/float(self._cpu_count)
            mem=float(self._proc.memory_info().rss)/(1024*1024)
            system=float(psutil.cpu_percent(None))
        except Exception:return
        if abs(cpu-self._cpu)>=.03:self._cpu=cpu;self.cpuChanged.emit()
        if abs(mem-self._memory)>=.05:self._memory=mem;self.memoryChanged.emit()
        if abs(system-self._system_cpu)>=.05:self._system_cpu=system;self.systemCpuChanged.emit()


def main():
    # Native validation keeps PCC-4 metadata visible in the launching console;
    # pcc4_trace remains content-free and never logs secrets or conversation text.
    os.environ.setdefault("AURA_PCC4_DEBUG", "1")
    if args.core_mode == "native" and not args.state_dir:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            local_app_data = str(Path.home() / "AppData" / "Local")
        args.state_dir = str(Path(local_app_data) / "AURA-NATIVE")
    # Qt 6 no longer bundles fonts. Point the platform font loader at the
    # system directory when available so startup never probes PySide6/lib/fonts.
    if os.name == "nt" and not os.environ.get("QT_QPA_FONTDIR"):
        _system_font_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        if _system_font_dir.is_dir():
            os.environ["QT_QPA_FONTDIR"] = str(_system_font_dir)
    app=QApplication(sys.argv)

    # AURA_MUSIC_EXIT_LIFECYCLE_R2_FIX1
    _aura_music_shutdown_state = {"done": False}
    def _aura_shutdown_music_on_app_exit():
        if _aura_music_shutdown_state["done"]:
            return
        _aura_music_shutdown_state["done"] = True
        try:
            import urllib.request as _aura_music_urllib
            _aura_music_req = _aura_music_urllib.Request(
                "http://127.0.0.1:18180/lifecycle/shutdown",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _aura_music_urllib.urlopen(_aura_music_req, timeout=2.0) as _aura_music_resp:
                _aura_music_resp.read()
        except Exception:
            pass
    if args.core_mode == "legacy":
        app.aboutToQuit.connect(_aura_shutdown_music_on_app_exit)

    app.setApplicationName("AURA Native UI POC 6G Chromium Fidelity")
    app.setOrganizationName("VeyrNova")
    qmlRegisterType(NeuralOrbItem,"Aura.Native",1,0,"NeuralOrbItem")

    base=Path(__file__).resolve().parent
    engine=QQmlApplicationEngine()
    bridge=AuraBridge(args.backend)
    if args.core_mode == "native" and os.environ.get("AURA_NATIVE_WORKSPACE"):
        bridge.setWorkspace(os.environ["AURA_NATIVE_WORKSPACE"])
    native_runtime = None
    native_dispatcher = None
    if args.core_mode == "legacy":
        core_bridge=AuraCoreBridge()
        music_bridge=MusicQtBridge()
        weather_bridge=WeatherBridge()
        core_bridge.uiStateRequested.connect(bridge.setState)
        native_models = None
    else:
        project_root = base.parent
        source_root = project_root / "src"
        if str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))
        from aura_native.bootstrap.composition import compose_runtime
        from aura_native.ui.models import EmptyListModel
        from aura_native.ui.qt_bridge import NativeCoreBridge, NativeUnavailableBridge, NativeDiagnosticsBridge
        from aura_native.voice.qt_bridge import NativeVoiceBridge
        from aura_native.ui.music_bridge import NativeMusicBridge
        from aura_native.weather.qt_bridge import NativeWeatherBridge
        from aura_native.ui.qt_dispatcher import QtBusDispatcher
        from aura_native.developer_fabric.qt_bridge import DeveloperFabricBridge, DeveloperProjectsModel, DeveloperJobsModel, DeveloperProvidersModel, DeveloperAgentsModel
        try:
            native_runtime = compose_runtime(project_root=project_root, state_dir=args.state_dir)
            native_runtime.start()
            native_runtime.start_background()
        except (OSError, ValueError) as exc:
            print(f"native runtime configuration failed: {exc}", file=sys.stderr)
            return 2
        native_dispatcher = QtBusDispatcher(native_runtime.bus, app)
        core_bridge = NativeCoreBridge(native_runtime, app)
        developer_fabric_bridge = DeveloperFabricBridge(native_runtime.developer_fabric_service, app)
        developer_projects_model = DeveloperProjectsModel([], app)
        developer_jobs_model = DeveloperJobsModel([], app)
        developer_providers_model = DeveloperProvidersModel([], app)
        developer_agents_model = DeveloperAgentsModel([{"agentId":a.agent_id,"displayName":a.display_name,"installed":a.installed,"available":a.installed,"platformSupported":True,"supportLevel":a.support_level,"protocol":a.protocol,"bridgeMode":a.bridge_mode} for a in native_runtime.developer_fabric_service.agents.agents], app)
        from aura_native.ui.module_composition import NativeModuleComposition
        from aura_native.mail.qt_bridge import NativeMailBridge
        from aura_native.google.day_summary_bridge import GoogleDaySummaryBridge
        from aura_native.maps.qt_bridge import NativeMapsBridge
        from aura_native.search.duckduckgo import DuckDuckGoHtmlBackend
        from aura_native.search.service import SearchService
        from aura_native.search.qt_bridge import NativeSearchBridge
        from aura_native.documents.filesystem import FileSystemRepository
        from aura_native.documents.service import DocumentsService
        from aura_native.documents.qt_bridge import NativeDocumentsBridge
        from aura_native.contacts.repository import ContactsRepository
        from aura_native.contacts.service import ContactsService
        from aura_native.contacts.qt_bridge import NativeContactsBridge
        native_module_composition = NativeModuleComposition.build(native_runtime, app)
        music_bridge = native_module_composition.music_bridge
        weather_bridge = native_module_composition.weather_bridge
        diagnostics_bridge = native_module_composition.diagnostics_bridge
        mail_bridge = NativeMailBridge(native_runtime.mail_service, app, native_runtime.prepared_action_repository)
        google_day_summary_bridge = GoogleDaySummaryBridge(native_runtime.google_day_summary_service, app)
        maps_bridge = NativeMapsBridge(native_runtime.maps_service, app)
        search_bridge = NativeSearchBridge(SearchService(DuckDuckGoHtmlBackend()), app)
        documents_bridge = NativeDocumentsBridge(DocumentsService(FileSystemRepository(native_runtime.paths.data_dir / "documents")), app)
        contacts_bridge = NativeContactsBridge(ContactsService(ContactsRepository(native_runtime.paths.data_dir / "contacts.sqlite")), app)
        voice_bridge = NativeVoiceBridge(parent=app)
        voice_bridge.voiceConversationRequested.connect(core_bridge.sendVoiceMessage, Qt.QueuedConnection)
        # Legacy transcriptReady remains a public signal for observers; the
        # production local-command path uses the correlated signal below.
        # voice_bridge.transcriptReady.connect(core_bridge.dispatchLocalTranscript, Qt.QueuedConnection)
        voice_bridge.localTranscriptReady.connect(core_bridge.dispatchLocalTranscriptWithRequest, Qt.QueuedConnection)
        core_bridge.voiceLocalActionTerminal.connect(voice_bridge.onLocalActionTerminal, Qt.QueuedConnection)
        core_bridge.voiceResponseFinal.connect(voice_bridge.onVoiceResponseFinal, Qt.QueuedConnection)
        # Keep the native productivity models wired to their actual bridges.
        # The remaining surfaces stay explicit empty models until migrated.
        native_models = [music_bridge.model, music_bridge.libraryModel, EmptyListModel(app),
                         core_bridge.tasks_model, core_bridge.reminders_model, core_bridge.notes_model,
                         EmptyListModel(app), EmptyListModel(app), EmptyListModel(app),
                         EmptyListModel(app)]
    engine.rootContext().setContextProperty("bridge",bridge)
    engine.rootContext().setContextProperty("coreBridge",core_bridge)
    engine.rootContext().setContextProperty("musicBridge",music_bridge)
    engine.rootContext().setContextProperty("weatherBridge",weather_bridge)
    engine.rootContext().setContextProperty("diagnosticsBridge", diagnostics_bridge if args.core_mode == "native" else core_bridge)
    engine.rootContext().setContextProperty("mailBridge", mail_bridge if args.core_mode == "native" else None)
    engine.rootContext().setContextProperty("googleDaySummaryBridge", google_day_summary_bridge if args.core_mode == "native" else None)
    engine.rootContext().setContextProperty("mapsBridge", maps_bridge if args.core_mode == "native" else None)
    engine.rootContext().setContextProperty("searchBridge", search_bridge if args.core_mode == "native" else None)
    engine.rootContext().setContextProperty("documentsBridge", documents_bridge if args.core_mode == "native" else None)
    engine.rootContext().setContextProperty("contactsBridge", contacts_bridge if args.core_mode == "native" else None)
    engine.rootContext().setContextProperty("voiceBridge", voice_bridge if args.core_mode == "native" else None)
    engine.rootContext().setContextProperty("runtimeMode",args.core_mode)
    if args.core_mode == "native":
        engine.rootContext().setContextProperty("developerFabricBridge", developer_fabric_bridge)
        engine.rootContext().setContextProperty("developerProjectsModel", developer_projects_model)
        engine.rootContext().setContextProperty("developerJobsModel", developer_jobs_model)
        engine.rootContext().setContextProperty("developerProvidersModel", developer_providers_model)
        engine.rootContext().setContextProperty("developerAgentsModel", developer_agents_model)
    models = (music_bridge.model, music_bridge.libraryModel, core_bridge.messages, core_bridge.tasks_model, core_bridge.reminders_model, core_bridge.notes_model, core_bridge.google_tasks_model, core_bridge.google_calendar_model, core_bridge.memories_model, core_bridge.memory_context_model, core_bridge.agenda_calendar_model) if native_models is None else tuple(native_models + [native_models[-1]])
    for name, model in zip(("musicPlaylistModel","musicLibraryModel","conversationModel","tasksModel","remindersModel","notesModel","googleTasksModel","googleCalendarModel","memoriesModel","memoryContextModel","agendaCalendarModel"), models):
        engine.rootContext().setContextProperty(name,model)
    engine.rootContext().setContextProperty("auraAssetBase",QUrl.fromLocalFile(str(base/"assets")+os.sep).toString())
    if args.core_mode == "legacy":
        app.aboutToQuit.connect(music_bridge.shutdown)
    engine.load(QUrl.fromLocalFile(str(base/"qml"/"Main.qml")))
    if not engine.rootObjects():
        print("QML failed to load",file=sys.stderr)
        return 2
    if (args.core_mode == "native" and args.voice_transcript_probe is not None
            and os.environ.get("AURA_PTT_DIAGNOSTICS") == "1"):
        # Test-only entry: keep the normal QML/bridge/router path and never
        # open audio.  The explicit diagnostics env guard prevents production
        # users from invoking this path accidentally.
        QTimer.singleShot(1200, lambda: voice_bridge.injectTranscriptForDiagnostics(args.voice_transcript_probe))
    if args.core_mode == "native" and native_runtime is not None:
        native_runtime.reminder_window_state.set_window(engine.rootObjects()[0])
        from aura_native.reminders.tray_service import AuraTrayService
        shutdown_state = {"done": False}
        def shutdown_native(request_quit=True):
            if shutdown_state["done"]:
                return
            shutdown_state["done"] = True
            native_runtime.stop_background()
            tray_service.close()
            core_bridge.close()
            voice_bridge.close()
            music_bridge.shutdown()
            native_dispatcher.close()
            native_runtime.stop()
            if request_quit:
                app.quit()
        tray_service = AuraTrayService(engine.rootObjects()[0], app, base / "assets" / "AURA_LOGO_SYMBOL_ARCTIC.svg", shutdown=shutdown_native)
        root_window = engine.rootObjects()[0]
        if tray_service.tray:
            app.setQuitOnLastWindowClosed(False)
            def close_to_tray(event):
                event.accepted = False
                root_window.hide()
                print("AURA_WINDOW_HIDDEN_TO_TRAY", flush=True)
            root_window.closing.connect(close_to_tray)
        else:
            app.setQuitOnLastWindowClosed(True)
        coordinator = getattr(native_runtime, "reminder_notification_coordinator", None)
        if coordinator and coordinator.windows and tray_service.tray:
            coordinator.windows.set_tray(tray_service.tray)
        app.aboutToQuit.connect(lambda: shutdown_native(False))
    if args.qml_self_check:
        if args.core_mode == "native":
            core_bridge.close()
            native_dispatcher.close()
        return 0
    return app.exec()

if __name__=="__main__":
    raise SystemExit(main())
