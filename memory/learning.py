"""Controlled adaptive learning for AURA v0.7.2.

AURA may evolve from explicit user feedback without silently rewriting identity,
permissions, security policy or source code.  Patch 25.6 keeps the learned profile bounded while making personality axes
independent and usable by the living dialogue composer.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import json
import re
import unicodedata


@dataclass(frozen=True)
class AdaptiveStyle:
    warmth: float = 0.72
    verbosity: float = 0.34
    directness: float = 0.78
    emoji_affinity: float = 0.45
    proactivity: float = 0.62
    playfulness: float = 0.50
    sensuality: float = 0.62
    formality: float = 0.22
    expressiveness: float = 0.56
    spontaneity: float = 0.58

    def bounded(self) -> "AdaptiveStyle":
        return AdaptiveStyle(**{
            key: max(0.0, min(1.0, float(value)))
            for key, value in asdict(self).items()
        })


class AdaptiveLearningEngine:
    """Persist small, auditable behavioral adaptations from explicit feedback."""

    KEY_STYLE = "learning.style.v1"
    KEY_REVISION = "learning.revision"
    KEY_FEEDBACK = "learning.explicit_feedback"
    KEY_INTERACTIONS = "learning.interactions"
    KEY_LAST_CHANGE = "learning.last_change"
    KEY_LAST_CHANGE_AT = "learning.last_change_at"

    _RESPONSE_SHORT = re.compile(r"\b(?:plus|tr[eè]s)\s+(?:court(?:e|es|s)?|concis(?:e|es|s)?)\b|\br[eé]ponses?\s+(?:plus\s+)?courtes?\b", re.I)
    _RESPONSE_LONG = re.compile(r"\b(?:plus|davantage)\s+(?:d[eé]taill[eé]e?s?|long(?:ue|ues|s)?)\b|\bd[eé]veloppe\s+(?:plus|davantage)\b", re.I)
    _WARMER = re.compile(r"\bplus\s+(?:humain(?:e)?|naturel(?:le)?|chaleureu(?:x|se)|personnel(?:le)?)\b", re.I)
    _COOLER = re.compile(r"\bmoins\s+(?:familier(?:e)?|chaleureu(?:x|se)|personnel(?:le)?)\b|\bplus\s+formel(?:le)?\b", re.I)
    _MORE_DIRECT = re.compile(r"\bplus\s+direct(?:e)?\b|\bva\s+droit\s+au\s+but\b", re.I)
    _LESS_DIRECT = re.compile(r"\bmoins\s+direct(?:e)?\b|\bplus\s+doux|\bplus\s+nuanc[eé]", re.I)
    _MORE_EMOJI = re.compile(r"\bplus\s+d['’]?emojis?\b|\butilise\s+(?:davantage|plus)\s+d['’]?emojis?\b", re.I)
    _LESS_EMOJI = re.compile(r"\bmoins\s+d['’]?emojis?\b|\bsans\s+emojis?\b|\bn['’]?utilise\s+pas\s+d['’]?emojis?\b", re.I)
    _MORE_PROACTIVE = re.compile(r"\bplus\s+proactive\b|\brelance[- ]?moi\b|\bpose[- ]?moi\s+(?:des|plus\s+de)\s+questions\b", re.I)
    _LESS_PROACTIVE = re.compile(r"\bmoins\s+proactive\b|\bne\s+(?:me\s+)?relance\s+pas\b|\bpose\s+moins\s+de\s+questions\b|\bne\s+pose\s+pas\s+de\s+question", re.I)

    # Intent-aware trait vocabulary.  It is deliberately activated only by an
    # explicit behavioral directive ("sois plus...", "adopte un ton...", etc.).
    # Ordinary statements such as "elle est sensuelle" never mutate AURA.
    _EXPLICIT_STYLE_DIRECTIVE = re.compile(
        r"(?:\bsois\b|\bdeviens\b|\breste\b|\bparle\b|\br[eé]ponds?\b|\badopte\b|\bprends?\b|"
        r"\bj['’]?aimerais\s+que\s+tu\s+sois\b|\bje\s+veux\s+que\s+tu\s+sois\b|"
        r"\btu\s+peux\s+(?:[eê]tre|devenir)\b|\bessaie\s+d['’]?[eê]tre\b)",
        re.I,
    )

    # name -> (positive aliases, negative aliases, changes)
    # A change tuple is (field, positive_delta, user-facing label).
    _TRAIT_RULES = (
        ("sensuality", ("sensuelle", "sensuel", "seduisante", "seductrice", "envoutante", "feutree"), (), (("sensuality", 0.12, "présence plus sensuelle"),)),
        ("playfulness", ("joueuse", "taquine", "espiegle", "malicieuse"), (), (("playfulness", 0.12, "ton plus joueur"),)),
        ("softness", ("douce", "tendre", "delicate", "apaisante"), (), (("warmth", 0.08, "ton plus doux"),)),
        ("complicity", ("complice", "proche", "connivente"), (), (("warmth", 0.08, "présence plus complice"), ("playfulness", 0.06, "ton plus joueur"))),
        ("spontaneity", ("spontanee", "spontane", "naturelle", "fluide"), (), (("spontaneity", 0.12, "réponses plus spontanées"),)),
        ("expressiveness", ("expressive", "vivante", "animee"), (), (("expressiveness", 0.12, "présence plus expressive"),)),
        ("reserved", ("reservee", "reserve", "discrete", "discret", "retenue"), (), (("expressiveness", -0.10, "présence plus réservée"), ("playfulness", -0.06, "ton moins joueur"), ("formality", 0.06, "ton plus posé"))),
        ("formal", ("formelle", "formel", "professionnelle", "professionnel"), (), (("formality", 0.12, "ton plus formel"), ("playfulness", -0.08, "ton moins joueur"), ("sensuality", -0.08, "présence moins sensuelle"))),
        ("relaxed", ("detendue", "detendu", "decontractee", "decontracte"), (), (("formality", -0.10, "ton plus détendu"), ("playfulness", 0.06, "ton plus joueur"))),
        ("serious", ("serieuse", "serieux", "sobre"), (), (("formality", 0.10, "ton plus sérieux"), ("playfulness", -0.10, "ton moins joueur"), ("sensuality", -0.08, "présence moins sensuelle"))),
    )

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _int(value, default: int = 0) -> int:
        try:
            return int(value or default)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_spaces(text: str) -> str:
        return " ".join(str(text or "").strip().split())

    @staticmethod
    def _strip_accents(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(text or ""))
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))

    @classmethod
    def _intent_text(cls, text: str) -> str:
        return cls._strip_accents(cls._normalize_spaces(text)).casefold().replace("’", "'")

    def style(self) -> AdaptiveStyle:
        raw = self.db.get_preference(self.KEY_STYLE)
        if not raw:
            return AdaptiveStyle()
        try:
            data = json.loads(raw)
            base = AdaptiveStyle()
            values = asdict(base)
            for key in values:
                if key in data:
                    values[key] = float(data[key])
            # Old v1 JSON remains valid: newly introduced dimensions simply use
            # their stable defaults until the user explicitly changes them.
            return AdaptiveStyle(**values).bounded()
        except (TypeError, ValueError, json.JSONDecodeError):
            return AdaptiveStyle()

    @property
    def revision(self) -> int:
        return self._int(self.db.get_preference(self.KEY_REVISION))

    @property
    def explicit_feedback_count(self) -> int:
        return self._int(self.db.get_preference(self.KEY_FEEDBACK))

    @property
    def interactions(self) -> int:
        return self._int(self.db.get_preference(self.KEY_INTERACTIONS))

    @property
    def last_change(self) -> str:
        return str(self.db.get_preference(self.KEY_LAST_CHANGE) or "").strip()

    def _save_style(self, style: AdaptiveStyle, summary: str) -> None:
        style = style.bounded()
        self.db.set_preference(self.KEY_STYLE, json.dumps(asdict(style), ensure_ascii=False, sort_keys=True))
        self.db.set_preference(self.KEY_REVISION, str(self.revision + 1))
        self.db.set_preference(self.KEY_FEEDBACK, str(self.explicit_feedback_count + 1))
        self.db.set_preference(self.KEY_LAST_CHANGE, summary)
        self.db.set_preference(self.KEY_LAST_CHANGE_AT, datetime.now().astimezone().isoformat(timespec="seconds"))

    @staticmethod
    def _has_modifier_near_alias(message: str, alias: str, modifier: str) -> bool:
        # Keep the parser deterministic while allowing natural word order:
        # "sois un peu plus sensuelle", "un ton beaucoup moins formel".
        alias = re.escape(alias)
        modifier_group = f"(?:{modifier})"
        return bool(re.search(rf"\b{modifier_group}\b(?:\s+\w+){{0,3}}\s+\b{alias}\b|\b{alias}\b(?:\s+\w+){{0,2}}\s+\b{modifier_group}\b", message, re.I))

    def _apply_personality_directive(self, message: str, adjust) -> None:
        normalized = self._intent_text(message)
        if not normalized or not self._EXPLICIT_STYLE_DIRECTIVE.search(normalized):
            return

        for _name, positive_aliases, _negative_aliases, changes in self._TRAIT_RULES:
            matched_alias = ""
            direction = 0
            for alias in positive_aliases:
                if self._has_modifier_near_alias(normalized, alias, "plus|davantage"):
                    matched_alias = alias
                    direction = 1
                    break
                if self._has_modifier_near_alias(normalized, alias, "moins"):
                    matched_alias = alias
                    direction = -1
                    break
            if not matched_alias:
                continue
            for field, delta, label in changes:
                effective = delta * direction
                if direction < 0:
                    # Reverse user-facing semantics without proliferating a
                    # second vocabulary table.
                    if label.startswith("présence plus"):
                        out_label = label.replace("présence plus", "présence moins", 1)
                    elif label.startswith("ton plus"):
                        out_label = label.replace("ton plus", "ton moins", 1)
                    elif label.startswith("réponses plus"):
                        out_label = label.replace("réponses plus", "réponses moins", 1)
                    elif label.startswith("style plus"):
                        out_label = label.replace("style plus", "style moins", 1)
                    elif label.startswith("style moins"):
                        out_label = label.replace("style moins", "style plus", 1)
                    elif label.startswith("ton moins"):
                        out_label = label.replace("ton moins", "ton plus", 1)
                    elif label.startswith("présence moins"):
                        out_label = label.replace("présence moins", "présence plus", 1)
                    else:
                        out_label = f"ajustement {matched_alias}"
                else:
                    out_label = label
                adjust(field, effective, out_label)

    def observe_user_message(self, text: str, *, private: bool = False) -> list[str]:
        """Learn only from explicit style feedback; return human-readable changes.

        Normal conversation increments the interaction counter but does not cause
        silent personality drift. Private mode deliberately persists nothing.
        """
        if private:
            return []
        message = self._normalize_spaces(text)
        if not message:
            return []

        self.db.set_preference(self.KEY_INTERACTIONS, str(self.interactions + 1))
        style = self.style()
        values = asdict(style)
        changes: list[str] = []

        def adjust(field: str, delta: float, label: str) -> None:
            before = float(values[field])
            after = max(0.0, min(1.0, before + delta))
            if abs(after - before) >= 0.001:
                values[field] = after
                changes.append(label)

        # Explicit feedback only. These patterns intentionally do not infer
        # personality preferences from ordinary sentiment or topic choices.
        if self._RESPONSE_SHORT.search(message):
            adjust("verbosity", -0.12, "réponses plus concises")
        if self._RESPONSE_LONG.search(message):
            adjust("verbosity", +0.12, "réponses plus détaillées")
        if self._WARMER.search(message):
            adjust("warmth", +0.10, "ton plus humain et chaleureux")
        if self._COOLER.search(message):
            adjust("warmth", -0.10, "ton plus réservé/formel")
        if self._MORE_DIRECT.search(message):
            adjust("directness", +0.10, "style plus direct")
        if self._LESS_DIRECT.search(message):
            adjust("directness", -0.10, "style plus nuancé")
        if self._MORE_EMOJI.search(message):
            adjust("emoji_affinity", +0.15, "davantage d'emojis")
        if self._LESS_EMOJI.search(message):
            adjust("emoji_affinity", -0.20, "moins d'emojis")
        if self._MORE_PROACTIVE.search(message):
            adjust("proactivity", +0.12, "davantage de relances utiles")
        if self._LESS_PROACTIVE.search(message):
            adjust("proactivity", -0.15, "moins de relances/questions")

        self._apply_personality_directive(message, adjust)

        if changes:
            # One explicit instruction is one auditable revision even if it
            # changes several correlated personality axes.
            unique = list(dict.fromkeys(changes))
            summary = ", ".join(unique)
            self._save_style(AdaptiveStyle(**values), summary)
            return unique
        return []

    def reset(self) -> None:
        """Reset personal adaptation without touching immutable identity/security."""
        for key in (
            self.KEY_STYLE,
            self.KEY_REVISION,
            self.KEY_FEEDBACK,
            self.KEY_INTERACTIONS,
            self.KEY_LAST_CHANGE,
            self.KEY_LAST_CHANGE_AT,
        ):
            self.db.conn.execute("DELETE FROM preferences WHERE key=?", (key,))
        self.db.conn.commit()

    def render_for_prompt(self, *, private: bool = False, compact: bool = False) -> str:
        if private:
            return (
                "APPRENTISSAGE ADAPTATIF\n"
                "- Mode privé : n'apprends ni ne persiste de nouvelles préférences pendant cette session."
            )
        style = self.style()
        personality_line = (
            f"jeu={style.playfulness:.2f}, sensualité={style.sensuality:.2f}, formalité={style.formality:.2f}, "
            f"expressivité={style.expressiveness:.2f}, spontanéité={style.spontaneity:.2f}"
        )
        if compact:
            return (
                "APPRENTISSAGE ADAPTATIF\n"
                f"- Révision comportementale locale : {self.revision}; retours explicites intégrés : {self.explicit_feedback_count}.\n"
                f"- Style appris : chaleur={style.warmth:.2f}, verbosité={style.verbosity:.2f}, direct={style.directness:.2f}, emojis={style.emoji_affinity:.2f}, proactivité={style.proactivity:.2f}; {personality_line}.\n"
                "- Ces valeurs modulent ta présence conversationnelle de façon contextuelle; elles ne remplacent ni le mode courant ni les règles de sécurité.\n"
                "- Combine les axes au lieu de réciter des phrases fixes : choix des mots, rythme, relances et expressivité doivent refléter le profil.\n"
                "- Spontanéité et formalité sont indépendantes : être plus spontanée ne veut pas dire devenir moins formelle.\n"
                "- Adapte le ton à ces préférences sans inventer de souvenir ni modifier identité, permissions ou sécurité."
            )
        last = f" Dernière évolution : {self.last_change}." if self.last_change else ""
        return (
            "APPRENTISSAGE / EVOLUTION CONTROLEE\n"
            f"- Interactions observées : {self.interactions}; retours explicites intégrés : {self.explicit_feedback_count}; révision : {self.revision}.{last}\n"
            f"- Profil appris : chaleur={style.warmth:.2f}; verbosité={style.verbosity:.2f}; direct={style.directness:.2f}; affinité emojis={style.emoji_affinity:.2f}; proactivité={style.proactivity:.2f}; {personality_line}.\n"
            "- Tu apprends progressivement des préférences explicites, des corrections et des souvenirs autorisés.\n"
            "- Hiérarchie de ton : sécurité et contexte sérieux > mode courant > relation > personnalité apprise.\n"
            "- Sensualité, jeu, expressivité et spontanéité restent contextuels : exprime-les surtout par le rythme et le choix des mots, et réduis-les automatiquement en mode sérieux/professionnel.\n"
            "- Spontanéité et formalité sont deux axes indépendants : une réponse peut être spontanée tout en restant formelle.\n"
            "- Ne nomme pas tes traits à chaque réponse : fais-les sentir naturellement, sans caricature.\n"
            "- Tu peux faire évoluer ton comportement conversationnel, mais tu ne réécris jamais seule ton code, ton identité centrale, tes permissions ou les règles de sécurité.\n"
            "- Une évolution technique profonde doit rester versionnée, testée et approuvée hors de la conversation."
        )

    def dialogue_kwargs(self) -> dict[str, float | int | str]:
        style = self.style()
        return {
            "learning_revision": self.revision,
            "learned_preferences": self.explicit_feedback_count,
            "learning_interactions": self.interactions,
            "last_learning_change": self.last_change,
            "warmth": style.warmth,
            "verbosity": style.verbosity,
            "directness": style.directness,
            "emoji_affinity": style.emoji_affinity,
            "proactivity": style.proactivity,
            "playfulness": style.playfulness,
            "sensuality": style.sensuality,
            "formality": style.formality,
            "expressiveness": style.expressiveness,
            "spontaneity": style.spontaneity,
        }

    def acknowledgement(self, changes: list[str] | tuple[str, ...]) -> str:
        """Build a short local acknowledgement after an explicit adaptation."""
        clean = [str(item or "").strip() for item in changes if str(item or "").strip()]
        clean = list(dict.fromkeys(clean))
        if not clean:
            return ""
        if len(clean) == 1:
            return f"Compris. Je m'adapte : {clean[0]}."
        return "Compris. Je m'adapte : " + ", ".join(clean[:-1]) + f" et {clean[-1]}."


__all__ = ["AdaptiveLearningEngine", "AdaptiveStyle"]
