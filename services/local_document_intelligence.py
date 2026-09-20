"""Local deterministic document intelligence for authorized desktop files.

P0.6.5.3 intentionally performs no LLM call and no network access.
It consumes a locally extracted DocumentContext and returns bounded,
extractive results only.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from services.document_analysis import DocumentContext, select_document_context


class LocalDocumentIntelligenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalDocumentResult:
    mode: str
    query: str
    text: str
    matches: int
    source_chars: int
    result_chars: int
    extractive: bool = True
    local_only: bool = True


_STOPWORDS = frozenset({
    "alors","avec","avoir","cela","celle","celles","celui","ceux","comme","dans",
    "des","elle","elles","entre","être","fait","faire","fois","ils","leur","leurs",
    "mais","nous","pour","sans","ses","sont","sur","une","vous","plus","tout",
    "tous","toute","toutes","aux","ces","cet","cette","qui","que","quoi","dont",
    "par","pas","est","les","du","de","la","le","un","et","ou","où","au","en",
    "the","and","for","with","this","that","from","into","are","was","were","have",
    "has","not","but","you","your","our","its","can","will","about",
})


def _words(text: str) -> list[str]:
    return [
        token.casefold()
        for token in re.findall(r"[A-Za-zÀ-ÿ0-9_'-]{3,}", str(text or ""))
        if token.casefold() not in _STOPWORDS
    ]


def _sentences(text: str) -> list[str]:
    clean = re.sub(r"\r\n?", "\n", str(text or ""))
    clean = re.sub(r"[ \t]+", " ", clean)
    chunks = re.split(r"(?<=[.!?])\s+|\n{1,}", clean)
    out = []
    for chunk in chunks:
        value = chunk.strip(" \t\r\n•*-")
        if 20 <= len(value) <= 900:
            out.append(value)
    return out


def _extractive_summary(text: str, *, max_chars: int = 1800) -> str:
    sentences = _sentences(text)
    if not sentences:
        value = str(text or "").strip()
        return value[:max_chars] if value else "(Document vide.)"

    frequencies = Counter(_words(text))
    if not frequencies:
        return "\n".join(sentences[:6])[:max_chars]

    max_freq = max(frequencies.values()) or 1
    scored = []
    total = max(1, len(sentences))
    for idx, sentence in enumerate(sentences):
        tokens = _words(sentence)
        if not tokens:
            continue
        lexical = sum(frequencies[t] / max_freq for t in tokens) / max(1, len(tokens))
        position = 0.18 if idx < max(2, total // 8) else 0.0
        ending = 0.08 if idx >= max(0, total - 2) else 0.0
        heading = 0.12 if len(sentence) < 90 else 0.0
        scored.append((lexical + position + ending + heading, idx, sentence))

    chosen = sorted(scored, key=lambda item: (item[0], -item[1]), reverse=True)[:7]
    chosen.sort(key=lambda item: item[1])
    parts, used = [], 0
    for _score, _idx, sentence in chosen:
        if used + len(sentence) + 2 > max_chars and parts:
            continue
        parts.append(sentence)
        used += len(sentence) + 2
    return "\n".join(f"• {s}" for s in parts)[:max_chars]


def _search_snippets(text: str, query: str, *, max_chars: int = 2200) -> tuple[str, int]:
    query_words = list(dict.fromkeys(_words(query)))[:10]
    if not query_words:
        raise LocalDocumentIntelligenceError("La recherche locale nécessite un terme précis.")

    source = str(text or "")
    low = source.casefold()
    windows = []
    for word in query_words:
        start = 0
        while True:
            pos = low.find(word, start)
            if pos < 0:
                break
            left = max(0, pos - 170)
            right = min(len(source), pos + len(word) + 260)
            snippet = re.sub(r"\s+", " ", source[left:right]).strip()
            score = sum(snippet.casefold().count(w) for w in query_words)
            windows.append((score, left, snippet))
            start = pos + max(1, len(word))
            if len(windows) >= 80:
                break
        if len(windows) >= 80:
            break

    if not windows:
        return "Aucune occurrence pertinente trouvée dans le contenu local.", 0

    unique = {}
    for score, pos, snippet in windows:
        key = snippet.casefold()
        if key not in unique or score > unique[key][0]:
            unique[key] = (score, pos, snippet)
    ranked = sorted(unique.values(), key=lambda item: (item[0], -item[1]), reverse=True)

    parts, used = [], 0
    for score, pos, snippet in ranked[:10]:
        block = f"• …{snippet}…"
        if used + len(block) + 2 > max_chars and parts:
            break
        parts.append(block)
        used += len(block) + 2
    return "\n".join(parts)[:max_chars], len(ranked)


def _contextual_extract(document: DocumentContext, query: str, *, max_chars: int = 2600) -> str:
    if not str(query or "").strip():
        raise LocalDocumentIntelligenceError("La question contextuelle est vide.")
    selected = select_document_context(document, query=query, max_chars=max_chars)
    text = str(selected.text or "").strip()
    if not text:
        return "Aucun passage textuel pertinent n'est disponible localement."
    return (
        "Passages locaux les plus pertinents (réponse extractive, sans LLM) :\n\n"
        + text[:max_chars]
    )


def analyze_local_document(
    document: DocumentContext,
    *,
    mode: str,
    query: str = "",
) -> LocalDocumentResult:
    mode = str(mode or "").strip().casefold()
    query = str(query or "").strip()
    if document.native_required:
        raise LocalDocumentIntelligenceError(
            "Ce document nécessite la lane Document native ; aucun upload cloud n'est effectué ici."
        )

    source = str(document.text or "")
    if not source:
        return LocalDocumentResult(
            mode=mode,
            query=query,
            text="(Document vide.)",
            matches=0,
            source_chars=0,
            result_chars=len("(Document vide.)"),
        )

    if mode == "summary":
        result = _extractive_summary(source)
        matches = 0
    elif mode == "search":
        result, matches = _search_snippets(source, query)
    elif mode == "context":
        result = _contextual_extract(document, query)
        matches = 0
    else:
        raise LocalDocumentIntelligenceError("Mode d'analyse locale non pris en charge.")

    return LocalDocumentResult(
        mode=mode,
        query=query,
        text=result,
        matches=matches,
        source_chars=len(source),
        result_chars=len(result),
    )
