from __future__ import annotations

import sys
from pathlib import Path

# When this file is executed directly (``python scripts\\opengl_orb_probe.py``),
# Python places ``scripts`` on sys.path but not the AURA project root.  Add the
# parent directory explicitly so imports such as ``ui.orb_widget`` work from
# Explorer, cmd.exe, PowerShell and arbitrary working directories.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from ui.orb_widget import OrbWidget


def main() -> int:
    app = QApplication(sys.argv)
    orb = OrbWidget(show_brand=True)
    orb.resize(620, 620)
    orb.set_state("STARTUP")
    orb.show()

    visual_samples = {}

    def sampled_pixels() -> list[tuple[int, int, int]]:
        # Capture the OpenGL framebuffer directly. QWidget.grab() on the parent
        # can return a composited/cached child image on Windows and falsely
        # report zero motion even when the GL FBO changes.
        surface = getattr(orb, "_gl_surface", None)
        if orb.using_opengl and surface is not None and hasattr(surface, "grabFramebuffer"):
            image = surface.grabFramebuffer()
        else:
            image = orb.grab().toImage()
        w = max(1, image.width())
        h = max(1, image.height())
        values: list[tuple[int, int, int]] = []
        # Dense enough to cover moving rings/torus while remaining very cheap.
        for gy in range(3, 30):
            y = min(h - 1, int(h * gy / 32.0))
            for gx in range(3, 30):
                x = min(w - 1, int(w * gx / 32.0))
                c = image.pixelColor(x, y)
                values.append((c.red(), c.green(), c.blue()))
        return values

    def capture_baseline() -> None:
        visual_samples["baseline"] = sampled_pixels()

    def report() -> None:
        backend = "opengl-shader" if orb.using_opengl else "qpainter-fallback"
        stats = orb.animation_snapshot()
        current = sampled_pixels()
        baseline = visual_samples.get("baseline", current)
        count = max(1, min(len(baseline), len(current)))
        delta = 0.0
        for before, after in zip(baseline[:count], current[:count]):
            delta += abs(before[0] - after[0]) + abs(before[1] - after[1]) + abs(before[2] - after[2])
        motion_score = delta / (count * 3.0)
        active = (
            backend == "opengl-shader"
            and bool(stats.get("timer_active"))
            and float(stats.get("shader_time", 0.0)) >= 2.0
            and int(stats.get("paint_frames", 0)) >= 20
            and motion_score >= 0.75
        )
        if backend == "opengl-shader":
            animation_state = "active" if active else "stalled"
        else:
            fallback = getattr(orb, "_fallback", None)
            fallback_timer = getattr(fallback, "timer", None)
            animation_state = "fallback-active" if fallback_timer is not None and fallback_timer.isActive() else "fallback-stalled"
        print("AURA_OPENGL_ORB_BACKEND=" + backend)
        print(
            "AURA_OPENGL_ORB_ANIMATION=" + animation_state
            + " shader_time={:.2f}s ticks={} frames={} motion_score={:.2f}".format(
                float(stats.get("shader_time", 0.0)),
                int(stats.get("timer_ticks", 0)),
                int(stats.get("paint_frames", 0)),
                motion_score,
            )
        )
        print(
            "AURA_OPENGL_ORB_PACING=display_refresh={:.2f}Hz target_fps={:.2f} frame_gap_p95={:.1f}ms max_gap={:.1f}ms".format(
                float(stats.get("display_refresh_hz", 0.0)),
                float(stats.get("target_fps", 0.0)),
                float(stats.get("frame_gap_p95_ms", 0.0)),
                float(stats.get("max_frame_gap_ms", 0.0)),
            )
        )
        app.quit()

    QTimer.singleShot(900, capture_baseline)
    QTimer.singleShot(4200, report)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
