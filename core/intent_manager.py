"""
intent_manager.py
Detection d'intentions simples par regles (section 20 du cahier des charges) :
une commande simple ne doit pas forcement passer par le LLM.

Si aucun pattern ne correspond, l'intent retourne est None : le message
sera alors traite comme une conversation generale (CHAT), transmise au LLM.
"""
import re

# Chaque entree associe un intent a un pattern capturant les parametres utiles.
_PATTERNS = [
    ("CREATE_MEMORY", re.compile(
        r"^(?:aura[,]?\s*)?(?:souviens[- ]toi\s+que|m[ée]morise\s+que|retiens\s+que|garde\s+en\s+m[ée]moire\s+que)\s+(.+)$",
        re.IGNORECASE,
    )),
    ("LIST_MEMORIES", re.compile(
        r"^(?:aura[,]?\s*)?(?:qu['’]est-ce que tu sais (?:sur|de) moi|que sais-tu (?:sur|de) moi|montre[- ]moi (?:mes souvenirs|ce que tu sais sur moi)|liste (?:mes souvenirs|ce que tu sais sur moi))\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("SEARCH_MEMORY", re.compile(
        r"^(?:aura[,]?\s*)?(?:dans ta m[ée]moire[,]?\s*(?:qu['’]est-ce que tu sais sur|que sais-tu sur)|cherche dans ta m[ée]moire(?: sur)?)\s+(.+?)[?.!]*$",
        re.IGNORECASE,
    )),
    ("FORGET_MEMORY", re.compile(
        r"^(?:aura[,]?\s*)?(?:oublie|efface de ta m[ée]moire)\s+(?:le\s+souvenir\s+)?(?:num[ée]ro\s*|n°\s*|#\s*)?(\d+)\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("FORGET_MEMORY", re.compile(
        r"^(?:aura[,]?\s*)?oublie\s+que\s+(.+)$",
        re.IGNORECASE,
    )),
    ("FORGET_ALL_MEMORIES", re.compile(
        r"^(?:aura[,]?\s*)?(?:(?:oublie|efface)\s+tout\s+ce\s+que\s+tu\s+sais\s+sur\s+moi|efface\s+toute\s+ta\s+m[ée]moire(?:\s+sur\s+moi)?)\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("FORGET_MEMORY_ALL", re.compile(
        r"^(?:aura[,]?\s*)?(?:oublie|efface)\s+tout\s+ce\s+que\s+tu\s+sais\s+sur\s+(.+?)[?.!]*$",
        re.IGNORECASE,
    )),
    # AURA P0.8.5.4.7.6.1.5 — NATURAL FORGET ROUTING
    # Broad natural-language forgetting remains AFTER the explicit "forget all"
    # rules, so "oublie tout..." cannot become a fuzzy single-memory deletion.
    ("FORGET_MEMORY", re.compile(
        r"^(?:aura[,]?\s*)?(?:(?:oublie)|(?:efface\s+de\s+ta\s+m[ée]moire)|(?:(?:efface|supprime)\s+(?:ce|le)\s+souvenir))\s+(?!tout\b|que\b)(.+?)[?.!]*$",
        re.IGNORECASE,
    )),
    ("EXPLAIN_MEMORY", re.compile(
        r"^(?:aura[,]?\s*)?(?:pourquoi tu sais (?:[cç]a|cela)|d['’]o[uù] tu sais (?:[cç]a|cela)|comment tu sais (?:[cç]a|cela))\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("MEMORY_STATUS", re.compile(
        r"^(?:aura[,]?\s*)?(?:statut m[ée]moire|[ée]tat de ta m[ée]moire|la m[ée]moire est-elle active)\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("SET_MEMORY_PRIVATE_MODE", re.compile(
        r"^(?:aura[,]?\s*)?(?:active|passe en|mets-toi en)\s+(?:le\s+)?mode\s+priv[ée]\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("SET_MEMORY_NORMAL_MODE", re.compile(
        r"^(?:aura[,]?\s*)?(?:d[ée]sactive|quitte|sors du)\s+(?:le\s+)?mode\s+priv[ée]\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("CREATE_NOTE", re.compile(
        r"^(?:aura[,]?\s*)?(?:note que|prends?\s+une\s+note[:]?|ajoute\s+une\s+note[:]?|note[:]?)\s+(.+)$",
        re.IGNORECASE,
    )),
    ("SEARCH_NOTE", re.compile(
        r"^(?:aura[,]?\s*)?(?:montre[- ]moi mes notes (?:concernant|sur|à propos de)"
        r"|cherche(?:z)? dans mes notes|recherche(?:z)? dans mes notes)\s+(.+)$",
        re.IGNORECASE,
    )),
    ("LIST_NOTES", re.compile(
        r"^(?:aura[,]?\s*)?(?:montre[- ]moi mes notes|liste(?: moi)? mes notes"
        r"|liste des notes|quelles sont mes notes|affiche mes notes|ouvre mes notes)\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("DELETE_NOTE", re.compile(
        r"^(?:aura[,]?\s*)?supprime(?:z)?\s+la\s+note\s+(?:numéro |num[ée]ro |n°|#)?(\d+)\.?$",
        re.IGNORECASE,
    )),
    ("CREATE_TASK", re.compile(
        r"^(?:aura[,]?\s*)?(?:cr[ée]e|cree|cr[ée][ée]|ajoute)\s+(?:une\s+)?t[âa]che(?:\s*[:\-]\s*|\s+)(.+)$",
        re.IGNORECASE,
    )),
    ("CREATE_TASK", re.compile(
        r"^(?:aura[,]?\s*)?(?:cr[ée]e|cree|cr[ée][ée]|ajoute)\s+(?:une\s+)?t[âa]che\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("CREATE_TASK", re.compile(
        r"^(?:aura[,]?\s*)?ajoute\s+(.+?)\s+(?:à|a)\s+m(?:a liste|es t[âa]ches)\.?$",
        re.IGNORECASE,
    )),
    ("CREATE_TASK", re.compile(
        r"^(?:aura[,]?\s*)?je dois\s+(.+)$",
        re.IGNORECASE,
    )),
    ("LIST_TASKS", re.compile(
        r"^(?:aura[,]?\s*)?(?:quelles sont mes t[âa]ches|montre[- ]moi mes t[âa]ches"
        r"|liste(?: moi)? mes t[âa]ches|affiche mes t[âa]ches|ouvre mes t[âa]ches|qu['’]est-ce que j['’]ai [àa] faire(?: aujourd['’]hui)?)"
        r"\s*\??\.?$",
        re.IGNORECASE,
    )),
    ("COMPLETE_TASK", re.compile(
        r"^(?:aura[,]?\s*)?marque\s+la\s+t[âa]che\s+(.+?)\s+comme\s+termin[ée]e?\.?$",
        re.IGNORECASE,
    )),
    ("COMPLETE_TASK", re.compile(
        r"^(?:aura[,]?\s*)?termine\s+la\s+t[âa]che\s+(.+?)\.?$",
        re.IGNORECASE,
    )),
    ("LIST_REMINDERS", re.compile(
        r"^(?:aura[,]?\s*)?(?:mes rappels|quels sont mes rappels|liste(?: moi)? mes rappels"
        r"|montre[- ]moi mes rappels|affiche mes rappels|ouvre mes rappels)\s*[?.!]*$",
        re.IGNORECASE,
    )),
    ("DELETE_REMINDER", re.compile(
        r"^(?:aura[,]?\s*)?supprime(?:z)?\s+le\s+rappel\s+(?:numéro |num[ée]ro |n°|#)?(\d+)\.?$",
        re.IGNORECASE,
    )),
]


class IntentManager:
    """Detecte une intention a partir du texte brut de l'utilisateur."""

    def detect(self, text: str):
        text = text.strip()
        for intent, pattern in _PATTERNS:
            match = pattern.match(text)
            if match:
                if match.groups():
                    raw = match.group(1).strip().lstrip(":").strip()
                    params = {"raw": raw}
                else:
                    params = {}
                return intent, params

        # Cas particulier : dans une phrase de rappel, l'expression temporelle
        # peut se trouver avant, apres ou au milieu du contenu ("Rappelle-moi
        # de X a 19h", "Rappelle-moi demain matin d'X", "Dans 30 minutes,
        # rappelle-moi de X"). Un simple pattern ancre ne suffit pas : on
        # delegue toute la phrase a ReminderParser (section 13).
        # Tolerance aux fautes de frappe courantes (rapelle, rappel, rapel).
        if re.search(r"\b(?:rappelle|rapelle|rappele|rappel|rapel)[- ]moi\b", text, re.IGNORECASE):
            return "CREATE_REMINDER", {"raw": text}

        return None, {}
