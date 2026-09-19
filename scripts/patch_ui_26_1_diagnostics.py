from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.local_first_voice import social_reply
from config.settings import settings

main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
mods = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8")
dialogue = (ROOT / "consciousness" / "dialogue.py").read_text(encoding="utf-8")

checks: list[tuple[str, bool]] = []
def check(name: str, condition: bool) -> None:
    checks.append((name, bool(condition)))

check("app_version_072", settings.APP_VERSION == "0.7.2")
check("bonjour_period_social", social_reply("Bonjour Aura.", familiarity=.95).startswith("Bonjour."))
check("aura_prefix_social", bool(social_reply("Aura, bonjour !", familiarity=.95)))
check("emoji_salut_social", bool(social_reply("Salut Aura 😊", familiarity=.95)))
check("hello_social", bool(social_reply("Hello Aura", familiarity=.95)))
check("wellbeing_variant_social", bool(social_reply("Tu vas bien Aura ?", familiarity=.95)))
check("factual_bonjour_not_hijacked", social_reply("Cherche la chanson Bonjour Aura", familiarity=.95) == "")
check("social_preempts_visual", main.index("AURA social ambient handled local delivery") < main.index("visual_followup = bool", main.index("AURA social ambient handled local delivery")))
check("social_voice_primary", "self._voice_primary_turn = bool(voice_available)" in main[main.rfind("social_reply = xtts_local_first_social_reply", 0, main.index("AURA social ambient handled local delivery")):main.index("visual_followup = bool", main.index("AURA social ambient handled local delivery"))])
check("guardian_raw_error_hidden", "self.chat_panel.add_system_message(str(exc))" not in main[main.index("except ResourcePressureError as exc:", main.index("def _continue_after_agent_router")):main.index("except Exception:", main.index("except ResourcePressureError as exc:", main.index("def _continue_after_agent_router")))])
check("composer_min_40", "self._min_height = 40" in chat)
check("composer_max_104", "self._max_height = 104" in chat)
check("composer_autogrow", "self.textChanged.connect(self._sync_height)" in chat)
check("composer_controls_centered", "Qt.AlignVCenter" in chat)
check("avatar_26px", "self.setFixedSize(26, 26)" in chat)
check("aura_bubble_1040", 'bubble.setMaximumWidth(1040 if role == "aura" else 780)' in chat)
check("context_card_compact", "context.setFixedHeight(146)" in mods)
check("suggestions_card_compact", "suggestions.setFixedHeight(238)" in mods)
check("rail_not_stretched", "root.addWidget(suggestions, 1)" not in mods and "root.addStretch(1)" in mods)
check("social_address_normalizer", "def _strip_aura_address" in dialogue)

print("=== PATCH UI 26.1 DIAGNOSTICS ===")
failed = 0
for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    failed += 0 if ok else 1
print(f"RESULT {len(checks)-failed}/{len(checks)} PASS")
raise SystemExit(1 if failed else 0)
