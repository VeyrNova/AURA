"""ActionRouter for deterministic local actions.

v0.4.1 flow:
User Input -> IntentManager -> ActionRouter -> SecurityPolicyEngine -> Module
"""
import logging
from datetime import datetime

from config.settings import settings
from modules.reminder_parser import ReminderParser
from security.policy_engine import SecurityPolicyEngine

logger = logging.getLogger("aura.router")


class ActionRouter:
    def __init__(
        self,
        notes_manager,
        task_manager,
        reminder_manager,
        security_engine: SecurityPolicyEngine,
        memory_manager=None,
    ):
        self.notes_manager = notes_manager
        self.task_manager = task_manager
        self.reminder_manager = reminder_manager
        self.security_engine = security_engine
        self.memory_manager = memory_manager
        self.reminder_parser = ReminderParser()

    def route(self, intent: str, params: dict, *, user_confirmed: bool = False) -> str:
        decision = self.security_engine.authorize(
            intent,
            params,
            user_confirmed=user_confirmed,
        )
        if not decision.allowed:
            if decision.confirmation_required:
                return "Cette action nécessite une confirmation explicite avant exécution."
            return "Je n'exécute pas cette action : elle n'est pas autorisée par ma politique de sécurité."

        if intent == "CREATE_MEMORY":
            return self._create_memory(params.get("raw", ""))
        if intent == "LIST_MEMORIES":
            return self._list_memories()
        if intent == "SEARCH_MEMORY":
            return self._search_memory(params.get("raw", ""))
        if intent == "ANSWER_MEMORY_QUERY":
            return self._answer_memory_query(params.get("raw", ""))
        if intent == "FORGET_MEMORY":
            return self._forget_memory(params.get("raw", ""), all_matches=False)
        if intent == "FORGET_MEMORY_ALL":
            return self._forget_memory(params.get("raw", ""), all_matches=True)
        if intent == "FORGET_ALL_MEMORIES":
            return self._forget_all_memories()
        if intent == "EXPLAIN_MEMORY":
            return self._explain_memory()
        if intent == "MEMORY_STATUS":
            return self._memory_status()
        if intent == "SET_MEMORY_PRIVATE_MODE":
            return self._set_memory_private(True)
        if intent == "SET_MEMORY_NORMAL_MODE":
            return self._set_memory_private(False)
        if intent == "CREATE_NOTE":
            return self._create_note(params.get("raw", ""))
        if intent == "LIST_NOTES":
            return self._list_notes()
        if intent == "SEARCH_NOTE":
            return self._search_notes(params.get("raw", ""))
        if intent == "DELETE_NOTE":
            return self._delete_note(params.get("raw", ""))
        if intent == "CREATE_TASK":
            return self._create_task(params.get("raw", ""))
        if intent == "LIST_TASKS":
            return self._list_tasks()
        if intent == "COMPLETE_TASK":
            return self._complete_task(params.get("raw", ""))
        if intent == "CREATE_REMINDER":
            return self._create_reminder(params.get("raw", ""))
        if intent == "LIST_REMINDERS":
            return self._list_reminders()
        if intent == "DELETE_REMINDER":
            return self._delete_reminder(params.get("raw", ""))

        # This should not normally be reached because the security engine fails closed.
        logger.warning("Intent autorise mais sans executeur : %s", intent)
        return "Cette capacité n'a pas encore d'exécuteur disponible."

    def _create_note(self, content: str) -> str:
        content = content.strip()
        if not content:
            return "Je n'ai pas compris le contenu de la note."
        note_id = self.notes_manager.create_note(content=content)
        return f"C'est noté (note #{note_id})."

    def _list_notes(self) -> str:
        notes = self.notes_manager.list_notes(limit=10)
        if not notes:
            return "Tu n'as pas encore de notes enregistrées."
        lines = [f"#{n['id']} — {n['content']}" for n in notes]
        return "Voici tes notes les plus récentes :<br>" + "<br>".join(lines)

    def _search_notes(self, query: str) -> str:
        query = query.strip()
        if not query:
            return "Que dois-je chercher dans tes notes ?"
        notes = self.notes_manager.search_notes(query)
        if not notes:
            return f"Je n'ai trouvé aucune note concernant « {query} »."
        lines = [f"#{n['id']} — {n['content']}" for n in notes]
        return f"Notes concernant « {query} » :<br>" + "<br>".join(lines)

    def _delete_note(self, raw_id: str) -> str:
        try:
            note_id = int(raw_id.strip())
        except ValueError:
            return "Je n'ai pas compris le numéro de la note à supprimer."
        success = self.notes_manager.delete_note(note_id)
        if success:
            return f"La note #{note_id} a été supprimée."
        return f"Je n'ai trouvé aucune note portant le numéro {note_id}."

    def _create_task(self, title: str) -> str:
        title = title.strip().rstrip(".")
        if not title:
            return "Quelle tâche veux-tu ajouter ?"
        task_id = self.task_manager.create_task(title=title)
        return f"Tâche ajoutée (#{task_id}) : {title}."

    def _list_tasks(self) -> str:
        tasks = self.task_manager.list_tasks()
        if not tasks:
            return "Tu n'as aucune tâche en cours."
        lines = []
        for task in tasks:
            mark = "✓" if task["status"] == "DONE" else "…"
            lines.append(f"[{mark}] #{task['id']} — {task['title']}")
        return "Voici tes tâches :<br>" + "<br>".join(lines)

    def _complete_task(self, identifier: str) -> str:
        identifier = identifier.strip().rstrip(".")
        if not identifier:
            return "Quelle tâche dois-je marquer comme terminée ?"
        task = self.task_manager.complete_task(identifier)
        if task is None:
            return f"Je n'ai trouvé aucune tâche correspondant à « {identifier} »."
        return f"Tâche #{task['id']} marquée comme terminée : {task['title']}."

    def _create_reminder(self, raw_text: str) -> str:
        content, trigger_dt = self.reminder_parser.parse(raw_text)
        if trigger_dt is None:
            return (
                "Je n'ai pas compris pour quand programmer ce rappel. "
                "Peux-tu préciser une heure ou une date ? (ex : « à 19 heures », "
                "« demain matin », « dans 30 minutes »)"
            )
        if not content:
            return "Je n'ai pas compris ce que je dois te rappeler."
        reminder_id = self.reminder_manager.create_reminder(content, trigger_dt)
        formatted = trigger_dt.strftime("%d/%m/%Y à %H:%M")
        return f"Rappel programmé (#{reminder_id}) pour le {formatted} : {content}."

    def _list_reminders(self) -> str:
        reminders = self.reminder_manager.list_reminders()
        if not reminders:
            return "Tu n'as aucun rappel programmé."
        lines = []
        for reminder in reminders:
            dt = datetime.fromisoformat(reminder["trigger_at"])
            lines.append(
                f"#{reminder['id']} — {reminder['content']} ({dt.strftime('%d/%m %H:%M')})"
            )
        return "Voici tes prochains rappels :<br>" + "<br>".join(lines)

    def _delete_reminder(self, raw_id: str) -> str:
        try:
            reminder_id = int(raw_id.strip())
        except ValueError:
            return "Je n'ai pas compris le numéro du rappel à supprimer."
        success = self.reminder_manager.delete_reminder(reminder_id)
        if success:
            return f"Le rappel #{reminder_id} a été supprimé."
        return f"Je n'ai trouvé aucun rappel portant le numéro {reminder_id}."
    # ------------------------------------------------------------------
    # Persistent memory v0.6
    def _memory_unavailable(self) -> str:
        return "La mémoire persistante n'est pas disponible dans cette installation."

    def _create_memory(self, content: str) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        if not settings.MEMORY_ENABLED:
            return "La mémoire persistante est désactivée dans la configuration AURA."
        content = (content or "").strip().rstrip(".")
        if not content:
            return "Que veux-tu que je retienne ?"
        if self.memory_manager.private_mode:
            return "Le mode privé est actif : je n'ajoute aucun nouveau souvenir tant qu'il reste activé."
        try:
            record, created = self.memory_manager.remember(content, source="explicit_user", importance=4)
        except RuntimeError:
            return "Le mode privé est actif : je n'ajoute aucun nouveau souvenir."
        if record.is_sensitive:
            if created:
                return "D'accord. Je le garde en mémoire locale comme information sensible."
            return "Oui, je l'avais déjà en mémoire locale comme information sensible."
        fact = self.memory_manager.humanize_record(record)
        if created:
            return f"D'accord. Je retiens que {fact[0].lower() + fact[1:]}"
        return f"Oui, je m'en souvenais déjà : {fact[0].lower() + fact[1:]}"

    def _list_memories(self) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        records = self.memory_manager.list_memories(limit=20, include_sensitive=True)
        if not records:
            return "Je n'ai encore aucun souvenir persistant à ton sujet."
        lines = []
        for rec in records:
            if rec.is_sensitive:
                lines.append(f"• {rec.content} (information sensible)")
            else:
                lines.append(f"• {self.memory_manager.humanize_record(rec)}")
        if len(lines) == 1:
            return "Je me souviens de ceci :\n" + lines[0]
        return "Je me souviens notamment de ceci :\n" + "\n".join(lines)

    def _search_memory(self, query: str) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        query = (query or "").strip().rstrip("?.!")
        if not query:
            return "Que dois-je chercher dans ma mémoire ?"
        records = self.memory_manager.search(query, limit=10, include_sensitive=True)
        if not records:
            return f"Je n'ai trouvé aucun souvenir concernant « {query} »."
        lines = []
        for rec in records:
            if rec.is_sensitive:
                lines.append(f"• {rec.content} (information sensible)")
            else:
                lines.append(f"• {self.memory_manager.humanize_record(rec)}")
        if len(lines) == 1:
            return f"Je me souviens de ceci à propos de « {query} » :<br>" + lines[0]
        return f"Voilà ce que je me rappelle à propos de « {query} » :<br>" + "<br>".join(lines)

    def _answer_memory_query(self, query: str) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        answer = self.memory_manager.answer_personal_question(query)
        if answer:
            return answer
        return "Je n'ai pas de souvenir suffisamment précis pour répondre à ça sans supposer."

    def _forget_memory(self, raw: str, *, all_matches: bool) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        raw = (raw or "").strip().rstrip("?.!")
        if not raw:
            return "Quel souvenir dois-je oublier ?"
        removed = self.memory_manager.forget(raw, all_matches=all_matches)
        if not removed:
            return f"Je n'ai trouvé aucun souvenir correspondant à « {raw} »."
        if len(removed) == 1:
            return "C'est oublié. J'ai supprimé ce souvenir de ma mémoire locale."
        return f"C'est oublié : {len(removed)} souvenirs correspondants ont été supprimés de ma mémoire locale."

    def _forget_all_memories(self) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        counts = self.memory_manager.forget_all_profile_data()
        return (
            "C'est fait. J'ai effacé ma mémoire personnelle locale et remis à zéro la continuité/familiarité "
            f"({counts['memories']} souvenir(s), {counts['sessions']} session(s)). "
            "Tes notes, tâches et rappels n'ont pas été touchés."
        )

    def _explain_memory(self) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        records = self.memory_manager.explain_last_context()
        if not records:
            return "Je n'ai utilisé aucun souvenir persistant identifiable dans le contexte récent."
        lines = []
        for rec in records[:5]:
            source = self.memory_manager.source_label(rec)
            fact = rec.content if rec.is_sensitive else self.memory_manager.humanize_record(rec)
            lines.append(f"• {fact} — {source}, enregistré le {rec.created_at}")
        return "Voilà pourquoi je le sais :<br>" + "<br>".join(lines)

    def _memory_status(self) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        count = int(self.memory_manager.db.conn.execute("SELECT COUNT(*) FROM memories WHERE status='ACTIVE'").fetchone()[0])
        mode = "PRIVÉ" if self.memory_manager.private_mode else "NORMAL"
        auto = "active" if settings.MEMORY_AUTO_CAPTURE else "désactivée"
        return f"Mémoire persistante : {count} souvenir(s) · mode {mode} · capture adaptative prudente {auto}."

    def _set_memory_private(self, enabled: bool) -> str:
        if self.memory_manager is None:
            return self._memory_unavailable()
        if not settings.MEMORY_ENABLED and not enabled:
            return "La mémoire persistante est désactivée dans la configuration AURA ; le mode privé reste actif."
        self.memory_manager.set_private_mode(enabled)
        if enabled:
            return "Mode privé activé. Je n'ajouterai ni n'injecterai de nouveaux souvenirs persistants pendant cette session."
        return "Mode privé désactivé. La mémoire persistante et la continuité sont de nouveau actives."


# === AURA v2.1.1 R4 canonical memory router binding BEGIN ===
_AURA_V211_R4_PREVIOUS_ROUTER_CREATE_MEMORY = ActionRouter._create_memory


def _aura_v211_r4_memory_response(decision, result) -> str:
    candidate = decision.candidate
    if candidate is None:
        return "Je n'ai pas identifié de fait mémoire structuré."

    subject = str(candidate.subject)
    value = str(candidate.object_text)

    if decision.operation == "NEW":
        return f"D'accord. Je retiens dans ma mémoire canonique que {subject} : {value}."
    if decision.operation == "UPDATE":
        return (
            f"D'accord. J'ai mis à jour ma mémoire canonique : "
            f"{subject} vaut maintenant {value}."
        )
    if decision.operation == "UNCHANGED":
        return f"Oui, cette information est déjà dans ma mémoire canonique : {subject} : {value}."
    if decision.operation == "CONTRADICTION":
        count = len(result.get("conflicts") or [])
        return (
            f"J'ai mémorisé cette information, mais elle contredit "
            f"{count} fait(s) déjà présent(s) pour {subject}. "
            "Je conserve les deux versions comme conflit explicite tant qu'il n'est pas résolu."
        )
    if decision.operation == "TEMPORAL_TRANSITION":
        return (
            f"D'accord. J'ai enregistré cette évolution temporelle pour {subject} "
            f"sans écraser son historique."
        )
    return "D'accord."


def _aura_v211_r4_router_create_memory(self, raw: str) -> str:
    # Keep the exact legacy path for free-text memories the deterministic v2.1.1
    # extractor does not yet understand.
    if self.memory_manager is None:
        return _AURA_V211_R4_PREVIOUS_ROUTER_CREATE_MEMORY(self, raw)

    if bool(getattr(self.memory_manager, "private_mode", False)):
        return _AURA_V211_R4_PREVIOUS_ROUTER_CREATE_MEMORY(self, raw)

    from runtime.aura_conversation_memory_integration_v211 import (
        ConversationMemoryIntegration,
    )

    adapter = getattr(self, "_aura_v211_conversation_memory", None)
    if adapter is None or getattr(adapter, "memory_manager", None) is not self.memory_manager:
        adapter = ConversationMemoryIntegration(self.memory_manager)
        self._aura_v211_conversation_memory = adapter

    decision = adapter.plan_message(str(raw or ""), scope="user")
    if decision.operation == "IGNORE":
        return _AURA_V211_R4_PREVIOUS_ROUTER_CREATE_MEMORY(self, raw)

    # Reaching CREATE_MEMORY is already an explicit user memory action. This is
    # the authorization boundary defined by the frozen R2 contract.
    result = adapter.commit_explicit_fact(
        decision,
        explicit_user_authorization=True,
    )
    return _aura_v211_r4_memory_response(decision, result)


ActionRouter._create_memory = _aura_v211_r4_router_create_memory
# === AURA v2.1.1 R4 canonical memory router binding END ===

# === AURA v2.1.1 R6 canonical personal-answer router binding BEGIN ===
_AURA_V211_R6_PREVIOUS_ANSWER_MEMORY_QUERY = ActionRouter._answer_memory_query
_AURA_V211_R6_PREVIOUS_EXPLAIN_MEMORY = ActionRouter._explain_memory


def _aura_v211_r6_router_adapter(self):
    if self.memory_manager is None:
        return None
    from runtime.aura_conversation_memory_integration_v211 import (
        ConversationMemoryIntegration,
    )
    adapter = getattr(self, "_aura_v211_conversation_memory", None)
    if adapter is None or getattr(adapter, "memory_manager", None) is not self.memory_manager:
        adapter = ConversationMemoryIntegration(self.memory_manager)
        self._aura_v211_conversation_memory = adapter
    return adapter


def _aura_v211_r6_answer_memory_query(self, raw: str) -> str:
    adapter = _aura_v211_r6_router_adapter(self)
    if adapter is None:
        return _AURA_V211_R6_PREVIOUS_ANSWER_MEMORY_QUERY(self, raw)

    result = adapter.answer_personal_query(
        str(raw or ""),
        scope="user",
        include_sensitive=False,
    )

    if result.get("status") == "answered":
        return str(result["answer"])

    if result.get("status") == "empty":
        return _AURA_V211_R6_PREVIOUS_ANSWER_MEMORY_QUERY(self, raw)

    if result.get("status") == "private":
        return self._memory_unavailable()

    # Fail closed: a canonical recall error must not promote stale legacy memory
    # to authoritative truth.
    return (
        "Je n'arrive pas à interroger ma mémoire canonique correctement pour "
        "le moment. Je préfère ne pas te donner un ancien souvenir comme s'il "
        "était certain."
    )


def _aura_v211_r6_explain_memory(self, *args, **kwargs) -> str:
    adapter = _aura_v211_r6_router_adapter(self)
    if adapter is not None:
        explanation = adapter.explain_last_answer()
        if explanation:
            return explanation
    return _AURA_V211_R6_PREVIOUS_EXPLAIN_MEMORY(self, *args, **kwargs)


ActionRouter._answer_memory_query = _aura_v211_r6_answer_memory_query
ActionRouter._explain_memory = _aura_v211_r6_explain_memory
# === AURA v2.1.1 R6 canonical personal-answer router binding END ===
