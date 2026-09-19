
from __future__ import annotations
from pathlib import Path

IMPORT = "from ui.developer_mode_web_surface import apply_web_developer_mode\n"

def patch_visual(path: Path):
    source=path.read_text(encoding="utf-8-sig",errors="strict")
    original=source
    if IMPORT.strip() not in source:
        anchor="from runtime.aura_developer_mode import developer_mode_enabled\n"
        if anchor not in source:
            raise RuntimeError("developer visual import anchor missing")
        source=source.replace(anchor,anchor+IMPORT,1)

    fn_anchor="def apply_developer_mode_visuals(window, enabled: bool):\n"
    if fn_anchor not in source:
        raise RuntimeError("apply_developer_mode_visuals anchor missing")

    if "web_result = apply_web_developer_mode(window, enabled)" not in source:
        insert=(
            "def apply_developer_mode_visuals(window, enabled: bool):\n"
            "    # AURA v1.3.0 visible surface is the QWebEngine/Three.js shell.\n"
            "    # Apply there first; native Qt badges remain a fallback only.\n"
            "    try:\n"
            "        web_result = apply_web_developer_mode(window, enabled)\n"
            "    except Exception:\n"
            "        web_result = {\"webviews_applied\": 0, \"webviews_found\": 0}\n"
        )
        source=source.replace(fn_anchor,insert,1)

    if source!=original:
        path.write_text(source,encoding="utf-8",newline="\n")
    return {"changed":source!=original,"web_surface_call":True}
