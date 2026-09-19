"""Deterministic geographic entity normalization for AURA.

The resolver is deliberately lightweight: it does not replace Open-Meteo's
online geocoder.  It normalizes human variants/aliases before controlled tools
send a query, while keeping an auditable canonical label for the UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
import re
import unicodedata


@dataclass(frozen=True)
class GeoEntity:
    raw: str
    canonical: str
    kind: str = "place"
    country: str = ""
    confidence: float = 0.60
    matched_alias: bool = False


def _key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").replace("’", "'"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("-", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# High-value aliases are intentionally explicit. Unknown cities still benefit
# from separator/case normalization and are then resolved by Open-Meteo.
_ALIAS_ROWS = (
    ("New York", "city", "États-Unis", ("new york", "new-york", "newyork", "nyc", "new york city")),
    ("Los Angeles", "city", "États-Unis", ("los angeles", "los-angeles", "la")),
    ("San Francisco", "city", "États-Unis", ("san francisco", "san-francisco", "sf")),
    ("Washington", "city", "États-Unis", ("washington dc", "washington d c", "washington")),
    ("Londres", "city", "Royaume-Uni", ("londres", "london")),
    ("Rome", "city", "Italie", ("rome", "roma")),
    ("Munich", "city", "Allemagne", ("munich", "munchen", "muenchen")),
    ("Pékin", "city", "Chine", ("pekin", "pékin", "beijing")),
    ("Tokyo", "city", "Japon", ("tokyo",)),
    ("Provence-Alpes-Côte d'Azur", "region", "France", ("paca", "region paca", "provence alpes cote d azur", "provence-alpes-cote-d-azur")),
    ("Île-de-France", "region", "France", ("ile de france", "île-de-france", "idf", "region parisienne")),
    ("Auvergne-Rhône-Alpes", "region", "France", ("auvergne rhone alpes", "aura region", "ara")),
    ("Bourgogne-Franche-Comté", "region", "France", ("bourgogne franche comte", "bfc")),
    ("Nouvelle-Aquitaine", "region", "France", ("nouvelle aquitaine",)),
    ("Occitanie", "region", "France", ("occitanie",)),
    ("Hauts-de-France", "region", "France", ("hauts de france",)),
    ("Grand Est", "region", "France", ("grand est",)),
    ("Normandie", "region", "France", ("normandie",)),
    ("Bretagne", "region", "France", ("bretagne",)),
    ("Pays de la Loire", "region", "France", ("pays de la loire",)),
    ("Centre-Val de Loire", "region", "France", ("centre val de loire",)),
    ("Corse", "region", "France", ("corse",)),
    ("États-Unis", "country", "", ("etats unis", "états-unis", "usa", "us", "united states", "united states of america")),
    ("Royaume-Uni", "country", "", ("royaume uni", "uk", "united kingdom", "grande bretagne")),
    ("Émirats arabes unis", "country", "", ("emirats arabes unis", "eau", "uae")),
    ("Pays-Bas", "country", "", ("pays bas", "netherlands", "hollande")),
)

_ALIAS_MAP: dict[str, tuple[str, str, str]] = {}
for canonical, kind, country, aliases in _ALIAS_ROWS:
    _ALIAS_MAP[_key(canonical)] = (canonical, kind, country)
    for alias in aliases:
        _ALIAS_MAP[_key(alias)] = (canonical, kind, country)


def _smart_title(raw: str) -> str:
    value = re.sub(r"[-_]+", " ", str(raw or "").strip())
    value = re.sub(r"\s+", " ", value)
    if not value:
        return ""
    small = {"de", "du", "des", "la", "le", "les", "sur", "sous", "en", "et", "d'"}
    words = []
    for i, word in enumerate(value.split(" ")):
        low = word.casefold()
        if i and low in small:
            words.append(low)
        elif "'" in word:
            head, tail = word.split("'", 1)
            words.append(head.capitalize() + "'" + tail.capitalize())
        else:
            words.append(word.capitalize())
    return " ".join(words)


def resolve_geo_entity(value: str, *, fuzzy: bool = True) -> GeoEntity:
    raw = str(value or "").strip(" ,.?!\t\r\n")
    key = _key(raw)
    if not key:
        return GeoEntity(raw=raw, canonical="", confidence=0.0)
    exact = _ALIAS_MAP.get(key)
    if exact:
        canonical, kind, country = exact
        return GeoEntity(raw, canonical, kind, country, 1.0, True)
    if fuzzy and len(key) >= 5:
        matches = get_close_matches(key, _ALIAS_MAP.keys(), n=1, cutoff=0.90)
        if matches:
            canonical, kind, country = _ALIAS_MAP[matches[0]]
            return GeoEntity(raw, canonical, kind, country, 0.91, True)
    return GeoEntity(raw, _smart_title(raw), "place", "", 0.60, False)


def canonical_geo_query(value: str) -> str:
    return resolve_geo_entity(value).canonical
