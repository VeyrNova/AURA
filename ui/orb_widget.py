"""AURA holographic core — v0.7.0.12 Holographic UI Fidelity.

QPainter fallback implementation. v0.7.0.15.6.3 can place a procedural OpenGL surface above it when available. The target UI is not a
flat set of rings: it is a living cyan/violet plasma torus wrapped around a dark
central intelligence core, crossed by a fine waveform and suspended above a
holographic emitter.  The widget stays DPI-independent and state-reactive.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QBrush,
    QConicalGradient,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QLabel, QWidget

from ui.aura_logo import master_symbol_path
from ui.aura_mood import MOOD_STRENGTH, mood_palette, normalize_mood


STATE_COLORS = {
    "STARTUP": QColor(0, 220, 255),
    "PRELOAD": QColor(0, 226, 255),
    "IDLE": QColor(0, 190, 255),
    "THINKING": QColor(128, 91, 255),
    "PROCESSING": QColor(102, 98, 255),
    "SPEAKING": QColor(126, 82, 255),
    "LISTENING": QColor(0, 224, 255),
    "EXECUTING": QColor(43, 210, 255),
    "ERROR": QColor(255, 74, 104),
}
STATE_ENERGY = {"STARTUP": 1.0, "PRELOAD": 1.08, "IDLE": .46, "THINKING": .76, "PROCESSING": .84, "SPEAKING": 1.0, "LISTENING": .91, "EXECUTING": .95, "ERROR": .62}
STATE_SPEED = {"STARTUP": 1.90, "PRELOAD": 1.72, "IDLE": .48, "THINKING": 1.05, "PROCESSING": 1.25, "SPEAKING": 1.68, "LISTENING": 1.38, "EXECUTING": 1.54, "ERROR": .74}



def _qcolor_from_unit(rgb) -> QColor:
    return QColor(*(max(0, min(255, int(round(float(v) * 255)))) for v in rgb))


def _blend_qcolor(a: QColor, b: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, float(amount)))
    return QColor(
        int(round(a.red() + (b.red() - a.red()) * amount)),
        int(round(a.green() + (b.green() - a.green()) * amount)),
        int(round(a.blue() + (b.blue() - a.blue()) * amount)),
    )


def _state_mood_colors(state: str, mood: str):
    state = state if state in STATE_COLORS else "IDLE"
    mood = "alert" if state == "ERROR" else normalize_mood(mood)
    base_primary = QColor(STATE_COLORS[state])
    base_secondary = QColor(172, 74, 255) if state != "ERROR" else QColor(255, 74, 120)
    mp, ms = mood_palette(mood)
    strength = 0.88 if state == "ERROR" else MOOD_STRENGTH.get(mood, 0.0)
    return (
        _blend_qcolor(base_primary, _qcolor_from_unit(mp), strength),
        _blend_qcolor(base_secondary, _qcolor_from_unit(ms), strength),
    )


_ORB_FONT_CANDIDATES = (
    "Bahnschrift SemiCondensed",
    "Bahnschrift Light",
    "Bahnschrift",
    "Segoe UI Variable",
    "Segoe UI",
    "Rajdhani",
    "Exo 2",
    "Orbitron",
)

def resolve_orb_font_family() -> str:
    """Resolve a technical HUD font without making AURA depend on font files."""
    try:
        available = {name.casefold(): name for name in QFontDatabase.families()}
        for candidate in _ORB_FONT_CANDIDATES:
            hit = available.get(candidate.casefold())
            if hit:
                return hit
    except Exception:
        pass
    return "Segoe UI"


class _AuraMarkWidget(QWidget):
    """Single-source vector AURA mark shared by GL and QPainter backends.

    Patch 03 removes the last hand-drawn central A. The geometry is loaded from
    ``ui/assets/branding/aura_symbol_master.svg`` and rendered as a vector path
    above either backend. During startup the exact same path is revealed only
    after the neural sphere has formed (60–72%).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "IDLE"
        self._mood = "neutral"
        self._color = QColor(99, 243, 255)
        self._phase = 0.0
        self._construction_progress = 1.0
        self._target_progress = 1.0
        self._visual_progress = 1.0
        self._master_path = master_symbol_path()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(45)

    def _tick(self):
        self._phase = (self._phase + 0.018) % 1.0
        # Patch 15: visual boot progress is frame-driven, not wall-clock driven.
        # A long XTTS/UI stall therefore cannot skip the hollow or white logo
        # states. At 45 ms/tick, a full 0->1 catch-up takes ~3.7 s minimum.
        if self._visual_progress < self._target_progress:
            self._visual_progress = min(self._target_progress, self._visual_progress + 0.012)
        elif self._visual_progress > self._target_progress:
            self._visual_progress = self._target_progress
        self.update()

    def _refresh_color(self) -> None:
        self._color = _state_mood_colors(self._state, self._mood)[0]

    def set_state(self, state: str) -> None:
        self._state = state if state in STATE_COLORS else "IDLE"
        self._refresh_color()
        self.update()

    def set_mood(self, mood: str) -> None:
        self._mood = normalize_mood(mood)
        self._refresh_color()
        self.update()

    def set_construction_progress(self, progress: float) -> None:
        target = max(0.0, min(1.0, float(progress)))
        self._construction_progress = target
        # Boot/restart resets must be immediate; forward jumps are deliberately
        # smoothed so every visual logo state is actually displayed.
        if target <= 0.02 or target + 0.10 < self._visual_progress:
            self._visual_progress = target
        self._target_progress = target
        self.update()

    @staticmethod
    def _stage(value: float, start: float, end: float) -> float:
        if value <= start:
            return 0.0
        if value >= end:
            return 1.0
        x = (value - start) / max(0.0001, end - start)
        return x * x * (3.0 - 2.0 * x)

    def paintEvent(self, event):
        del event
        progress = max(0.0, min(1.0, self._visual_progress))

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        w, h = float(self.width()), float(self.height())
        if w <= 2 or h <= 2:
            return

        bounds = self._master_path.boundingRect()
        target_w = w * 0.75
        target_h = h * 0.84
        scale = min(target_w / max(1.0, bounds.width()), target_h / max(1.0, bounds.height()))
        draw_w = bounds.width() * scale
        draw_h = bounds.height() * scale
        tx = (w - draw_w) * 0.5 - bounds.left() * scale
        ty = (h - draw_h) * 0.50 - bounds.top() * scale

        p.save()
        p.translate(tx, ty)
        p.scale(scale, scale)

        pulse = 0.90 + 0.10 * math.sin(self._phase * math.tau)
        # Locked boot sequence:
        # 0-25%   = hollow A only
        # 25-60%  = progressive white fill
        # 60-84%  = stable white A
        # 84-100% = white -> cyan/blue/violet gradient
        white_fill = self._stage(progress, 0.25, 0.60)
        color_phase = self._stage(progress, 0.84, 1.00)
        primary, secondary = _state_mood_colors(self._state, self._mood)

        grad = QLinearGradient(bounds.left(), bounds.top(), bounds.right(), bounds.bottom())
        grad.setColorAt(0.00, QColor(246, 253, 255, 255))
        grad.setColorAt(0.22, QColor(125, 239, 255, 255))
        grad.setColorAt(0.68, QColor(125, 146, 255, 255))
        grad.setColorAt(1.00, QColor(212, 102, 255, 255))

        # Stage 1 — hollow/empty A is present from the actual 0% frame.
        outline_glow = QColor(128, 88, 255, int((42 + 38*(1.0-color_phase)) * pulse))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(outline_glow, 18.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(self._master_path)
        p.setPen(QPen(QColor(244, 251, 255, 212), 4.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(self._master_path)

        # Stage 2 — true morph from hollow outline to a solid white A.
        # The whole silhouette fills uniformly, avoiding the horizontal reveal
        # band seen in Patch 15. The outline stays visible during the morph.
        if white_fill > 0.001:
            white_alpha = int(248 * white_fill * (1.0 - 0.94*color_phase))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(244, 251, 255, white_alpha))
            p.drawPath(self._master_path)

        # Stage 3 — only near the end does the official AURA gradient replace
        # the white fill. The geometry never changes between states.
        if color_phase > 0.001:
            outer_glow = QColor(138, 88, 255, int((40 + 88*color_phase) * pulse))
            cyan_glow = QColor(primary)
            cyan_glow.setAlpha(int((42 + 90*color_phase) * pulse))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(outer_glow, 24.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(self._master_path)
            p.setPen(QPen(cyan_glow, 12.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(self._master_path)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.setOpacity(color_phase)
            p.drawPath(self._master_path)
            p.setOpacity(1.0)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(244, 251, 255, int(180 - 60*color_phase)), 1.8,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(self._master_path)
        p.restore()



class PainterOrbWidget(QWidget):
    """Organic, state-reactive holographic sphere used by boot and final UI."""

    def __init__(self, parent=None, *, show_brand: bool = True):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        # QOpenGLWidget inside a translucent top-level window can punch an alpha
        # hole through the Windows compositor.  The visual core is deliberately
        # opaque; only the shader content creates the holographic illusion.
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color:#010711;")
        self.state = "IDLE"
        self._preload_progress = 1.0
        self.show_brand = bool(show_brand)
        self._phase = 0.0
        self._target_energy = STATE_ENERGY["IDLE"]
        self._energy = self._target_energy
        self._mood = "neutral"
        self._primary, self._secondary = _state_mood_colors("IDLE", self._mood)
        self._target_primary = QColor(self._primary)
        self._target_secondary = QColor(self._secondary)
        self._voice = 0.0
        self._target_voice = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(33)

    def _refresh_palette(self):
        self._target_primary, self._target_secondary = _state_mood_colors(self.state, self._mood)

    def set_mood(self, mood: str) -> None:
        self._mood = normalize_mood(mood)
        self._refresh_palette()
        self.update()

    def set_state(self, state: str):
        self.state = state if state in STATE_COLORS else "IDLE"
        self._target_energy = STATE_ENERGY[self.state]
        # Patch 22.4: SPEAKING only enables the lane; actual PCM drives level.
        # Never pin the fallback waveform to a constant full-scale amplitude.
        if self.state != "SPEAKING":
            self._target_voice = 0.0
        self._refresh_palette()
        self.update()

    def set_voice_amplitude(self, value: float) -> None:
        self._target_voice = max(0.0, min(1.0, float(value))) if self.state == "SPEAKING" else 0.0

    def set_brand_visible(self, visible: bool) -> None:
        self.show_brand = bool(visible)
        self.update()

    def set_preload_progress(self, percent: int) -> None:
        self._preload_progress = max(0.0, min(1.0, float(percent) / 100.0))
        self.update()

    def _on_tick(self):
        self._phase = (self._phase + 0.033 * STATE_SPEED[self.state]) % (math.tau * 1000)
        self._energy += (self._target_energy - self._energy) * .08
        self._voice += (self._target_voice - self._voice) * .18
        self._primary = _blend_qcolor(self._primary, self._target_primary, .075)
        self._secondary = _blend_qcolor(self._secondary, self._target_secondary, .075)
        self.update()

    @staticmethod
    def _alpha(color: QColor, alpha: int) -> QColor:
        c = QColor(color)
        c.setAlpha(max(0, min(255, int(alpha))))
        return c

    # ---------------------------------------------------------- neural core v1
    def _neural_nodes(self, cx: float, cy: float, radius: float, density: float):
        """Deterministic pseudo-3D sphere nodes, stable across frames.

        Longitude drifts slowly while latitude remains mostly stable. Projected
        depth controls point size/alpha and gives the reference orb its living
        spherical volume without mechanical concentric rings.
        """
        total = 520
        active = max(0, min(total, int(round(total * max(0.0, min(1.0, density))))))
        nodes = []
        for idx in range(active):
            u = (idx * 0.61803398875 + 0.137) % 1.0
            vv = (idx * 0.41421356237 + 0.271) % 1.0
            z = vv * 2.0 - 1.0
            lat = math.asin(max(-.999, min(.999, z)))
            lon = math.tau * u + self._phase * (0.028 + (idx % 7) * 0.0017)
            cos_lat = math.cos(lat)
            depth = cos_lat * math.sin(lon)
            x = cos_lat * math.cos(lon)
            y = math.sin(lat)
            # Tiny organic drift; no orbiting HUD mechanics.
            drift = 0.018 * math.sin(self._phase * .31 + idx * 1.73)
            x += drift * math.cos(idx * 2.17)
            y += drift * math.sin(idx * 1.91)
            nodes.append((
                QPointF(cx + x * radius, cy + y * radius * .96),
                depth,
                idx,
            ))
        return nodes

    def _draw_neural_field(self, p: QPainter, cx: float, cy: float, radius: float,
                           primary: QColor, violet: QColor, density: float,
                           links: float, core: float, stable: float) -> None:
        nodes = self._neural_nodes(cx, cy, radius, density)
        if not nodes:
            return

        # Soft volumetric sphere appears after the network itself starts forming.
        if core > 0.001:
            halo = QRadialGradient(cx, cy, radius * 1.42)
            halo.setColorAt(0.0, self._alpha(QColor(104, 82, 255), int(23 * core)))
            halo.setColorAt(.42, self._alpha(primary, int((19 + 17*self._energy) * core)))
            halo.setColorAt(.74, self._alpha(violet, int((15 + 29*self._energy) * core)))
            halo.setColorAt(1.0, QColor(0,0,0,0))
            p.setPen(Qt.NoPen); p.setBrush(halo)
            p.drawEllipse(QPointF(cx, cy), radius*1.42, radius*1.42)

        # Patch 15 strict neural containment. Halo may breathe outside, but every
        # node, filament, branch and impulse is clipped inside the orb membrane.
        p.save()
        neural_clip = QPainterPath()
        neural_clip.addEllipse(QPointF(cx, cy), radius*.975, radius*.975)
        p.setClipPath(neural_clip, Qt.IntersectClip)

        # PATCH 19 — hub-anchored connected synaptic web. Six explicit hubs connect
        # nearby neural anchors; lower-intensity support fibres and short dendrites attach to them. Distances
        # are capped so the result reads as a cortex, never as orbital chords.
        if links > 0.001 and len(nodes) > 8:
            branch_budget = max(14, int(18 + 18*links))
            state_activity = {
                "SPEAKING": 1.0, "THINKING": .54, "PROCESSING": .62,
                "EXECUTING": .48, "LISTENING": .20,
            }.get(self.state, .06)

            # PATCH 19 — six explicit synaptic hubs. These define the visual
            # hierarchy before the low-intensity node-to-node connective tissue.
            hub_pts = [
                QPointF(cx-radius*.45, cy-radius*.30),
                QPointF(cx-radius*.10, cy-radius*.43),
                QPointF(cx+radius*.35, cy-radius*.24),
                QPointF(cx+radius*.46, cy+radius*.19),
                QPointF(cx+radius*.06, cy+radius*.43),
                QPointF(cx-radius*.42, cy+radius*.22),
            ]
            routes = ((0,1,1.0),(1,2,-1.0),(2,3,1.0),(3,4,1.0),(4,5,-1.0),(5,0,-1.0),(1,4,1.0))
            hub_activity = max(state_activity, self._voice) * links
            for route_idx, (ha, hb, sign) in enumerate(routes):
                a = hub_pts[ha]; b = hub_pts[hb]
                dx, dy = b.x()-a.x(), b.y()-a.y()
                dist = max(1.0, math.hypot(dx,dy))
                nx, ny = -dy/dist, dx/dist
                bend = dist*(.18 + .035*math.sin(route_idx*.77))*sign
                c1 = QPointF(a.x()+dx*.34+nx*bend, a.y()+dy*.34+ny*bend)
                c2 = QPointF(a.x()+dx*.70-nx*bend*.55, a.y()+dy*.70-ny*bend*.55)
                path = QPainterPath(a); path.cubicTo(c1,c2,b)
                c = QColor(primary if route_idx in (0,2,4,6) else violet)
                c.setAlpha(int(92 + 95*links + 28*stable))
                width = max(.9, radius*(.0030 + .00045*(route_idx%2)))
                halo = QColor(c); halo.setAlpha(max(18,c.alpha()//4))
                p.setBrush(Qt.NoBrush); p.setPen(QPen(halo,width*3.4,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)); p.drawPath(path)
                p.setPen(QPen(c,width,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)); p.drawPath(path)
                if hub_activity > .06:
                    t0 = (self._phase*(.18+.018*(route_idx%3)) + route_idx*.137) % 1.0
                    om = 1.0-t0
                    px = om**3*a.x()+3*om**2*t0*c1.x()+3*om*t0**2*c2.x()+t0**3*b.x()
                    py = om**3*a.y()+3*om**2*t0*c1.y()+3*om*t0**2*c2.y()+t0**3*b.y()
                    pulse = QPointF(px,py)
                    ph = QColor(c); ph.setAlpha(int(min(130,35+90*hub_activity)))
                    pc = QColor(244,252,255); pc.setAlpha(int(min(245,95+145*hub_activity)))
                    p.setPen(Qt.NoPen); p.setBrush(ph); p.drawEllipse(pulse,radius*.017*hub_activity,radius*.017*hub_activity)
                    p.setBrush(pc); p.drawEllipse(pulse,max(.8,radius*.0042),max(.8,radius*.0042))

            # Patch 20: hubs become discreet branch centres instead of large stars.
            # More secondary arms carry the visual density; white is reserved for
            # active impulses and the smallest core point.
            for hi, hub in enumerate(hub_pts):
                act = (.50+.50*math.sin(self._phase*(3.6+1.8*state_activity)+hi*.92))
                act = max(0.0, act)**4 * hub_activity
                hc = QColor(primary if hi%2==0 else violet)
                halo = QColor(hc); halo.setAlpha(int(24+38*links+58*act))
                corec = QColor(242,252,255); corec.setAlpha(int(min(235,96+58*links+92*act)))
                p.setPen(Qt.NoPen); p.setBrush(halo); p.drawEllipse(hub,radius*(.013+.008*act),radius*(.013+.008*act))
                p.setBrush(corec); p.drawEllipse(hub,max(.7,radius*.0042),max(.7,radius*.0042))
                for arm in range(6):
                    angle = hi*.93 + arm*1.035 + .22*math.sin(hi+arm)
                    ln = radius*(.085 + .030*((hi+arm)%4))
                    end = QPointF(hub.x()+math.cos(angle)*ln,hub.y()+math.sin(angle)*ln)
                    ctrl = QPointF(hub.x()+math.cos(angle+.23)*ln*.55,hub.y()+math.sin(angle+.23)*ln*.55)
                    twig = QPainterPath(hub); twig.quadTo(ctrl,end)
                    tc = QColor(hc); tc.setAlpha(int(24+52*links+86*act))
                    p.setBrush(Qt.NoBrush); p.setPen(QPen(tc,max(.28,radius*.00105),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)); p.drawPath(twig)
                    # tertiary twig from the secondary arm
                    if arm % 2 == 0:
                        ta = angle + (.72 if (arm//2)%2==0 else -.68)
                        tlen = ln*.36
                        base = QPointF(hub.x()+math.cos(angle)*ln*.64, hub.y()+math.sin(angle)*ln*.64)
                        tend = QPointF(base.x()+math.cos(ta)*tlen, base.y()+math.sin(ta)*tlen)
                        tctrl = QPointF(base.x()+math.cos(ta+.18)*tlen*.52, base.y()+math.sin(ta+.18)*tlen*.52)
                        fine = QPainterPath(base); fine.quadTo(tctrl,tend)
                        fc = QColor(tc); fc.setAlpha(max(12,int(tc.alpha()*.62)))
                        p.setPen(QPen(fc,max(.22,radius*.00072),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)); p.drawPath(fine)
            max_link = radius * .27
            min_link = radius * .040
            used_pairs = set()
            for i in range(branch_budget):
                ai = (i * 7 + 3) % len(nodes)
                anchor, depth, idx = nodes[ai]
                front = .46 + .54*((depth+1.0)*.5)

                # Select up to two nearby targets. This creates a connected graph
                # without the long cross-sphere lines of the old implementation.
                candidates = []
                for bj, (point, bdepth, bidx) in enumerate(nodes):
                    if bj == ai:
                        continue
                    dx = point.x() - anchor.x()
                    dy = point.y() - anchor.y()
                    dist = math.hypot(dx, dy)
                    if min_link <= dist <= max_link:
                        candidates.append((dist, bj, point, bdepth, bidx))
                candidates.sort(key=lambda item: item[0])
                targets = candidates[:3]
                for edge_no, (dist, bj, end_pt, bdepth, bidx) in enumerate(targets):
                    pair = (min(ai,bj), max(ai,bj))
                    if pair in used_pairs:
                        continue
                    used_pairs.add(pair)
                    dx = end_pt.x() - anchor.x()
                    dy = end_pt.y() - anchor.y()
                    inv = 1.0 / max(dist, 1e-5)
                    nx, ny = -dy*inv, dx*inv
                    sign = -1.0 if ((idx + bidx + edge_no) % 2) else 1.0
                    bend = dist * (.12 + .07*math.sin(idx*.47+bidx*.23)) * sign
                    ctrl1 = QPointF(anchor.x()+dx*.32 + nx*bend, anchor.y()+dy*.32 + ny*bend)
                    ctrl2 = QPointF(anchor.x()+dx*.70 - nx*bend*.55, anchor.y()+dy*.70 - ny*bend*.55)
                    path = QPainterPath(anchor)
                    path.cubicTo(ctrl1, ctrl2, end_pt)
                    edge_front = .5 + .5*(((depth+bdepth)*.5 + 1.0)*.5)
                    # A few dominant cyan/violet highways define the large-scale
                    # hierarchy; remaining edges become dim connective tissue.
                    master_edge = False  # Patch 19: explicit hubs/routes carry the hierarchy
                    if master_edge:
                        c = QColor(primary if (i % 3) else violet)
                        c.setAlpha(int((58 + 94*links + 34*stable) * (.58 + .42*edge_front)))
                        width = max(.72, radius*(.00235 + .00105*edge_front))
                        halo_c = QColor(c); halo_c.setAlpha(max(12, c.alpha()//4))
                        p.setPen(QPen(halo_c, width*3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                        p.setBrush(Qt.NoBrush); p.drawPath(path)
                    else:
                        c = QColor(primary if ((idx+bidx)%4) else violet)
                        c.setAlpha(int((11 + 26*links + 15*stable) * (.42 + .42*edge_front)))
                        width = max(.24, radius*(.00054 + .00030*edge_front))
                    p.setPen(QPen(c, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)

                    # Secondary branch attached to the master axon.
                    sprout_t = .56 + .08*((idx+bidx)%3)
                    omt = 1.0 - sprout_t
                    sx = (omt**3)*anchor.x() + 3*(omt**2)*sprout_t*ctrl1.x() + 3*omt*(sprout_t**2)*ctrl2.x() + (sprout_t**3)*end_pt.x()
                    sy = (omt**3)*anchor.y() + 3*(omt**2)*sprout_t*ctrl1.y() + 3*omt*(sprout_t**2)*ctrl2.y() + (sprout_t**3)*end_pt.y()
                    sprout = QPointF(sx, sy)
                    tangent_angle = math.atan2(dy, dx) + sign*(.72 + .14*math.sin(idx+bidx))
                    twig_len = min(radius*.10, dist*.34)
                    twig_end = QPointF(sprout.x()+math.cos(tangent_angle)*twig_len,
                                       sprout.y()+math.sin(tangent_angle)*twig_len)
                    twig_ctrl = QPointF(sprout.x()+math.cos(tangent_angle)*twig_len*.50 - math.sin(tangent_angle)*twig_len*.12*sign,
                                        sprout.y()+math.sin(tangent_angle)*twig_len*.50 + math.cos(tangent_angle)*twig_len*.12*sign)
                    twig = QPainterPath(sprout)
                    twig.quadTo(twig_ctrl, twig_end)
                    tc = QColor(c); tc.setAlpha(max(7, int(c.alpha()*(.76 if master_edge else .54))))
                    p.setPen(QPen(tc, max(.28,width*(.54 if master_edge else .60)), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    p.drawPath(twig)
                    if not master_edge and ((idx+bidx+edge_no) % 3 == 0):
                        angle2 = tangent_angle - sign*(.90 + .10*math.sin(idx*.33+bidx))
                        twig2_len = twig_len*.62
                        twig2_end = QPointF(sprout.x()+math.cos(angle2)*twig2_len,
                                            sprout.y()+math.sin(angle2)*twig2_len)
                        twig2_ctrl = QPointF(sprout.x()+math.cos(angle2+.15*sign)*twig2_len*.52,
                                             sprout.y()+math.sin(angle2+.15*sign)*twig2_len*.52)
                        twig2 = QPainterPath(sprout); twig2.quadTo(twig2_ctrl,twig2_end)
                        tc2 = QColor(tc); tc2.setAlpha(max(6,int(tc.alpha()*.62)))
                        p.setPen(QPen(tc2,max(.22,width*.46),Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin)); p.drawPath(twig2)
                    if master_edge:
                        # Secondary bifurcation attached to the same master axon.
                        angle2 = tangent_angle - sign*1.18
                        twig2_len = twig_len*.78
                        twig2_end = QPointF(sprout.x()+math.cos(angle2)*twig2_len,
                                            sprout.y()+math.sin(angle2)*twig2_len)
                        twig2_ctrl = QPointF(sprout.x()+math.cos(angle2)*twig2_len*.52,
                                             sprout.y()+math.sin(angle2)*twig2_len*.52)
                        twig2 = QPainterPath(sprout); twig2.quadTo(twig2_ctrl, twig2_end)
                        p.setPen(QPen(tc, max(.26,width*.44), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                        p.drawPath(twig2)
                        # Bright synaptic junction at the bifurcation.
                        jc = QColor(240,252,255); jc.setAlpha(min(240, 105 + int(90*links)))
                        jh = QColor(c); jh.setAlpha(min(105, 35 + int(45*links)))
                        p.setPen(Qt.NoPen); p.setBrush(jh)
                        p.drawEllipse(sprout, radius*.013, radius*.013)
                        p.setBrush(jc); p.drawEllipse(sprout, max(.75,radius*.0038), max(.75,radius*.0038))

                    # Travelling activation packet follows the connected axon.
                    rhythm = .62 + .38*(.5+.5*math.sin(self._phase*4.8 + i*.31 + edge_no))
                    activity = max(state_activity, self._voice) * rhythm * links * (1.22 if master_edge else .72)
                    if activity > .08 and ((i+edge_no) % 2 == 0):
                        t0 = (self._phase*(.16 + .035*((i+edge_no)%4)) + ((i+edge_no)*.173)%1.0) % 1.0
                        omt = 1.0 - t0
                        px = (omt**3)*anchor.x() + 3*(omt**2)*t0*ctrl1.x() + 3*omt*(t0**2)*ctrl2.x() + (t0**3)*end_pt.x()
                        py = (omt**3)*anchor.y() + 3*(omt**2)*t0*ctrl1.y() + 3*omt*(t0**2)*ctrl2.y() + (t0**3)*end_pt.y()
                        pulse = QPointF(px, py)
                        pc = QColor(238,250,255); pc.setAlpha(int(min(235,70+150*activity)))
                        halo = QColor(c); halo.setAlpha(int(min(100,22+62*activity)))
                        p.setPen(Qt.NoPen); p.setBrush(halo)
                        p.drawEllipse(pulse, radius*.014*activity, radius*.014*activity)
                        p.setBrush(pc)
                        p.drawEllipse(pulse, max(.70,radius*.0038), max(.70,radius*.0038))

        # Nodes are the dominant matter. Cyan is slightly stronger on the left,
        # violet/magenta on the right, as in the final visual reference.
        for point, depth, idx in nodes:
            side_mix = max(0.0, min(1.0, (point.x() - (cx-radius)) / max(1.0, radius*2.0)))
            if side_mix < .53:
                c = QColor(primary)
            else:
                c = QColor(violet)
            front = .55 + .45 * ((depth + 1.0) * .5)
            firing = 0.0
            if self.state in {"SPEAKING", "THINKING", "PROCESSING", "EXECUTING"}:
                firing = max(0.0, math.sin(self._phase*(4.2 + (idx%5)*.21) + idx*.83))
                firing *= (1.0 if self.state == "SPEAKING" else .42)
            alpha = int((64 + 96*self._energy + 32*stable + 50*firing) * front)
            if idx % 9 == 0:
                c = QColor(235, 248, 255)
                alpha = min(245, alpha + 62)
            c.setAlpha(max(14, min(240, alpha)))
            size = radius * (.0058 + .0052*front + (.0038 if idx % 13 == 0 else 0.0))
            # Local halo on bright nodes.
            if idx % 6 == 0:
                hc = QColor(c); hc.setAlpha(max(8, c.alpha()//4))
                p.setBrush(hc); p.setPen(Qt.NoPen)
                p.drawEllipse(point, size*2.3, size*2.3)
            p.setBrush(c); p.setPen(Qt.NoPen)
            p.drawEllipse(point, size, size)

        # Detached motes remain inside the orb edge after stabilization.
        if stable > 0.001:
            for idx in range(int(24*stable)):
                angle = idx*2.399963 + self._phase*(.016 + (idx%3)*.002)
                rr = radius*(0.90 + (idx%9)*.008 + .014*math.sin(self._phase*.22+idx))
                pt = QPointF(cx+math.cos(angle)*rr, cy+math.sin(angle)*rr*.94)
                c = QColor(primary if idx%3 else violet); c.setAlpha(int(60+80*stable))
                sz = max(.7, radius*(.0038 + (idx%3)*.0012))
                p.setPen(Qt.NoPen); p.setBrush(c); p.drawEllipse(pt, sz, sz)

        p.restore()

    def _draw_neural_wave(self, p: QPainter, cx: float, cy: float, width: float,
                          radius: float, primary: QColor, violet: QColor, amount: float) -> None:
        if amount <= 0.001:
            return
        left = max(0.0, cx-radius*1.72)
        right = min(width, cx+radius*1.72)
        voice = max(0.0, min(1.0, float(self._voice)))
        voice_gain = voice ** .68 if voice > 0.0 else 0.0
        speaking = 1.0 if self.state == "SPEAKING" else 0.0
        # Patch 22.4: near-flat idle, but normal speech visibly expands the line.
        base_amp = .010 + .008*(1.0 if self.state in {"THINKING","PROCESSING","LISTENING"} else 0.0)
        speech_amp = speaking * (.012 + .105*voice_gain)
        amp = base_amp + speech_amp
        path = QPainterPath(); steps = 220
        for i in range(steps+1):
            x = left + (right-left) * i/steps
            nx = (x-cx)/max(1.0, radius)
            envelope = .52 + .48*math.exp(-((nx)/1.22)**4)
            carrier = (
                .46*math.sin(nx*10.5 + self._phase*1.35)
                + .25*math.sin(nx*22.8 - self._phase*1.95 + .8)
                + .12*math.sin(nx*44.0 + self._phase*2.65 + 1.7)
            )
            spike_gate = abs(math.sin(nx*21.0 - self._phase*3.4)) ** 7
            transient = math.sin(nx*94.0 + self._phase*(8.0 + 5.0*voice_gain)) * spike_gate
            y = cy + radius*(carrier*amp + speaking*voice_gain*.022*transient)*envelope
            if i == 0: path.moveTo(x,y)
            else: path.lineTo(x,y)
        grad = QLinearGradient(left, cy, right, cy)
        alpha_boost = int(65*voice_gain)
        grad.setColorAt(0.0, self._alpha(primary, int(100*amount)))
        grad.setColorAt(.32, self._alpha(primary, min(255, int(190*amount)+alpha_boost)))
        grad.setColorAt(.55, self._alpha(QColor(225,246,255), min(255, int(130*amount)+alpha_boost)))
        grad.setColorAt(.78, self._alpha(violet, min(255, int(205*amount)+alpha_boost)))
        grad.setColorAt(1.0, self._alpha(violet, int(105*amount)))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(grad, max(4.0,radius*(.013 + .008*voice_gain)), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(grad, max(.8,radius*.0038), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)

    def _draw_neural_reflection(self, p: QPainter, cx: float, cy: float, radius: float,
                                primary: QColor, violet: QColor, amount: float) -> None:
        if amount <= 0.001:
            return
        y = cy + radius*1.08
        # PATCH 17 — stronger concentric holographic pedestal like the final
        # reference, but still thin enough to remain a reflection rather than a
        # physical platform.
        rings = ((1.42, .140, 178), (1.20, .115, 158), (1.00, .092, 138),
                 (.79, .072, 118), (.59, .054, 98), (.39, .038, 78))
        for idx, (scale, squash, alpha) in enumerate(rings):
            rect = QRectF(cx-radius*.86*scale, y-radius*squash,
                          radius*1.72*scale, radius*squash*2.0)
            col = primary if idx not in (1,3) else violet
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self._alpha(col, int(alpha*amount)), max(.60,radius*(.0040-.00030*idx))))
            p.drawEllipse(rect)
        glow = QRadialGradient(cx, y, radius*.52)
        glow.setColorAt(0.0, self._alpha(QColor(238,252,255), int(132*amount)))
        glow.setColorAt(.22, self._alpha(primary, int(96*amount)))
        glow.setColorAt(.62, self._alpha(violet, int(42*amount)))
        glow.setColorAt(1.0, QColor(0,0,0,0))
        p.setPen(Qt.NoPen); p.setBrush(glow)
        p.drawEllipse(QPointF(cx,y), radius*.72, radius*.18)
        # Faint vertical holographic reflection connects the orb to the base.
        shaft = QLinearGradient(cx, cy+radius*.42, cx, y+radius*.08)
        shaft.setColorAt(0.0, QColor(0,0,0,0))
        shaft.setColorAt(.38, self._alpha(primary, int(28*amount)))
        shaft.setColorAt(.72, self._alpha(violet, int(20*amount)))
        shaft.setColorAt(1.0, QColor(0,0,0,0))
        p.setBrush(shaft); p.setPen(Qt.NoPen)
        p.drawRect(QRectF(cx-radius*.16, cy+radius*.42, radius*.32, radius*.88))
    # ------------------------------------------------------------------ backdrop
    def _draw_back_halo(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor, violet: QColor):
        halo = QRadialGradient(cx, cy, radius * 2.05)
        halo.setColorAt(0.0, self._alpha(QColor(18, 91, 185), 54))
        halo.setColorAt(.28, self._alpha(primary, 34 + 20 * self._energy))
        halo.setColorAt(.52, self._alpha(violet, 26 + 28 * self._energy))
        halo.setColorAt(.77, self._alpha(QColor(31, 87, 174), 12))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), radius * 2.05, radius * 2.05)

        # Vertical holographic shaft and falling light under the core.
        shaft = QLinearGradient(cx, cy + radius * .20, cx, cy + radius * 1.72)
        shaft.setColorAt(0.0, self._alpha(primary, 0))
        shaft.setColorAt(.30, self._alpha(primary, 45))
        shaft.setColorAt(.68, self._alpha(QColor(86, 122, 255), 31))
        shaft.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(shaft)
        p.drawPolygon(QPolygonF([
            QPointF(cx - radius * .34, cy + radius * .28),
            QPointF(cx + radius * .34, cy + radius * .28),
            QPointF(cx + radius * .16, cy + radius * 1.56),
            QPointF(cx - radius * .16, cy + radius * 1.56),
        ]))

    def _draw_platform(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor, violet: QColor):
        base_y = cy + radius * 1.16
        # Target pedestal is cyan-dominant with violet secondary reflections.
        for idx, (rx, ry, alpha) in enumerate(((1.42, .25, 175), (1.16, .19, 150), (.91, .14, 130), (.68, .095, 112), (.46, .060, 92))):
            rect = QRectF(cx - radius * rx, base_y - radius * ry, radius * rx * 2, radius * ry * 2)
            c = primary if idx != 2 else violet
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self._alpha(c, alpha), max(.8, radius * (.008 - idx * .001))))
            p.drawEllipse(rect)
        glow = QRadialGradient(cx, base_y, radius * .48)
        glow.setColorAt(0.0, self._alpha(QColor(242, 254, 255), 235))
        glow.setColorAt(.15, self._alpha(primary, 180))
        glow.setColorAt(.48, self._alpha(QColor(74, 112, 255), 55))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, base_y), radius * .50, radius * .12)
        # Narrow emitter column.
        beam = QLinearGradient(cx, cy + radius * .72, cx, base_y)
        beam.setColorAt(0.0, self._alpha(primary, 0))
        beam.setColorAt(.55, self._alpha(primary, 42))
        beam.setColorAt(1.0, self._alpha(QColor(221, 249, 255), 135))
        p.setBrush(beam)
        p.drawPolygon(QPolygonF([
            QPointF(cx-radius*.055, cy+radius*.64), QPointF(cx+radius*.055, cy+radius*.64),
            QPointF(cx+radius*.015, base_y), QPointF(cx-radius*.015, base_y),
        ]))

    # ------------------------------------------------------------------ wave / telemetry
    def _draw_energy_wave(self, p: QPainter, cx: float, cy: float, width: float, radius: float, primary: QColor, violet: QColor):
        """Fine layered waveform crossing the core; no oversized smooth ribbon."""
        span = min(width * .98, radius * 5.55)
        left = cx - span / 2
        count = 300
        points = QPolygonF()
        glow_points = QPolygonF()
        for i in range(count + 1):
            t = i / count
            x = left + span * t
            d = abs(t - .5)
            side = .36 + .92 * math.exp(-((d - .31) / .16) ** 2)
            inner_quiet = .58 + .42 * min(1.0, d / .18)
            carrier = (
                .46 * math.sin(t * math.tau * 8.0 + self._phase * 2.4)
                + .20 * math.sin(t * math.tau * 21.0 - self._phase * 3.3)
                + .09 * math.sin(t * math.tau * 43.0 + self._phase * 1.7)
            )
            y = cy + radius * .085 * (1.0 + .65*self._energy) * side * inner_quiet * carrier
            points.append(QPointF(x, y))
            glow_points.append(QPointF(x, cy + (y-cy)*.80))
        grad = QLinearGradient(left, cy, left + span, cy)
        grad.setColorAt(0.0, self._alpha(primary, 0))
        grad.setColorAt(.23, self._alpha(primary, 220))
        grad.setColorAt(.50, self._alpha(QColor(224, 250, 255), 195))
        grad.setColorAt(.72, self._alpha(violet, 235))
        grad.setColorAt(1.0, self._alpha(violet, 0))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(grad, max(5.0, radius*.028), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(glow_points)
        p.setPen(QPen(grad, max(1.0, radius*.006), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(points)

    def _draw_telemetry_rings(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor, violet: QColor):
        # Sparse outer HUD. Rings are secondary to the living plasma torus.
        specs = ((1.16, 1.1), (1.34, .9), (1.56, .75), (1.73, .65))
        for idx, (scale, pen_scale) in enumerate(specs):
            rr = radius * scale
            c = primary if idx % 2 == 0 else violet
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(self._alpha(c, 70 - idx*8), pen_scale))
            direction = 1 if idx % 2 == 0 else -1
            base = (math.degrees(self._phase) * (.27 + idx*.045) * direction + idx*61) % 360
            for arc_idx, sweep in enumerate((31+idx*4, 12+idx*3, 52-idx*3)):
                angle = base + arc_idx * (101 + idx*9)
                p.drawArc(QRectF(cx-rr, cy-rr, rr*2, rr*2), int(angle*16), int(sweep*16))
        # Target-like cardinal ticks and telemetry sparks.
        for idx in range(36):
            a = idx * math.tau / 36 + self._phase*.08
            rr = radius * (1.30 if idx % 3 else 1.55)
            x, y = cx+math.cos(a)*rr, cy+math.sin(a)*rr
            c = violet if idx % 7 == 0 else primary
            p.setPen(Qt.NoPen); p.setBrush(self._alpha(c, 80+int(75*self._energy)))
            size = max(.8, radius*(.0035 + .0015*(idx%3)))
            p.drawEllipse(QPointF(x,y), size, size)

    # ------------------------------------------------------------------ organic plasma
    def _draw_plasma_torus(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor, violet: QColor):
        """Irregular layered plasma ring replacing uniform concentric bands."""
        # Outer diffuse torus glow.
        p.setBrush(Qt.NoBrush)
        glow_grad = QConicalGradient(cx, cy, -math.degrees(self._phase)*.7)
        glow_grad.setColorAt(0.0, self._alpha(primary, 95))
        glow_grad.setColorAt(.22, self._alpha(QColor(222,248,255), 120))
        glow_grad.setColorAt(.48, self._alpha(violet, 115))
        glow_grad.setColorAt(.75, self._alpha(primary, 100))
        glow_grad.setColorAt(1.0, self._alpha(primary, 95))
        p.setPen(QPen(glow_grad, max(12.0, radius*.090), Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(QPointF(cx,cy), radius*.88, radius*.88)

        # Short, variable-width arclets create a molten/electrical surface.
        segments = 108
        for layer, base_scale in enumerate((.82, .90, .97)):
            for i in range(segments):
                a = i / segments * 360.0
                n = .55*math.sin(i*.73 + self._phase*(3.2+layer*.4)) + .32*math.sin(i*1.91 - self._phase*2.1)
                scale = base_scale + .018*n
                rr = radius*scale
                rect = QRectF(cx-rr, cy-rr, rr*2, rr*2)
                pulse = .5 + .5*math.sin(i*.39 + self._phase*4.0)
                if layer == 0:
                    color = violet if i % 4 in (0,1) else primary
                elif layer == 1:
                    color = QColor(224,247,255) if i % 9 == 0 else (primary if i%3 else violet)
                else:
                    color = primary if i%2 else violet
                alpha = 65 + int((105 + 45*self._energy)*pulse)
                width = radius * (.018 + .018*pulse) * (1.15 if layer==1 else .82)
                p.setPen(QPen(self._alpha(color, alpha), max(1.2,width), Qt.SolidLine, Qt.RoundCap))
                sweep = 2.2 + 2.0*pulse
                p.drawArc(rect, int((a + layer*1.7)*16), int(sweep*16))

    def _draw_electric_arcs(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor, violet: QColor):
        for arc_idx in range(8):
            start = self._phase*(.22 + arc_idx*.015) + arc_idx*math.tau/8
            span = .46 + .09*(arc_idx%3)
            pts = QPolygonF()
            for j in range(45):
                t = j/44
                a = start + span*t
                jitter = .020*math.sin(j*1.73 + self._phase*8 + arc_idx) + .011*math.sin(j*3.11-arc_idx)
                rr = radius*(.88 + jitter)
                pts.append(QPointF(cx+math.cos(a)*rr, cy+math.sin(a)*rr))
            c = primary if arc_idx%2==0 else violet
            p.setPen(QPen(self._alpha(c, 55+int(70*self._energy)), max(3.5,radius*.020), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline(pts)
            p.setPen(QPen(self._alpha(QColor(230,251,255), 150+int(70*self._energy)), max(.7,radius*.004), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline(pts)

    def _draw_inner_filaments(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor, violet: QColor):
        # Orbital/Lissajous plasma paths give the sphere depth and motion.
        for idx in range(7):
            pts = QPolygonF()
            phase = self._phase*(.42+idx*.045) + idx*.83
            for j in range(120):
                t = j/119*math.tau
                x = cx + math.cos(t+phase*.20)*radius*(.66 + .055*math.sin(3*t+phase))
                y = cy + math.sin(t*2 + phase)*radius*(.22 + idx*.022)
                # Rotate each filament deterministically.
                ang = idx*.38 + .20*math.sin(phase*.3)
                dx,dy=x-cx,y-cy
                rx = cx + dx*math.cos(ang)-dy*math.sin(ang)
                ry = cy + dx*math.sin(ang)+dy*math.cos(ang)
                pts.append(QPointF(rx,ry))
            c = primary if idx%2==0 else violet
            p.setPen(QPen(self._alpha(c, 35+idx*14), max(.65,radius*.004)))
            p.drawPolyline(pts)

    # ------------------------------------------------------------------ sphere
    def _draw_sphere(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor, violet: QColor):
        corona = QRadialGradient(cx,cy,radius*1.25)
        corona.setColorAt(0.0,QColor(0,0,0,0))
        corona.setColorAt(.60,self._alpha(primary,10))
        corona.setColorAt(.78,self._alpha(primary,40))
        corona.setColorAt(.91,self._alpha(violet,68))
        corona.setColorAt(1.0,QColor(0,0,0,0))
        p.setPen(Qt.NoPen); p.setBrush(corona)
        p.drawEllipse(QPointF(cx,cy),radius*1.25,radius*1.25)

        # Deep translucent sphere beneath the plasma surface.
        core = QRadialGradient(cx-radius*.12,cy-radius*.16,radius*1.06)
        core.setColorAt(0.0,QColor(2,7,20,248))
        core.setColorAt(.55,QColor(3,10,28,247))
        core.setColorAt(.77,self._alpha(QColor(7,45,80),190))
        core.setColorAt(.92,self._alpha(primary,42))
        core.setColorAt(1.0,self._alpha(violet,70))
        p.setBrush(core); p.setPen(QPen(self._alpha(QColor(157,222,255),55),1.0))
        p.drawEllipse(QPointF(cx,cy),radius*.99,radius*.99)

        # Patch 14 containment: no synaptic filaments or plasma branches are
        # allowed to render outside the orb boundary.
        p.save()
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), radius*.985, radius*.985)
        p.setClipPath(clip, Qt.ReplaceClip)
        self._draw_inner_filaments(p,cx,cy,radius,primary,violet)
        self._draw_plasma_torus(p,cx,cy,radius,primary,violet)
        self._draw_electric_arcs(p,cx,cy,radius,primary,violet)
        p.restore()

        # Smaller dark intelligence core leaves more visible plasma, like target.
        disc = QRadialGradient(cx-radius*.06,cy-radius*.08,radius*.46)
        disc.setColorAt(0.0,QColor(2,6,17,255))
        disc.setColorAt(.70,QColor(3,8,24,252))
        disc.setColorAt(1.0,self._alpha(QColor(62,65,137),90))
        p.setBrush(disc); p.setPen(QPen(self._alpha(QColor(115,143,255),70),1.0))
        p.drawEllipse(QPointF(cx,cy),radius*.45,radius*.45)

    def _draw_particles(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor, violet: QColor, density: float = 1.0):
        # PATCH 02: particle count itself grows with startup progress instead of
        # fading an already-complete field in from frame one.
        density = max(0.0, min(1.0, float(density)))
        count = int(round(112 * density))
        gather = max(0.0, min(1.0, (density - .42) / .58))
        for idx in range(count):
            angle = idx*2.399963 + self._phase*(.11+(idx%3)*.035)
            outer = .62+(idx%19)/18*1.18
            target = .80 + .12*math.sin(idx*.73 + self._phase*.7)
            rr = radius*(outer*(1.0-gather) + target*gather)
            x = cx+math.cos(angle)*rr
            y = cy+math.sin(angle)*rr*.90
            c = primary if idx%5 else violet
            size = max(.55,radius*(.0024+(idx%4)*.00135))
            alpha = int((34+120*self._energy) * (.42+.58*density))
            p.setPen(Qt.NoPen); p.setBrush(self._alpha(c,alpha))
            p.drawEllipse(QPointF(x,y),size,size)
        # Falling digital rain belongs to the structure phase, not the void.
        rain_progress = max(0.0, min(1.0, (density-.66)/.34))
        for idx in range(int(round(20*rain_progress))):
            x = cx+math.sin(idx*1.73)*radius*.58
            y0 = cy+radius*.77+(idx%5)*radius*.055
            length=radius*(.18+.04*(idx%5))
            c=primary if idx%3 else violet
            grad=QLinearGradient(x,y0,x,y0+length)
            grad.setColorAt(0.0,self._alpha(c,int(100*rain_progress))); grad.setColorAt(1.0,QColor(0,0,0,0))
            p.setPen(QPen(grad,max(.6,radius*.0035)))
            p.drawLine(QPointF(x,y0),QPointF(x,y0+length))

    def _draw_brand(self, p: QPainter, cx: float, cy: float, radius: float, primary: QColor):
        if not self.show_brand or radius < 50:
            return
        font=QFont(resolve_orb_font_family())
        font.setWeight(QFont.Medium)
        font.setLetterSpacing(QFont.AbsoluteSpacing,max(4.0,radius*.055))
        font.setPointSizeF(max(12.0,radius*.135))
        p.setFont(font); p.setPen(self._alpha(QColor(235,248,255),248))
        p.drawText(QRectF(cx-radius*.58,cy-radius*.13,radius*1.16,radius*.26),Qt.AlignCenter,"AURA")
        sub=QFont(resolve_orb_font_family())
        sub.setPointSizeF(max(6.5,radius*.038)); sub.setLetterSpacing(QFont.AbsoluteSpacing,max(1.0,radius*.010))
        p.setFont(sub); p.setPen(self._alpha(primary,210))
        p.drawText(QRectF(cx-radius*.70,cy+radius*.12,radius*1.40,radius*.16),Qt.AlignCenter,"ÉCOUTE. COMPREND. AGIT.")

    def paintEvent(self, event):
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        w, h = float(self.width()), float(self.height())
        cx, cy = w*.5, h*.48
        radius = max(42.0, min(w*.282, h*.365))
        radius *= 1.0 + (.006 + .009*self._energy) * math.sin(self._phase*.86)
        primary = QColor(self._primary)
        violet = QColor(self._secondary)

        # Patch 03 canonical boot: void -> sparse matter -> dense matter ->
        # neural links -> volume -> SVG logo -> halo/reflection -> stabilization.
        boot = self._preload_progress if self.state in {"STARTUP", "PRELOAD"} else 1.0
        def stage(start: float, end: float) -> float:
            if boot <= start: return 0.0
            if boot >= end: return 1.0
            x = (boot-start) / max(.0001, end-start)
            return x*x*(3.0-2.0*x)

        sparse = stage(.05, .35)
        dense = stage(.35, .70)
        density = min(1.0, sparse*.30 + dense*.70)
        links = stage(.54, .82)
        core = stage(.68, .90)
        after_logo = stage(.86, .97)
        stable = stage(.93, .995)

        # Patch 22 UI Focus Mode: pause the orb/cortex/particles/reflection.
        # Keep only the reactive waveform; the validated SVG logo is rendered
        # by the wrapper _AuraMarkWidget above this fallback surface.
        wave_reveal = stage(.70, .90)
        self._draw_neural_wave(p, cx, cy, w, radius, primary, violet, wave_reveal)



# ---------------------------------------------------------------------------
# v0.7.0.15.6.11 — Material & Orb Typography Match V11 hybrid OpenGL visual core with fail-safe QPainter fallback.
class OrbWidget(QWidget):
    """Stable public orb API backed by GLSL when the local GPU/context allows it.

    The legacy painter core stays alive underneath until the OpenGL widget has
    successfully compiled and linked its shaders. A driver/context failure is
    therefore visual-only and never prevents AURA from starting.
    """

    def __init__(self, parent=None, *, show_brand: bool = True):
        super().__init__(parent)
        from config.settings import settings

        self.setMinimumSize(300, 300)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color:#010711;")
        self.state = "IDLE"
        self._mood = "neutral"
        self.show_brand = bool(show_brand)
        self._using_opengl = False
        self._gl_surface = None

        self._fallback = PainterOrbWidget(self, show_brand=False)
        self._fallback.show()

        if settings.OPENGL_ORB_ENABLED:
            try:
                from ui.opengl_orb_surface import OpenGLOrbSurface
                self._gl_surface = OpenGLOrbSurface(self)
                self._gl_surface.initialized.connect(self._activate_opengl)
                self._gl_surface.initialization_failed.connect(self._fallback_to_painter)
                self._gl_surface.show()
                # Painter remains above the GL surface until shader init succeeds.
                self._fallback.raise_()
            except Exception as exc:
                import logging
                logging.getLogger("aura.ui.opengl_orb").warning(
                    "OpenGL Orb indisponible à la construction; fallback QPainter: %s", exc
                )
                self._gl_surface = None

        self._orb_font_family = resolve_orb_font_family()
        # PATCH 01.1: initialize the wrapper preload state before any brand
        # visibility method reads it. MainWindow will immediately drive this
        # value to 0..100 during the startup gate. Keeping 1.0 here preserves
        # the legacy standalone OrbWidget behaviour outside startup.
        self._preload_progress = 1.0
        # Legacy typography calibration marker: brand_font.setPixelSize(35)
        self._brand = _AuraMarkWidget(self)
        self._tagline = QLabel("A U R A", self)
        self._tagline.setAlignment(Qt.AlignCenter)
        self._tagline.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        tagline_font = QFont(self._orb_font_family)
        tagline_font.setPixelSize(10)
        tagline_font.setWeight(QFont.Medium)
        tagline_font.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        self._tagline.setFont(tagline_font)
        self._tagline.setStyleSheet(
            "background: transparent; color: rgba(138,205,235,226);"
        )
        self.set_brand_visible(self.show_brand)
        self._sync_child_geometry()

    @property
    def using_opengl(self) -> bool:
        return bool(self._using_opengl)

    def _activate_opengl(self) -> None:
        if self._gl_surface is None:
            return
        self._using_opengl = True
        self._fallback.hide()
        self._gl_surface.raise_()
        self._brand.raise_(); self._tagline.raise_()
        try:
            self._fallback.timer.stop()
        except Exception:
            pass
        import logging
        logging.getLogger("aura.ui.opengl_orb").info("AURA Visual Core backend=opengl-shader")

    def _fallback_to_painter(self, reason: str = "") -> None:
        self._using_opengl = False
        if self._gl_surface is not None:
            self._gl_surface.hide()
        self._fallback.show(); self._fallback.raise_()
        self._brand.raise_(); self._tagline.raise_()
        try:
            if not self._fallback.timer.isActive():
                self._fallback.timer.start(33)
        except Exception:
            pass
        import logging
        logging.getLogger("aura.ui.opengl_orb").warning(
            "AURA Visual Core backend=qpainter-fallback reason=%s", reason or "OpenGL indisponible"
        )

    def _refresh_tagline_color(self) -> None:
        c = _state_mood_colors(self.state, self._mood)[0]
        self._tagline.setStyleSheet(
            f"background: transparent; color: rgba({c.red()},{c.green()},{c.blue()},220);"
        )

    def set_mood(self, mood: str) -> None:
        self._mood = normalize_mood(mood)
        if hasattr(self._fallback, "set_mood"):
            self._fallback.set_mood(self._mood)
        if self._gl_surface is not None and hasattr(self._gl_surface, "set_mood"):
            self._gl_surface.set_mood(self._mood)
        if hasattr(self._brand, "set_mood"):
            self._brand.set_mood(self._mood)
        self._refresh_tagline_color()
        self.update()

    def set_state(self, state: str):
        self.state = state if state in STATE_COLORS else "IDLE"
        self._fallback.set_state(self.state)
        if self._gl_surface is not None:
            self._gl_surface.set_state(self.state)
        if hasattr(self._brand, "set_state"):
            self._brand.set_state(self.state)
        self._refresh_tagline_color()

    def set_preload_progress(self, percent: int) -> None:
        """Drive the visual construction of AURA from the real startup rail."""
        percent = max(0, min(100, int(percent)))
        self._preload_progress = float(percent) / 100.0
        if hasattr(self._fallback, "set_preload_progress"):
            self._fallback.set_preload_progress(percent)
        if self._gl_surface is not None and hasattr(self._gl_surface, "set_preload_progress"):
            self._gl_surface.set_preload_progress(percent)
        if hasattr(self._brand, "set_construction_progress"):
            self._brand.set_construction_progress(self._preload_progress)
        # The AURA tagline follows the logo, rather than being visible from frame 1.
        self._tagline.setVisible(False)
        self.update()

    def set_voice_amplitude(self, value: float) -> None:
        if hasattr(self._fallback, "set_voice_amplitude"):
            self._fallback.set_voice_amplitude(value)
        if self._gl_surface is not None:
            self._gl_surface.set_voice_amplitude(value)

    def set_preload_visual_safety(self, active: bool) -> None:
        """Forward XTTS preload visual safety to the active OpenGL surface.

        MainWindow owns the public OrbWidget wrapper, not OpenGLOrbSurface
        directly.  Keeping this method on the wrapper ensures the preload
        guard is actually engaged while preserving the stable public orb API.
        """
        if self._gl_surface is not None and hasattr(self._gl_surface, "set_preload_visual_safety"):
            self._gl_surface.set_preload_visual_safety(bool(active))

    def restore_post_preload_cinematic(self) -> None:
        """Forward the successful XTTS post-preload cinematic restore."""
        if self._gl_surface is not None and hasattr(self._gl_surface, "restore_post_preload_cinematic"):
            self._gl_surface.restore_post_preload_cinematic()

    def animation_snapshot(self) -> dict:
        if self._gl_surface is not None and hasattr(self._gl_surface, "animation_snapshot"):
            return dict(self._gl_surface.animation_snapshot())
        return {
            "state": self.state,
            "shader_time": 0.0,
            "timer_ticks": 0,
            "paint_frames": 0,
            "timer_active": False,
            "visible": bool(self.isVisible()),
            "started": False,
        }

    def set_brand_visible(self, visible: bool) -> None:
        self.show_brand = bool(visible)
        self._brand.setVisible(self.show_brand)
        self._tagline.setVisible(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_child_geometry()

    def _sync_child_geometry(self) -> None:
        rect = self.rect()
        self._fallback.setGeometry(rect)
        if self._gl_surface is not None:
            self._gl_surface.setGeometry(rect)
        w, h = max(1, rect.width()), max(1, rect.height())
        cy = int(h * .480)
        # PATCH 05: target reference gives the neural glyph more presence,
        # while the open rail geometry keeps it visually lighter than Patch 04.
        mark_w = max(128, int(min(w, h) * .270))
        mark_h = max(146, int(min(w, h) * .312))
        self._brand.setGeometry(int(w*.5 - mark_w*.5), int(cy - mark_h*.52), mark_w, mark_h)
        self._tagline.setGeometry(int(w*.32), cy+int(h*.060), int(w*.36), max(18, int(h*.034)))
