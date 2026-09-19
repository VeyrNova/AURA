from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.local_first_voice import self_reply
from database.database import Database
from memory.learning import AdaptiveLearningEngine
from voice.xtts_tts import _split_native_stream_text, _XTTS_NATIVE_SEGMENT_MAX_CHARS

checks: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")


with tempfile.TemporaryDirectory() as tmp:
    db = Database(Path(tmp) / "adaptive-personality.db")
    engine = AdaptiveLearningEngine(db)

    before = engine.style()
    changes = engine.observe_user_message("Sois plus sensuelle")
    after = engine.style()
    check("sensuality directive learned", "présence plus sensuelle" in changes and after.sensuality > before.sensuality)
    check("sensuality change is persistent revision", engine.revision == 1 and engine.explicit_feedback_count == 1)
    ack = engine.acknowledgement(changes)
    check("personality adaptation has local acknowledgement", "Je m'adapte" in ack and "sensuelle" in ack)

    changes = engine.observe_user_message("Sois plus joueuse")
    check("playfulness directive learned", "ton plus joueur" in changes and engine.style().playfulness > after.playfulness)

    changes = engine.observe_user_message("Sois plus complice")
    check("complicity maps to bounded dimensions", "présence plus complice" in changes and engine.style().warmth > before.warmth)

    previous_formality = engine.style().formality
    changes = engine.observe_user_message("Adopte un ton beaucoup moins formel")
    check("natural less-formal directive learned", bool(changes) and engine.style().formality < previous_formality)

    snapshot = engine.style()
    changes = engine.observe_user_message("Elle est sensuelle et joueuse dans ce film")
    check("ordinary trait statement does not drift", changes == [] and engine.style() == snapshot)

    prompt = engine.render_for_prompt(compact=True)
    dialogue = engine.dialogue_kwargs()
    check("adaptive prompt exports personality axes", "sensualité=" in prompt and "spontanéité=" in prompt)
    check("local dialogue exports personality axes", all(k in dialogue for k in ("playfulness", "sensuality", "formality", "expressiveness", "spontaneity")))
    db.close()

self_text = self_reply(
    "Comment as-tu changé depuis qu'on se parle ?",
    learning_revision=7,
    learned_preferences=5,
    last_learning_change="présence plus sensuelle, ton plus joueur et réponses plus spontanées",
    verbosity=0.20,
    directness=0.92,
)
check("self evolution respects concise adaptive style", "révision comportementale 7" in self_text and len(self_text) <= _XTTS_NATIVE_SEGMENT_MAX_CHARS)

long_text = (
    "J'ai surtout changé dans ma manière de te répondre et de garder le fil entre nos échanges. "
    "J'ai intégré plusieurs retours explicites et j'en suis à une nouvelle révision comportementale. "
    "Ma dernière adaptation concerne ma façon d'être plus directe, plus naturelle et plus attentive avec toi dans nos échanges."
)
segments = _split_native_stream_text(long_text)
check("long XTTS text is segmented", len(segments) > 1)
check("all XTTS segments stay under French safety ceiling", bool(segments) and max(map(len, segments)) <= _XTTS_NATIVE_SEGMENT_MAX_CHARS)
check("short XTTS text stays single segment", len(_split_native_stream_text("Je suis là, attentive et prête à continuer avec toi.")) == 1)

learning_source = (ROOT / "memory" / "learning.py").read_text(encoding="utf-8")
dialogue_source = (ROOT / "consciousness" / "dialogue.py").read_text(encoding="utf-8")
local_voice_source = (ROOT / "ai" / "local_first_voice.py").read_text(encoding="utf-8")
xtts_source = (ROOT / "voice" / "xtts_tts.py").read_text(encoding="utf-8")
check("explicit style directive gate exists", "_EXPLICIT_STYLE_DIRECTIVE" in learning_source)
check("sensuality axis reaches deterministic dialogue", "sensuality: float = 0.62" in dialogue_source and "sensuality=sensuality" in local_voice_source)
check("native stream iterates safe segments", xtts_source.count("for segment_index, native_segment in enumerate(native_segments)") >= 2)
check("native stream inserts natural phrase pause", "_native_segment_pause_pcm" in xtts_source)
check("native XTTS safety margin is 240 chars", _XTTS_NATIVE_SEGMENT_MAX_CHARS == 240)

failed = [name for name, ok in checks if not ok]
print(f"\nResult: {len(checks) - len(failed)}/{len(checks)} PASS")
if failed:
    print("Failed:", ", ".join(failed))
    raise SystemExit(1)
