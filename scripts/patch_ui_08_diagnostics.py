from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "ui" / "opengl_orb_surface.py"
text = path.read_text(encoding="utf-8")
checks = {
    "v14_header": "V14 Organic Synaptic Filaments" in text,
    "no_segment_distance_helper": "float segmentDistance(" not in text,
    "no_partner_segments": "float partner =" not in text,
    "organic_filament_block": "PATCH 08 — ORGANIC SYNAPTIC FILAMENTS" in text,
    "warped_field": "vec2 organicP" in text,
    "curved_activity": "Synaptic firing is a moving phase *inside the curved contour field*" in text,
    "bundle_membrane": "Curved luminous bundles gather near the membrane" in text,
}
failed = []
for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")
    if not ok: failed.append(name)
if failed:
    raise SystemExit("Patch 08 diagnostics failed: " + ", ".join(failed))
print("Patch 08 diagnostics: PASS")
