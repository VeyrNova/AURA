from __future__ import annotations

import argparse
import sys
from pathlib import Path


def check(root: Path) -> tuple[bool, list[tuple[str, bool, str]]]:
    main_path = root / "ui" / "main_window.py"
    orb_path = root / "ui" / "orb_widget.py"
    gl_path = root / "ui" / "opengl_orb_surface.py"
    final_modules = root / "ui" / "final_modules.py"

    results: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        results.append((name, bool(ok), detail))

    for p in (main_path, orb_path, gl_path, final_modules):
        add(f"file:{p.relative_to(root)}", p.is_file(), str(p))
    if not all(p.is_file() for p in (main_path, orb_path, gl_path, final_modules)):
        return False, results

    main = main_path.read_text(encoding="utf-8")
    orb = orb_path.read_text(encoding="utf-8")
    gl = gl_path.read_text(encoding="utf-8")

    add(
        "no_runtime_preheat_popup",
        "self.preheat_overlay = None" in main
        and "self.preheat_overlay = PreheatOverlay(" not in main,
        "Le préchauffage doit rester dans le shell principal.",
    )
    add(
        "boot_rail_inside_home_hero",
        main.find("hero_lay.addWidget(self.orb, 1)") >= 0
        and main.find("self.boot_banner = QFrame()", main.find("hero_lay.addWidget(self.orb, 1)")) >= 0
        and main.find("hero_lay.addWidget(self.boot_banner", main.find("self.boot_banner = QFrame()")) >= 0,
        "La barre de chargement est directement sous OrbWidget.",
    )
    add(
        "profile_kos_removed",
        'who = QLabel("K-0S\\nProfil actif")' not in main,
        "Le bloc profil K-0S ne doit plus être construit.",
    )
    add(
        "fixed_kos_greeting_removed",
        'Bonsoir K-0S' not in main,
        "Aucune salutation K-0S ne doit rester.",
    )
    add(
        "dynamic_time_greeting",
        '"Bonjour, que faisons nous ?"' in main
        and '"Bonsoir, que faisons nous ?"' in main
        and "5 <= now.hour < 18" in main,
        "Bonjour 05:00–17:59, Bonsoir 18:00–04:59.",
    )
    add(
        "startup_greeting_spoken_once",
        "_startup_greeting_announced" in main
        and "force_output=True" in main
        and "_speak_text(" in main,
        "La salutation de boot est prononcée une fois si la voix est disponible.",
    )
    add(
        "single_progress_pipeline",
        "_startup_global_percent" in main
        and "_xtts_global_percent" in main
        and "_finish_startup_sequence" in main,
        "Progression initiale + XTTS partagent une seule barre 0–100.",
    )
    add(
        "orb_progress_api",
        "def set_preload_progress(self, percent: int)" in orb,
        "OrbWidget expose une progression de construction.",
    )
    wrapper_start = orb.find("class OrbWidget")
    init_progress = orb.find("self._preload_progress = 1.0", wrapper_start)
    brand_visibility = orb.find("self.set_brand_visible(self.show_brand)", wrapper_start)
    add(
        "wrapper_preload_initialized_before_brand",
        init_progress >= 0 and brand_visibility >= 0 and init_progress < brand_visibility,
        "_preload_progress doit exister avant set_brand_visible().",
    )
    add(
        "logo_construction",
        "set_construction_progress" in orb
        and "self._preload_progress >= 0.82" in orb,
        "Le logo/tagline apparaissent dans les derniers stades.",
    )
    add(
        "opengl_boot_uniform",
        "uniform float u_boot_progress;" in gl
        and '"u_boot_progress"' in gl
        and "self._preload_progress" in gl,
        "Le shader OpenGL reçoit la vraie progression de boot.",
    )
    add(
        "staged_orb_construction",
        all(token in gl for token in (
            "buildParticles", "buildBeam", "buildRings", "buildWaves", "buildCore"
        )),
        "Particules → faisceau → anneaux → ondes → noyau.",
    )

    return all(ok for _, ok, _ in results), results


def main() -> int:
    parser = argparse.ArgumentParser(description="AURA UI Patch 01 boot/orb diagnostics")
    parser.add_argument("root", nargs="?", default=".", help="Racine de l'installation AURA")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    ok, results = check(root)
    print("=== AURA UI PATCH 01 — BOOT / ORB DIAGNOSTICS ===")
    for name, passed, detail in results:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
