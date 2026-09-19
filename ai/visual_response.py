"""Visual-answer generation contract for AURA v0.7.0.15.4."""
from __future__ import annotations

from tools.search_intent import requested_result_count


def visual_output_contract(user_text: str) -> str:
    requested = requested_result_count(user_text, default=0)
    item_line = (
        f"- La demande exige {requested} éléments : produis exactement {requested} éléments complets et distincts."
        if requested >= 2
        else "- Si la demande implique plusieurs éléments, rends la liste complète et structurée."
    )
    return (
        "VISUAL OUTPUT CONTRACT v0.7.0.15.4\n"
        "- Cette réponse est destinée à l'écran, pas à être lue intégralement à voix haute.\n"
        "- Ne raccourcis pas la réponse pour des raisons de TTS ou de concision vocale.\n"
        f"{item_line}\n"
        "- Structure clairement les sections ou éléments et termine la réponse proprement.\n"
        "- N'affirme jamais avoir effectué une recherche Internet si aucune source/outils Web n'a été utilisé."
    )


def apply_visual_output_contract(messages: list[dict[str, str]], user_text: str) -> list[dict[str, str]]:
    result = [dict(message) for message in messages]
    contract = visual_output_contract(user_text)
    for message in result:
        if message.get("role") == "system":
            message["content"] = f"{message.get('content', '').rstrip()}\n\n{contract}"
            return result
    result.insert(0, {"role": "system", "content": contract})
    return result


def apply_visual_followup_context(messages: list[dict[str, str]], previous_result: str) -> list[dict[str, str]]:
    """Pin the previous visual result so a transformation follow-up stays complete."""
    previous = (previous_result or "").strip()[:2600]
    if not previous:
        return [dict(message) for message in messages]
    result = [dict(message) for message in messages]
    context = (
        "CONTEXTE VISUEL PRÉCÉDENT\n"
        "La demande actuelle fait référence au résultat visuel ci-dessous. "
        "Transforme ou complète ce résultat sans revenir au mode de réponse vocale courte.\n\n"
        + previous
    )
    result.insert(1 if result and result[0].get("role") == "system" else 0, {"role": "system", "content": context})
    return result
