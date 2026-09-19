"""Deterministic factual-grounding guard for AURA v0.7.0.

The local LLM is not allowed to invent live/public facts that require an
external source.  This module runs before the LLM.  It can answer facts that
are genuinely local (system date/time) and refuses source-dependent real-time
queries while the corresponding capability is unavailable.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GroundingDecision:
    handled: bool
    response: str = ""
    category: str = ""
    source: str = ""


class GroundedIntelligence:
    """Classify requests that must not be answered from model intuition alone."""

    _WEATHER = (
        "meteo", "temperature dehors", "temperature exterieure", "quel temps fait il", "quel temps fait-il", "fait il beau",
        "fait-il beau", "va t il pleuvoir", "va-t-il pleuvoir", "pluie aujourd", "pluie demain",
        "neige aujourd", "neige demain", "weather", "forecast",
    )
    _NEWS = (
        "actualites", "actualite du jour", "actualite aujourd", "dernieres actualites",
        "dernieres nouvelles", "derniere nouvelle", "news aujourd",
        "nouvelles du jour", "ce qui se passe aujourd", "quoi de neuf dans le monde",
    )
    _FINANCE = (
        "cours actuel", "prix actuel", "cours de l action", "cours de l'action", "cours du bitcoin",
        "prix du bitcoin", "cours btc", "prix btc", "bourse aujourd", "cac 40 aujourd",
        "nasdaq aujourd", "taux de change actuel", "euro dollar aujourd",
    )
    _SPORTS = (
        "score actuel", "score du match", "resultat du match", "resultats du match",
        "classement actuel", "match aujourd", "match ce soir", "score en direct", "live score",
    )
    _TRAFFIC = (
        "trafic actuel", "circulation actuelle", "bouchons maintenant", "bouchons sur la route",
        "y a t il des bouchons", "embouteillages", "trafic maintenant", "circulation maintenant",
    )
    _LOCAL_LIVE = (
        "ouvert maintenant", "ouverte maintenant", "ouvert aujourd", "ferme maintenant",
        "restaurant pres de moi", "restaurant près de moi", "magasin pres de moi", "magasin près de moi",
        "pharmacie de garde", "station service ouverte",
    )
    _WEB_EXPLICIT = (
        "cherche sur internet", "recherche sur internet", "regarde sur internet", "verifie sur internet",
        "vérifie sur internet", "cherche en ligne", "recherche en ligne", "regarde en ligne",
    )

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.casefold().replace("’", "'")
        text = re.sub(r"[^a-z0-9'\s-]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _contains_any(cls, normalized: str, needles: tuple[str, ...]) -> bool:
        normalized_needles = tuple(cls._normalize(item) for item in needles)
        return any(item and item in normalized for item in normalized_needles)

    @staticmethod
    def _internet_available(self_model) -> bool:
        try:
            return bool(self_model.has_capability("internet"))
        except Exception:
            return False

    @staticmethod
    def _local_datetime_answer(normalized: str, now: datetime) -> GroundingDecision | None:
        time_patterns = (
            r"\bquelle heure\b", r"\bil est quelle heure\b", r"\bheure actuelle\b", r"\bheure est il\b",
        )
        date_patterns = (
            r"\bquelle date\b", r"\bquel jour sommes nous\b", r"\bon est quel jour\b",
            r"\bdate d aujourd hui\b", r"\bdate actuelle\b",
        )
        if any(re.search(p, normalized) for p in time_patterns):
            return GroundingDecision(
                True,
                f"Il est {now.strftime('%H:%M')} d'après l'horloge locale de ton PC.",
                "local_time",
                "system_clock",
            )
        if any(re.search(p, normalized) for p in date_patterns):
            weekdays = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
            months = (
                "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                "septembre", "octobre", "novembre", "décembre",
            )
            label = f"{weekdays[now.weekday()]} {now.day} {months[now.month - 1]} {now.year}"
            return GroundingDecision(
                True,
                f"Nous sommes le {label}, d'après la date locale de ton PC.",
                "local_date",
                "system_clock",
            )
        return None

    def evaluate(self, text: str, self_model, *, now: datetime | None = None) -> GroundingDecision:
        normalized = self._normalize(text)
        if not normalized:
            return GroundingDecision(False)

        local = self._local_datetime_answer(normalized, (now or datetime.now().astimezone()))
        if local is not None:
            return local

        # v0.7.0 tools are planned before this guard. Reaching this point means
        # no dedicated source-backed tool accepted the request, so live facts
        # must still fail closed even though controlled Internet capability exists.
        categories = (
            ("weather", self._WEATHER, "Je n'ai pas encore accès aux données météo en temps réel. Je préfère ne pas inventer une température ou des conditions actuelles."),
            ("news", self._NEWS, "Je n'ai pas encore accès aux actualités en temps réel. Je préfère ne pas te donner de nouvelles non vérifiées."),
            ("finance", self._FINANCE, "Je n'ai pas encore accès aux cours financiers en temps réel. Je préfère ne pas inventer un prix ou un taux actuel."),
            ("sports", self._SPORTS, "Je n'ai pas encore accès aux scores et classements en temps réel. Je préfère ne pas inventer un résultat."),
            ("traffic", self._TRAFFIC, "Je n'ai pas encore accès au trafic en temps réel. Je préfère ne pas inventer l'état de la circulation."),
            ("local_live", self._LOCAL_LIVE, "Je n'ai pas encore accès aux informations locales en temps réel ni à ta position. Je ne peux donc pas vérifier cela correctement."),
            ("web", self._WEB_EXPLICIT, "Mon accès Internet général n'est pas encore activé. Je peux raisonner avec mes données locales, mais je ne vais pas prétendre avoir effectué une recherche en ligne."),
        )
        for category, needles, response in categories:
            if self._contains_any(normalized, needles):
                return GroundingDecision(True, response, category, "unavailable_external_source")

        return GroundingDecision(False)
