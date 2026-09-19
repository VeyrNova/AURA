"""Grounded definition/reference tool for AURA v0.7.0.9.

Direct definition requests should not be answered by the small conversational
voice model from memory alone. This tool first serves a tiny audited local core
reference for foundational science terms, then (when enabled) queries the fixed
French Wikipedia MediaWiki endpoint and returns a short extract without asking
an LLM to rewrite it.

The network destination is fixed in code; user text is only encoded as a query
parameter. No arbitrary URL is accepted here.
"""
from __future__ import annotations

import re
import unicodedata
import urllib.parse
from dataclasses import dataclass
from datetime import datetime

from tools.models import ToolResult, ToolSource
from tools.safe_http import SafeHTTPClient, SafeHTTPError


WIKIPEDIA_API = "https://fr.wikipedia.org/w/api.php"


@dataclass(frozen=True)
class LocalKnowledgeCard:
    key: str
    aliases: tuple[str, ...]
    sentences: tuple[str, ...]


# Small, deliberately conservative offline core. It is not intended to become a
# general encyclopedia. The web-backed reference path handles other direct
# definitions when controlled Internet is available.
_LOCAL_CARDS: tuple[LocalKnowledgeCard, ...] = (
    LocalKnowledgeCard(
        "neutron",
        ("neutron", "neutrons"),
        (
            "Un neutron est une particule subatomique sans charge électrique.",
            "Il se trouve dans le noyau de la plupart des atomes, aux côtés des protons.",
            "Sa masse est légèrement supérieure à celle d'un proton.",
        ),
    ),
    LocalKnowledgeCard(
        "proton",
        ("proton", "protons"),
        (
            "Un proton est une particule subatomique de charge électrique positive.",
            "Il se trouve dans le noyau atomique.",
            "Sa masse est proche de celle d'un neutron.",
        ),
    ),
    LocalKnowledgeCard(
        "electron",
        ("électron", "electron", "électrons", "electrons"),
        (
            "Un électron est une particule subatomique de charge électrique négative.",
            "Dans un atome, les électrons occupent le nuage électronique autour du noyau.",
            "Leur masse est très inférieure à celle des protons et des neutrons.",
        ),
    ),
    LocalKnowledgeCard(
        "atome",
        ("atome", "atomes"),
        (
            "Un atome est une unité de matière qui conserve les propriétés chimiques d'un élément.",
            "Il possède un noyau contenant au moins un proton et, selon l'isotope, des neutrons.",
            "Des électrons occupent le nuage électronique autour de ce noyau.",
        ),
    ),
    # v0.7.0.15.1: audited fast fact used by the explanation-grounding path.
    # This avoids loading the 8B text brain for a foundational science question
    # that can be answered deterministically and safely offline.
    LocalKnowledgeCard(
        "ciel_bleu",
        (
            "ciel bleu", "le ciel est bleu", "pourquoi le ciel est bleu",
            "couleur du ciel", "bleu du ciel",
        ),
        (
            "Le ciel paraît bleu surtout à cause de la diffusion de Rayleigh dans l'atmosphère.",
            "Les molécules de l'air diffusent davantage les courtes longueurs d'onde de la lumière visible, notamment le bleu, que les longues longueurs d'onde comme le rouge.",
        ),
    ),
)


_DEFINITION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bce\s+qu['’]est\s+(?:un|une|le|la|l['’])?\s*(.+?)[?.!]*$", re.IGNORECASE),
    re.compile(r"\bqu['’]est[- ]ce\s+qu['’](?:un|une)\s+(.+?)[?.!]*$", re.IGNORECASE),
    re.compile(r"\bc['’]est\s+quoi\s+(?:un|une|le|la|l['’])?\s*(.+?)[?.!]*$", re.IGNORECASE),
    re.compile(r"\b(?:définis|definis)\s+(?:moi\s+)?(?:un|une|le|la|l['’])?\s*(.+?)[?.!]*$", re.IGNORECASE),
    re.compile(r"\b(?:définition|definition)\s+(?:de|du|d['’])\s*(.+?)[?.!]*$", re.IGNORECASE),
)

_REJECT_SUBJECT = re.compile(
    r"https?://|\b(?:aujourd['’]hui|maintenant|actuellement|météo|meteo|prix|cours|trafic|score|horaire)\b",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9'\-\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_definition_subject(text: str) -> str:
    """Return a concise subject only for explicit direct-definition wording."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean or _REJECT_SUBJECT.search(clean):
        return ""
    for pattern in _DEFINITION_PATTERNS:
        match = pattern.search(clean)
        if not match:
            continue
        subject = match.group(1).strip().strip(" \t\r\n.,;:!?\"'“”«»")
        subject = re.sub(r"^(?:un|une|le|la|les|l['’])\s+", "", subject, flags=re.IGNORECASE)
        subject = re.sub(r"\s+(?:simplement|rapidement)$", "", subject, flags=re.IGNORECASE)
        if 1 <= len(subject) <= 80 and 1 <= len(subject.split()) <= 10:
            return subject
    return ""


_EXPLANATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*pourquoi\s+(.+?)[?.!]*$", re.IGNORECASE),
    re.compile(r"^\s*comment\s+(?:fonctionne|marche)\s+(.+?)[?.!]*$", re.IGNORECASE),
    re.compile(r"^\s*(?:explique|expliques|explique-moi|expliques-moi)\s+(?:pourquoi\s+)?(.+?)[?.!]*$", re.IGNORECASE),
)

_EXPLANATION_PERSONAL = re.compile(
    r"\b(?:aura|tu|toi|ton|ta|tes|mon|ma|mes|notre|nos|moi|nous)\b",
    re.IGNORECASE,
)


def extract_explanation_subject(text: str) -> str:
    """Extract a conservative encyclopedia-style explanation query.

    Personal/conversational "pourquoi" questions are deliberately excluded so
    they remain on the conversational brain. Public knowledge explanations are
    handled by the audited local/Wikipedia reference path before any LLM load.
    """
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean or _REJECT_SUBJECT.search(clean) or _EXPLANATION_PERSONAL.search(clean):
        return ""
    for pattern in _EXPLANATION_PATTERNS:
        match = pattern.search(clean)
        if not match:
            continue
        subject = match.group(1).strip().strip(" \t\r\n.,;:!?\"'“”«»")
        if 2 <= len(subject) <= 120 and 1 <= len(subject.split()) <= 16:
            # Prefer the audited alias for the startup science regression.
            folded = _fold(subject)
            if folded in {"le ciel est bleu", "ciel est bleu", "le ciel bleu", "ciel bleu"}:
                return "le ciel est bleu"
            return subject
    return ""


def local_reference(subject: str) -> tuple[str, ...] | None:
    folded = _fold(subject)
    if not folded:
        return None
    for card in _LOCAL_CARDS:
        if folded in {_fold(alias) for alias in card.aliases}:
            return card.sentences
    return None


def _split_sentences(text: str) -> tuple[str, ...]:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return ()
    parts = re.findall(r".+?(?:[.!?…](?=\s|$)|$)", clean)
    return tuple(part.strip() for part in parts if part.strip())


def _concise_extract(text: str, *, max_sentences: int, max_chars: int) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    chosen: list[str] = []
    for sentence in sentences:
        if len(chosen) >= max(1, int(max_sentences)):
            break
        candidate = " ".join(chosen + [sentence]).strip()
        if chosen and len(candidate) > max(120, int(max_chars)):
            break
        chosen.append(sentence)
    return " ".join(chosen).strip()


class KnowledgeReferenceTool:
    def __init__(self, client: SafeHTTPClient, *, max_sentences: int = 3, max_chars: int = 420):
        self.client = client
        self.max_sentences = max(1, int(max_sentences))
        self.max_chars = max(180, int(max_chars))

    def execute(self, subject: str, *, allow_web: bool = True) -> ToolResult:
        subject = re.sub(r"\s+", " ", (subject or "").strip())
        if not subject:
            return ToolResult(False, "Je n'ai pas identifié le terme à définir.", "knowledge_reference", "missing_subject")

        card = local_reference(subject)
        if card:
            response = " ".join(card)
            return ToolResult(True, response, "knowledge_reference", "aura-local-reference")

        if not allow_web:
            return ToolResult(
                False,
                f"Je n'ai pas de référence locale fiable pour définir « {subject} » et la vérification en ligne est désactivée. Je préfère ne pas inventer.",
                "knowledge_reference",
                "knowledge_unverified",
            )

        query = urllib.parse.urlencode(
            {
                "action": "query",
                "generator": "search",
                "gsrsearch": subject,
                "gsrlimit": "1",
                "prop": "extracts",
                "exintro": "1",
                "explaintext": "1",
                "redirects": "1",
                "format": "json",
                "formatversion": "2",
            }
        )
        url = f"{WIKIPEDIA_API}?{query}"
        try:
            payload, _response = self.client.get_json(
                url,
                headers={"Accept-Language": "fr-FR,fr;q=0.9"},
            )
            pages = ((payload.get("query") or {}).get("pages") or [])
            if not pages:
                raise SafeHTTPError("Aucun article de référence trouvé.")
            page = pages[0] if isinstance(pages[0], dict) else {}
            title = str(page.get("title") or subject).strip()
            extract = str(page.get("extract") or "").strip()
            concise = _concise_extract(
                extract,
                max_sentences=self.max_sentences,
                max_chars=self.max_chars,
            )
            if not concise:
                raise SafeHTTPError("La source n'a pas fourni de définition exploitable.")
            source_url = "https://fr.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe="_()'-")
            spoken = f"{concise} Source : Wikipédia en français."
            return ToolResult(
                True,
                spoken,
                "knowledge_reference",
                "wikipedia-fr",
                sources=(ToolSource("Wikipédia", "fr.wikipedia.org", datetime.now().astimezone().isoformat(timespec="minutes"), source_url),),
            )
        except SafeHTTPError:
            return ToolResult(
                False,
                f"Je n'ai pas pu vérifier une définition fiable de « {subject} ». Je préfère ne pas l'inventer.",
                "knowledge_reference",
                "knowledge_reference_error",
            )
