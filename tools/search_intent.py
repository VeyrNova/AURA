"""Deterministic search/visual-intent parsing for AURA v0.7.2 / Patch 26.6.

This module is intentionally LLM-free. It is shared by the Internet planner and
presentation layer so an explicit search request cannot be interpreted one way
for tools and another way for the UI.
"""
from __future__ import annotations

import re
import unicodedata


_DIRECT_SEARCH_RE = re.compile(
    r"^(?:aura[,\s:]*)?"
    r"(?P<verb>cherche|recherche|trouve|verifie|vérifie|regarde)"
    r"(?:[-\s]+moi)?"
    r"(?:\s+(?:sur\s+)?(?:internet|le\s+web|web|en\s+ligne))?"
    r"\s*[:,-]?\s*(?P<query>.+?)\s*$",
    re.IGNORECASE,
)

# Patch 26.6 — natural research language lock.  These patterns are deliberately
# deterministic and limited to explicit user instructions to search/research.
# They must not turn ordinary factual questions into Web searches.
_NATURAL_SEARCH_RES = (
    re.compile(
        r"^(?:aura[,\s:]*)?"
        r"fais(?:[-\s]+moi)?\s+(?:une|des)\s+recherches?"
        r"\s*[:,-]?\s*(?P<query>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:aura[,\s:]*)?"
        r"(?:peux[-\s]+tu|pourrais[-\s]+tu|tu\s+peux|tu\s+pourrais|"
        r"est[-\s]+ce\s+que\s+tu\s+peux|est[-\s]+ce\s+que\s+tu\s+pourrais)\s+"
        r"(?:me\s+)?(?:"
        r"(?:faire|lancer|effectuer)\s+(?:moi\s+)?(?:une|des)\s+recherches?|"
        r"chercher|rechercher|trouver|verifier|vérifier|regarder"
        r")\s*[:,-]?\s*(?P<query>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:aura[,\s:]*)?"
        r"(?:va|vas)\s+(?:chercher|rechercher|verifier|vérifier|regarder)"
        r"\s*[:,-]?\s*(?P<query>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:aura[,\s:]*)?"
        r"(?:je\s+veux|je\s+voudrais|j['’]aimerais|je\s+souhaiterais)\s+que\s+tu\s+"
        r"(?:cherches|recherches|trouves|verifies|vérifies|regardes)"
        r"\s*[:,-]?\s*(?P<query>.+?)\s*$",
        re.IGNORECASE,
    ),
)

_SEARCH_QUERY_PREFIX_RE = re.compile(
    r"^(?:(?:sur|dans)\s+(?:internet|le\s+web|web|internet|en\s+ligne)\s*[:,-]?\s*|"
    r"(?:sur|à\s+propos\s+de|au\s+sujet\s+de)\s+)",
    re.IGNORECASE,
)


_VISUAL_LIST_RE = re.compile(
    r"\b(?:compare(?:-moi)?|comparatif|liste(?:-moi)?|top|options?|alternatives?|"
    r"avantages?\s+et\s+inconv[eé]nients?|plusieurs\s+r[eé]sultats?)\b",
    re.IGNORECASE,
)

# RC3: explicit screen-oriented structured requests must not be squeezed into
# the short voice budget. Example: ``affiche la discographie de Deftones``.
_VISUAL_STRUCTURED_DISPLAY_RE = re.compile(
    r"\b(?:affiche|montre|présente|presente)\b.{0,80}\b(?:discographie|chronologie|liste|tableau|"
    r"classement|albums?|titres?|résultats?|resultats?|historique)\b",
    re.IGNORECASE,
)

_COUNT_RE = re.compile(r"\b(?P<count>[2-9]|1[0-9]|20)\b")

_VISUAL_EXTERNAL_RE = re.compile(
    r"\b(?:destinations?|lieux?|endroits?|restaurants?|h[oô]tels?|plages?|mus[eé]es?|"
    r"activit[eé]s?|sorties?|visites?|adresses?|magasins?|boutiques?|produits?|mod[eè]les?|"
    r"prix|tarifs?|voyages?|s[eé]jours?|campings?|bars?|caf[eé]s?|parcs?|attractions?)\b",
    re.IGNORECASE,
)

_VISUAL_EXTERNAL_CONTEXT_RE = re.compile(
    r"\b(?:[aà]\s+visiter|autour\s+de|pr[eè]s\s+de|proche\s+de|dans\s+les\s+environs|"
    r"meilleurs?|meilleures?|o[uù]\s+aller|o[uù]\s+manger|o[uù]\s+dormir|comparatif|compare(?:-moi)?|"
    r"disponibles?|acheter|r[eé]server)\b",
    re.IGNORECASE,
)

_COMPLEX_VISUAL_RE = re.compile(
    r"\b(?:analyse\s+approfondie|analyse\s+d[eé]taill[eé]e|rapport\s+complet|"
    r"strat[eé]gie\s+d[eé]taill[eé]e|raisonnement\s+approfondi|en\s+profondeur)\b",
    re.IGNORECASE,
)


def normalize_search_text(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.casefold().replace("’", "'")
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def extract_explicit_search_query(text: str) -> str | None:
    """Return the query only when the user explicitly instructs AURA to research.

    Patch 26.6 makes this parser the hard boundary between conversation and the
    configured research engine. Natural forms such as "fais des recherches",
    "peux-tu faire une recherche" and "va chercher" are equivalent to the
    historical "recherche-moi" command.
    """
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return None

    match = _DIRECT_SEARCH_RE.match(clean)
    if match is None:
        for pattern in _NATURAL_SEARCH_RES:
            match = pattern.match(clean)
            if match is not None:
                break
    if match is None:
        return None

    query = (match.group("query") or "").strip().strip(" .?!")
    # Natural forms commonly add "sur" after "faire une recherche". Strip
    # only the syntactic research prefix; keep the substantive query untouched.
    previous = None
    while query and query != previous:
        previous = query
        query = _SEARCH_QUERY_PREFIX_RE.sub("", query, count=1).strip().strip(" .?!")
    return query or None


def is_explicit_search_request(text: str) -> bool:
    return extract_explicit_search_query(text) is not None


_DOCUMENT_SCOPE_RE = re.compile(
    r"\b(?:ce|cet|cette|le|la|du|dans\s+le|dans\s+la|dans\s+ce|dans\s+cette)\s+"
    r"(?:document|fichier|pdf|facture|pi[eè]ce\s+jointe)\b|"
    r"\b(?:présent(?:e|es|s)?|figure(?:nt)?|indiqu[ée]s?|mentionn[ée]s?|contenu(?:e|es|s)?)\s+"
    r"(?:dans|sur)\s+(?:ce|cet|cette|le|la)\s+(?:document|fichier|pdf|facture)\b|"
    r"\b(?:cherche|recherche|trouve|vérifie|verifie)\s+(?:uniquement\s+)?dans\s+"
    r"(?:ce|cet|cette|le|la)\s+(?:document|fichier|pdf|facture)\b",
    re.IGNORECASE,
)

_EXPLICIT_WEB_CHANNEL_RE = re.compile(
    r"\b(?:sur\s+internet|sur\s+le\s+web|dans\s+le\s+web|en\s+ligne|"
    r"recherche\s+web|recherche\s+internet|sources?\s+web)\b",
    re.IGNORECASE,
)


def is_document_scoped_request(text: str) -> bool:
    """True when the request explicitly targets the currently attached document."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    return bool(clean and _DOCUMENT_SCOPE_RE.search(clean))


def should_route_explicit_search_to_web(text: str, *, has_active_document: bool = False) -> bool:
    """Resolve explicit-search wording when a document is attached.

    P0.6.2.4.1: words such as "recherche" or "cherche" do not automatically
    mean Internet when the same sentence explicitly says "dans ce document",
    "présents dans le document", etc. An explicit Web/Internet channel still
    wins when the user actually asks for it.
    """
    if not is_explicit_search_request(text):
        return False
    if not has_active_document:
        return True
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if _EXPLICIT_WEB_CHANNEL_RE.search(clean):
        return True
    return not is_document_scoped_request(clean)


def requested_result_count(text: str, *, default: int = 0, maximum: int = 8) -> int:
    """Extract a small requested list size such as '5 destinations'."""
    query = extract_explicit_search_query(text) or (text or "")
    match = _COUNT_RE.search(query)
    if match is None:
        return max(0, min(int(default), int(maximum)))
    return max(1, min(int(match.group("count")), int(maximum)))


def is_visual_request(text: str) -> bool:
    """Return True when the answer is better presented as a visual result surface."""
    if is_explicit_search_request(text):
        return True
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return False
    if _VISUAL_LIST_RE.search(clean):
        return True
    if _VISUAL_STRUCTURED_DISPLAY_RE.search(clean):
        return True
    # A requested multi-item answer is visual by default when it is clearly a
    # list-like task. Avoid treating ordinary years/numbers as visual intent.
    count = requested_result_count(clean, default=0)
    if count >= 3 and re.search(
        r"\b(?:destinations?|id[eé]es?|choix|solutions?|exemples?|lieux?|restaurants?|"
        r"h[oô]tels?|produits?|mod[eè]les?|raisons?|conseils?|points?)\b",
        clean,
        re.IGNORECASE,
    ):
        return True
    return False

def extract_visual_search_query(text: str) -> str | None:
    """Return a Web-search query for visual requests that require real-world facts.

    This deliberately excludes creative/list-making prompts such as "5 idées de
    chansons". Real places, businesses, products, prices and travel-style lists
    are tool-first because the local LLM must not invent them.
    """
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean or not is_visual_request(clean):
        return None
    if is_explicit_search_request(clean):
        return extract_explicit_search_query(clean)
    if not _VISUAL_EXTERNAL_RE.search(clean):
        return None
    if not (_VISUAL_EXTERNAL_CONTEXT_RE.search(clean) or requested_result_count(clean, default=0) >= 3):
        return None
    # Search engines handle natural-language queries well; only remove the AURA
    # wake prefix so the provider receives the actual task.
    query = re.sub(r"^(?:aura[,\s:]*)", "", clean, flags=re.IGNORECASE).strip(" .?!")
    return query or None


def is_structured_visual_request(text: str) -> bool:
    """True for screen-oriented structured/list displays such as discographies."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    return bool(clean and _VISUAL_STRUCTURED_DISPLAY_RE.search(clean))


def is_complex_visual_analysis(text: str) -> bool:
    """True only when the user explicitly asks for heavyweight local analysis."""
    return bool(_COMPLEX_VISUAL_RE.search(text or ""))

