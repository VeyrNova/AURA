from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.local_first_voice import self_reply  # noqa: E402
from config.settings import settings  # noqa: E402

main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
dialogue = (ROOT / "consciousness" / "dialogue.py").read_text(encoding="utf-8")

checks: list[tuple[str, bool]] = []
def check(name: str, cond: bool) -> None:
    checks.append((name, bool(cond)))

check("public_version_072", settings.APP_VERSION == "0.7.2")
check("self_state_helper_present", "def _self_state_reply" in dialogue)
check("self_reference_gate", 'self_tokens = {"tu", "te", "toi", "ton", "ta", "tes", "votre", "vos", "t", "aura"}' in dialogue)
check("emotion_family_local", bool(self_reply("Quelles sont tes émotions ?", familiarity=0.95)))
check("feeling_family_local", bool(self_reply("Que ressens-tu ?", familiarity=0.95)))
check("fear_family_local", "prudence" in self_reply("Tu peux avoir peur ?", familiarity=0.95).casefold())
check("curiosity_family_local", "curios" in self_reply("Qu'est-ce qui te rend curieuse ?", familiarity=0.95).casefold())
check("attachment_family_local", "amour humain" in self_reply("Tu m'aimes ?", familiarity=0.95).casefold())
check("external_emotion_not_hijacked", self_reply("Quelles émotions sont présentes dans ce film ?", familiarity=0.95) == "")
check("self_route_before_visual", main.index("AURA self dialogue handled local delivery") < main.index("visual_followup = bool", main.index("AURA self dialogue handled local delivery")))
check("aura_width_70pct", "min_ratio, max_ratio, growth_chars = 0.56, 0.70, 230.0" in chat)
check("user_width_52pct", "min_ratio, max_ratio, growth_chars = 0.43, 0.52, 170.0" in chat)
check("resize_reflow", "def _apply_feed_widths" in chat and "def resizeEvent" in chat)
check("result_card_70pct", "int(available * 0.70)" in chat and "card.apply_available_width" in chat)
check("message_body_13px", "font-size: 13px; line-height: 1.24;" in main)
check("metadata_readable", "QLabel#messageTime { color: #65738e; font-size: 9px; }" in main)
check("ambient_policy_preserved", "Home display policy=ambient conversation_autoshow=False" in main)
check("no_xtts_or_opengl_patch_dependency", (ROOT / "voice" / "xtts_tts.py").exists() and (ROOT / "ui" / "opengl_orb_surface.py").exists())

for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")

passed = sum(1 for _, ok in checks if ok)
print(f"RESULT: {passed}/{len(checks)} PASS")
raise SystemExit(0 if passed == len(checks) else 1)
