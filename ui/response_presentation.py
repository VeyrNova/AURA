"""Smart Speech / Visual Result Handoff policy for AURA v0.7.0.15.6.3."""
from __future__ import annotations

from dataclasses import dataclass

from config.settings import settings
from tools.search_intent import is_visual_request, requested_result_count


@dataclass(frozen=True)
class PresentationDecision:
    visual: bool
    title: str = ""
    subtitle: str = ""
    speech: str = ""


def for_user_request(user_text: str, *, visual_context_active: bool = False) -> PresentationDecision:
    """Pre-classify an input before generation so presentation is not length-driven."""
    if not settings.VISUAL_RESULT_HANDOFF_ENABLED or not settings.VISUAL_RESULT_INTENT_ENABLED:
        return PresentationDecision(False)
    from ai.visual_followup import is_visual_followup_request
    if not is_visual_request(user_text) and not (visual_context_active and is_visual_followup_request(user_text)):
        return PresentationDecision(False)
    count = requested_result_count(user_text, default=0)
    subtitle = f"{count} résultats demandés" if count >= 2 else "Résultats structurés par AURA"
    return PresentationDecision(
        True,
        "RÉSULTATS",
        subtitle,
        "Je prépare le résultat complet et je te l'affiche à l'écran.",
    )


def for_tool_result(result, plan=None) -> PresentationDecision:
    if not settings.VISUAL_RESULT_HANDOFF_ENABLED:
        return PresentationDecision(False)
    category = str(getattr(result, "category", "") or "").casefold()
    response = str(getattr(result, "response", "") or "")
    query = str(getattr(plan, "args", {}).get("query", "") if plan is not None else "").strip()
    if not getattr(result, "ok", False):
        # An explicit visual search must not silently disappear just because its
        # provider is unavailable. Show a transparent error surface instead of
        # falling through to an invented local-LLM answer.
        if category in {"web_search", "news"} and query:
            return PresentationDecision(
                True,
                "RECHERCHE WEB INDISPONIBLE",
                query,
                "La recherche Web n'est pas disponible. Je t'affiche le diagnostic à l'écran.",
            )
        return PresentationDecision(False)
    expected = int(getattr(result, "expected_items", 0) or 0)
    actual = int(getattr(result, "item_count", 0) or 0)
    complete = bool(getattr(result, "complete", True))

    if category == "knowledge_reference":
        subject = str(getattr(plan, "args", {}).get("subject", "") if plan is not None else "").strip()
        return PresentationDecision(
            True,
            "AURA // INFORMATIONS",
            subject or "Fiche de connaissance vérifiée",
            "J'ai trouvé les informations. Je te les affiche à l'écran.",
        )

    if category == "agent":
        actual = int(getattr(result, "item_count", 0) or 0)
        complete = bool(getattr(result, "complete", True))
        subtitle = f"{actual} étapes · Agent Kernel" if actual else "Agent Kernel"
        speech = (
            "Le plan multi-étapes est terminé. Je te l'affiche à l'écran."
            if complete else
            "Le plan est partiellement terminé. Je t'affiche les résultats disponibles."
        )
        return PresentationDecision(True, "PLAN AURA", subtitle, speech)

    if category in {"web_search", "news"}:
        if expected and complete:
            subtitle = f"{actual} résultats vérifiés · {query}" if query else f"{actual} résultats vérifiés"
            speech = f"J'ai trouvé les {actual} résultats demandés. Je te les affiche à l'écran."
        elif expected and not complete:
            subtitle = f"{actual}/{expected} résultats vérifiés · {query}" if query else f"{actual}/{expected} résultats vérifiés"
            speech = f"J'ai trouvé {actual} résultats fiables sur les {expected} demandés. Je te les affiche."
        else:
            subtitle = query or "Sources vérifiées par AURA"
            speech = "J'ai trouvé plusieurs résultats intéressants. Je te les affiche à l'écran."
        return PresentationDecision(True, "RÉSULTATS DE RECHERCHE", subtitle, speech)

    if category == "web_fetch" and len(response) >= settings.VISUAL_RESULT_TOOL_MIN_CHARS:
        return PresentationDecision(
            True,
            "LECTURE WEB",
            "Contenu vérifié et affiché dans l'interface",
            "J'ai lu la page. Je t'affiche les éléments utiles à l'écran.",
        )
    if len(response) >= settings.VISUAL_RESULT_LONG_TOOL_CHARS:
        return PresentationDecision(
            True,
            "RÉSULTAT DÉTAILLÉ",
            "AURA · Visual Result Handoff",
            "Il y a pas mal d'informations. Je te les affiche à l'écran.",
        )
    return PresentationDecision(False)


def for_llm_reply(reply: str, user_text: str = "", *, force_visual: bool = False) -> PresentationDecision:
    if not settings.VISUAL_RESULT_HANDOFF_ENABLED:
        return PresentationDecision(False)
    text = str(reply or "").strip()
    intent_visual = bool(force_visual or (settings.VISUAL_RESULT_INTENT_ENABLED and is_visual_request(user_text)))
    if not intent_visual and len(text) < settings.VISUAL_RESULT_MIN_CHARS:
        return PresentationDecision(False)
    count = requested_result_count(user_text, default=0)
    subtitle = f"{count} éléments demandés · AURA locale" if count >= 2 else "AURA · Analyse locale"
    return PresentationDecision(
        True,
        "RÉPONSE DÉTAILLÉE" if not intent_visual else "RÉSULTAT STRUCTURÉ",
        subtitle,
        "Le résultat est prêt. Je te l'affiche à l'écran.",
    )
