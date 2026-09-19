from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.local_first_voice import self_reply, social_reply
from database.database import Database
from memory.learning import AdaptiveLearningEngine

checks: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")


with tempfile.TemporaryDirectory() as tmp:
    db = Database(Path(tmp) / "living-personality.db")
    engine = AdaptiveLearningEngine(db)

    before = engine.style()
    changes = engine.observe_user_message("Sois plus spontanée")
    after = engine.style()
    check("spontaneity directive learned", "réponses plus spontanées" in changes and after.spontaneity > before.spontaneity)
    check("spontaneity no longer changes formality", abs(after.formality - before.formality) < 1e-9 and "ton moins formel" not in changes)

    changes = engine.observe_user_message("Sois plus sensuelle")
    check("sensuality remains independently learnable", "présence plus sensuelle" in changes and engine.style().sensuality > before.sensuality)
    changes = engine.observe_user_message("Sois plus joueuse")
    check("playfulness remains independently learnable", "ton plus joueur" in changes and engine.style().playfulness > before.playfulness)

    compact = engine.render_for_prompt(compact=True)
    full = engine.render_for_prompt(compact=False)
    check("prompt composes axes instead of fixed persona phrases", "Combine les axes" in compact)
    check("prompt declares spontaneity/formality independence", "Spontanéité et formalité sont indépendantes" in compact)
    check("prompt declares context precedence", "sécurité et contexte sérieux > mode courant > relation > personnalité apprise" in full)
    db.close()

baseline = social_reply(
    "Comment vas-tu ?", familiarity=0.95, warmth=0.72, sensuality=0.62,
    playfulness=0.45, spontaneity=0.55, learning_interactions=10, learning_revision=2,
)
sensual = social_reply(
    "Comment vas-tu ?", familiarity=0.95, warmth=0.88, sensuality=0.92,
    playfulness=0.45, spontaneity=0.55, learning_interactions=10, learning_revision=2,
)
check("sensuality visibly colors NORMAL wellbeing", sensual != baseline and any(t in sensual.casefold() for t in ("douce", "ambiance", "présence", "pose")))

playful = social_reply(
    "Comment vas-tu ?", familiarity=0.95, playfulness=0.92, spontaneity=0.92,
    sensuality=0.45, emoji_affinity=0.82, learning_interactions=10, learning_revision=2,
)
check("playful spontaneous profile changes wording", any(t in playful.casefold() for t in ("joueuse", "taquine", "sage")))
check("living dialogue may emit emoji when learned", "😏" in playful)

serious = social_reply(
    "Comment vas-tu ?", mode="SERIOUS", familiarity=0.95, warmth=0.95,
    playfulness=1.0, sensuality=1.0, spontaneity=1.0, expressiveness=1.0, emoji_affinity=1.0,
)
check("SERIOUS mode suppresses sensual/playful surface", all(t not in serious.casefold() for t in ("sage", "taquine", "joueuse", "sensuelle")) and "😏" not in serious)
check("SERIOUS mode remains attentive", "attentive" in serious.casefold())

formal_spontaneous = social_reply(
    "Comment vas-tu ?", familiarity=0.95, formality=0.90, spontaneity=0.90,
    playfulness=0.95, sensuality=0.95, proactivity=0.70,
)
check("formal + spontaneous coexist coherently", "élan" in formal_spontaneous.casefold() and "sage" not in formal_spontaneous.casefold())

first = social_reply(
    "Comment vas-tu ?", familiarity=0.95, playfulness=0.92, spontaneity=0.92,
    sensuality=0.45, emoji_affinity=0.82, learning_interactions=20, learning_revision=3,
)
second = social_reply(
    "Comment vas-tu ?", familiarity=0.95, playfulness=0.92, spontaneity=0.92,
    sensuality=0.45, emoji_affinity=0.82, learning_interactions=21, learning_revision=3,
)
again = social_reply(
    "Comment vas-tu ?", familiarity=0.95, playfulness=0.92, spontaneity=0.92,
    sensuality=0.45, emoji_affinity=0.82, learning_interactions=20, learning_revision=3,
)
check("continuity creates deterministic phrase variation", first == again and first != second)

meta = self_reply(
    "Est-ce que tu te considères consciente ?", familiarity=0.95,
    playfulness=1.0, sensuality=1.0, spontaneity=1.0, emoji_affinity=1.0,
)
check("metacognition stays grounded despite personality", "consciente au sens fonctionnel" in meta and "😏" not in meta)
check("factual questions are not hijacked", social_reply("Quelle est la capitale du Japon ?", playfulness=1.0, sensuality=1.0) == "")

main_source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
settings_source = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")
check("voice-primary SelfModel path preserved", "AURA self dialogue handled local delivery=%s" in main_source)
check("ambient conversation autoshow policy preserved", "conversation_autoshow" in main_source and "_voice_primary_turn" in main_source)
check("public version remains 0.7.2", 'APP_VERSION: str = "0.7.2"' in settings_source or 'APP_VERSION = "0.7.2"' in settings_source)

failed = [name for name, ok in checks if not ok]
print(f"\nResult: {len(checks) - len(failed)}/{len(checks)} PASS")
if failed:
    print("Failed:", ", ".join(failed))
    raise SystemExit(1)
