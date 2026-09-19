from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from core.spoken_version import (
    canonical_product_version,
    format_spoken_product_version,
    is_product_version_query,
    product_identity_text,
    rewrite_aura_product_version_for_speech,
)

assert AURA_VERSION == "0.9.4", AURA_VERSION
assert canonical_product_version() == "0.9.4"
assert format_spoken_product_version() == "zero point neuf point quatre"
assert format_spoken_product_version("0.8.7.1") == "zero point huit point sept point un"
assert format_spoken_product_version("v0.8.7.2") == "zero point huit point sept point deux"
assert product_identity_text() == "AURA, version 0.9.4"

assert is_product_version_query("AURA, quelle version es-tu ?")
assert is_product_version_query("Quelle est ta version actuelle ?")
assert is_product_version_query("Quelle version es-tu ?")
assert is_product_version_query("Tu es en quelle version ?")

assert not is_product_version_query("Quelle version de Python utilises-tu ?")
assert not is_product_version_query("Quelle version de Windows utilises-tu ?")
assert not is_product_version_query("Quelle version de XTTS utilises-tu ?")
assert not is_product_version_query("Quelle version du bridge utilises-tu ?")
assert not is_product_version_query("Quelle version de l'interface UI utilises-tu ?")

bad = rewrite_aura_product_version_for_speech("Je suis AURA, version 8.6.7.1.")
assert "8.6.7.1" not in bad, bad
assert "zero point neuf point quatre" in bad, bad

current = rewrite_aura_product_version_for_speech("AURA version 0.9.4")
assert "0.9.4" not in current, current
assert "zero point neuf point quatre" in current, current

technical = "Bridge version P0.6.5.4; UI release 0.7.2.2-rc4.2"
assert rewrite_aura_product_version_for_speech(technical) == technical

from ai.local_first_voice import self_reply
reply = self_reply("AURA, quelle version es-tu ?")
assert "0.9.4" in str(reply), reply
assert "8.6.7.1" not in str(reply), reply

from voice.text_to_speech import sanitize_for_speech
spoken = sanitize_for_speech(str(reply))
assert "0.9.4" not in spoken, spoken
assert "zero point neuf point quatre" in spoken.lower(), spoken

print("[PASS] spoken product version invariant v0872")
raise SystemExit(0)
