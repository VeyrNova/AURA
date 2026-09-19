"""Safe user-facing error messages."""


def user_safe_error_message(context: str = "operation") -> str:
    messages = {
        "intent": "Je n'ai pas pu terminer cette action. Rien d'autre n'a ete modifie.",
        "llm": "Mon moteur IA a rencontré un problème. Les fonctions locales restent disponibles.",
        "llm_context": "Je n'ai pas réussi à préparer mon contexte de réponse. Mes fonctions locales restent disponibles.",
        "database": "J'ai rencontre un probleme avec les donnees locales.",
    }
    return messages.get(context, "Une erreur interne est survenue.")
