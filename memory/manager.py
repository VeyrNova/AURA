"""Local persistent memory manager for AURA v0.6."""
from __future__ import annotations

import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from config.settings import settings
from memory.privacy import looks_sensitive

logger = logging.getLogger("aura.memory")

_STOPWORDS = {
    "avec", "dans", "pour", "sans", "mais", "donc", "comme", "plus", "moins", "très",
    "tres", "une", "des", "les", "mes", "tes", "ses", "mon", "ton", "son", "notre", "votre",
    "leur", "leurs", "que", "qui", "quoi", "dont", "est", "suis", "être", "etre", "avoir", "fait",
    "faire", "cela", "ça", "les", "sur", "sous", "aux", "par", "pas", "tout", "tous", "cette",
    "cet", "ces", "moi", "toi", "lui", "elle", "nous", "vous", "ils", "elles", "peux",
    "veux", "veux", "dois", "quel", "quelle", "quels", "quelles", "comment", "pourquoi",
}

_AUTO_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # P0.6.4.6.1 — explicit long-lived response-style preference.
    # Narrow on purpose: only "à partir de maintenant / désormais" directives
    # about how AURA should answer are auto-captured.
    ("preference", re.compile(
        r"\b(?:[àa]\s+partir\s+de\s+maintenant|d[ée]sormais)[, ]+"
        r"r[ée]ponds[- ]?moi\s+(.{2,180})[.!?]?$",
        re.IGNORECASE,
    )),
    ("preference", re.compile(r"\bje\s+pr[ée]f[èe]re\s+(.{2,180})$", re.IGNORECASE)),
    ("preference", re.compile(r"\bj['’]aime\s+(.{2,180})$", re.IGNORECASE)),
    ("preference", re.compile(r"\bje\s+n['’]aime\s+pas\s+(.{2,180})$", re.IGNORECASE)),
    ("project", re.compile(r"\bje\s+travaille\s+sur\s+(.{2,200})$", re.IGNORECASE)),
    ("project", re.compile(r"\bmon\s+projet(?:\s+principal)?\s+(?:est|:)\s+(.{2,200})$", re.IGNORECASE)),
    ("habit", re.compile(r"\b(?:d['’]habitude|habituellement|en g[ée]n[ée]ral)[, ]+je\s+(.{2,180})$", re.IGNORECASE)),
)


@dataclass(frozen=True)
class MemoryRecord:
    id: int
    content: str
    type: str
    importance: int
    source: str
    confidence: float
    created_at: str
    updated_at: str | None = None
    last_accessed_at: str | None = None
    access_count: int = 0
    is_sensitive: bool = False
    tags: str | None = None

    @classmethod
    def from_row(cls, row) -> "MemoryRecord":
        data = dict(row)
        return cls(
            id=int(data["id"]),
            content=str(data["content"]),
            type=str(data.get("type") or "fact"),
            importance=int(data.get("importance") or 1),
            source=str(data.get("source") or "unknown"),
            confidence=float(data.get("confidence") or 1.0),
            created_at=str(data.get("created_at") or ""),
            updated_at=data.get("updated_at"),
            last_accessed_at=data.get("last_accessed_at"),
            access_count=int(data.get("access_count") or 0),
            is_sensitive=bool(data.get("is_sensitive") or 0),
            tags=data.get("tags"),
        )


class MemoryManager:
    """SQLite-backed long-term memory with bounded local retrieval."""

    def __init__(self, db):
        self.db = db
        self.private_mode = False
        self.last_context_ids: list[int] = []
        self.last_visible_ids: list[int] = []

    @staticmethod
    def normalize(text: str) -> str:
        text = unicodedata.normalize("NFKD", (text or "").lower())
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return " ".join(text.split())

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        return {
            t for t in cls.normalize(text).split()
            if len(t) >= 3 and t not in _STOPWORDS
        }

    @staticmethod
    def _classify_explicit(content: str) -> str:
        low = (content or "").lower()
        if any(x in low for x in ("je préfère", "je prefere", "j'aime", "je n'aime pas", "je déteste", "je deteste")):
            return "preference"
        if any(x in low for x in ("projet", "je travaille sur", "je développe", "je developpe")):
            return "project"
        if any(x in low for x in ("d'habitude", "habituellement", "souvent je", "en général je", "en general je")):
            return "habit"
        if any(x in low for x in ("objectif", "je veux atteindre", "mon but")):
            return "goal"
        return "fact"

    def set_private_mode(self, enabled: bool) -> None:
        self.private_mode = bool(enabled)
        self.last_context_ids = []
        logger.info("Memory private mode=%s", self.private_mode)

    @staticmethod
    def _capitalize_sentence(text: str) -> str:
        text = (text or "").strip()
        if not text:
            return text
        return text[0].upper() + text[1:]

    @classmethod
    def humanize_record(cls, record: MemoryRecord) -> str:
        """Render a stored first-person fact as natural second-person French.

        Technical metadata (id/type/confidence) deliberately stays out of normal
        conversation. It remains visible in the dedicated Memory control center.
        """
        content = (record.content or "").strip().rstrip(" .!?")
        low = content.lower()
        replacements = (
            ("je préfère ", "tu préfères "),
            ("je prefere ", "tu préfères "),
            ("j'aime ", "tu aimes "),
            ("j’aime ", "tu aimes "),
            ("je n'aime pas ", "tu n'aimes pas "),
            ("je n’aime pas ", "tu n'aimes pas "),
            ("je déteste ", "tu détestes "),
            ("je deteste ", "tu détestes "),
            ("je travaille sur ", "tu travailles sur "),
            ("mon projet principal est ", "ton projet principal est "),
            ("mon projet est ", "ton projet est "),
            ("mon objectif est ", "ton objectif est "),
            ("mon but est ", "ton but est "),
        )
        for prefix, replacement in replacements:
            if low.startswith(prefix):
                converted = replacement + content[len(prefix):]
                return cls._capitalize_sentence(converted) + "."

        # For arbitrary facts, quoting the user's own wording is safer and more
        # natural than attempting fragile French conjugation.
        return f"Tu m'as dit : « {content} »."

    @classmethod
    def _is_response_style_query(cls, query: str) -> bool:
        q = cls.normalize(query)
        response_words = ("reponse", "reponses", "repondre", "style", "concis", "court", "detail")
        personal_words = ("pour moi", "me repondre", "devrais tu", "dois tu", "je prefere")
        return any(word in q for word in response_words) and any(word in q for word in personal_words)

    @classmethod
    def _is_profile_summary_query(cls, query: str) -> bool:
        """Return True when the user explicitly asks what AURA remembers about them.

        This must not rely on semantic overlap with a stored memory: a generic
        question such as ``Que sais-tu de moi ?`` is a request for the complete
        non-sensitive profile, not a topical retrieval query.
        """
        q = cls.normalize(query)
        exact_or_prefix = (
            "que sais tu de moi",
            "qu est ce que tu sais de moi",
            "que connais tu de moi",
            "que connais tu sur moi",
            "qu est ce que tu connais de moi",
            "qu est ce que tu connais sur moi",
            "qu as tu retenu de moi",
            "qu est ce que tu as retenu de moi",
            "que te rappelles tu de moi",
            "qu est ce que tu te rappelles de moi",
            "quels souvenirs as tu de moi",
            "what do you know about me",
            "what do you remember about me",
        )
        return any(q == phrase or q.startswith(phrase + " ") for phrase in exact_or_prefix)

    @classmethod
    def _is_response_style_memory(cls, record: MemoryRecord) -> bool:
        if record.type != "preference":
            return False
        text = cls.normalize(record.content)
        return any(word in text for word in ("reponse", "reponses", "repondre", "concis", "courtes", "courts", "detail"))

    def _select_personal_answer(self, query: str) -> tuple[str, MemoryRecord | None] | None:
        if self.private_mode or not settings.MEMORY_ENABLED:
            return None
        query = (query or "").strip()
        if not query:
            return None

        q = self.normalize(query)
        questionish = query.rstrip().endswith("?") or q.startswith((
            "quel ", "quelle ", "quels ", "quelles ", "comment ",
            "que ", "qu est ce", "est ce", "dois tu", "devrais tu",
        ))
        if not questionish:
            return None

        if self._is_profile_summary_query(query):
            # A global recall question is deterministic even when the profile is
            # empty; never send it to the LLM to improvise about AURA's memory.
            return "profile_summary", None

        candidates = self.list_memories(50, include_sensitive=False, track=False)
        if not candidates:
            return None

        if self._is_response_style_query(query):
            matches = [record for record in candidates if self._is_response_style_memory(record)]
            if matches:
                matches.sort(key=lambda r: (r.importance, r.confidence, r.updated_at or r.created_at), reverse=True)
                return "response_style", matches[0]

        # Generic direct-memory Q&A is intentionally narrow: it must clearly ask
        # about the user's own preference/fact and share meaningful words with a
        # stored memory. Advice questions such as "Comment avancer sur AURA ?"
        # still go to the LLM with memory context instead of being short-circuited.
        personal_markers = (
            "je prefere", "j aime", "pour moi", "sur moi",
            "mon ", "ma ", "mes ", "moi ",
        )
        padded = f" {q} "
        if not any(marker in padded for marker in personal_markers):
            return None

        scored = [(self._score(query, record), record) for record in candidates]
        scored = [(score, record) for score, record in scored if score >= 0.42]
        if not scored:
            return None
        scored.sort(key=lambda item: (item[0], item[1].importance, item[1].confidence), reverse=True)
        _, record = scored[0]
        if not (self._tokens(query) & self._tokens(record.content)):
            return None
        return "generic", record

    def can_answer_personal_question(self, query: str) -> bool:
        return self._select_personal_answer(query) is not None

    def answer_personal_question(self, query: str) -> str | None:
        """Answer a narrow personal-memory question without invoking the LLM."""
        selected = self._select_personal_answer(query)
        if selected is None:
            return None
        mode, record = selected

        if mode == "profile_summary":
            records = self.list_memories(20, include_sensitive=False, track=False)
            if not records:
                return "Je n'ai encore aucun souvenir personnel enregistré sur toi."
            records.sort(
                key=lambda r: (r.importance, r.confidence, r.updated_at or r.created_at),
                reverse=True,
            )
            self._mark_accessed(records)
            self.last_context_ids = [r.id for r in records]
            self.last_visible_ids = [r.id for r in records]
            facts = [self.humanize_record(r).rstrip() for r in records]
            if len(facts) == 1:
                fact = facts[0]
                return (
                    f"Pour l'instant, je me souviens que {fact[0].lower() + fact[1:]} "
                    "C'est le seul élément personnel que tu m'as demandé de conserver durablement."
                )
            rendered = " ".join(f"• {fact}" for fact in facts)
            return f"Voici ce que je me souviens de toi pour l'instant : {rendered}"

        if record is None:
            return None
        self._mark_accessed([record])
        self.last_context_ids = [record.id]
        self.last_visible_ids = [record.id]
        fact = self.humanize_record(record)

        if mode == "response_style":
            return f"{fact} Je vais donc privilégier ce style, sauf si tu me demandes plus de détails."
        if record.type == "preference":
            return f"D'après ce que tu m'as demandé de retenir, {fact[0].lower() + fact[1:]}"
        if record.type in {"project", "goal", "habit"}:
            return f"Je me souviens que {fact[0].lower() + fact[1:]}"
        return f"Je me souviens de ceci : {fact}"

    def remember(
        self,
        content: str,
        *,
        memory_type: str | None = None,
        importance: int = 3,
        source: str = "explicit_user",
        confidence: float = 1.0,
        allow_sensitive: bool = True,
        tags: str | None = None,
    ) -> tuple[MemoryRecord, bool]:
        content = (content or "").strip().rstrip()
        if not content:
            raise ValueError("Souvenir vide")
        if self.private_mode:
            raise RuntimeError("private_mode")

        sensitive = looks_sensitive(content)
        if sensitive and not allow_sensitive:
            raise ValueError("sensitive_auto_capture")

        normalized = self.normalize(content)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        existing = self.db.conn.execute(
            "SELECT * FROM memories WHERE normalized_content = ? AND status = 'ACTIVE' LIMIT 1",
            (normalized,),
        ).fetchone()
        if existing:
            new_importance = max(int(existing["importance"] or 1), max(1, min(5, int(importance))))
            new_confidence = max(float(existing["confidence"] or 0.0), max(0.0, min(1.0, float(confidence))))
            self.db.conn.execute(
                "UPDATE memories SET importance=?, confidence=?, updated_at=?, source=?, is_sensitive=? WHERE id=?",
                (new_importance, new_confidence, now, source, 1 if sensitive else 0, existing["id"]),
            )
            self.db.conn.commit()
            row = self.db.conn.execute("SELECT * FROM memories WHERE id=?", (existing["id"],)).fetchone()
            return MemoryRecord.from_row(row), False

        cursor = self.db.conn.execute(
            "INSERT INTO memories "
            "(content, type, importance, source, confidence, created_at, updated_at, normalized_content, "
            "status, access_count, is_sensitive, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 0, ?, ?)",
            (
                content,
                memory_type or self._classify_explicit(content),
                max(1, min(5, int(importance))),
                source,
                max(0.0, min(1.0, float(confidence))),
                now,
                now,
                normalized,
                1 if sensitive else 0,
                tags,
            ),
        )
        self.db.conn.commit()
        row = self.db.conn.execute("SELECT * FROM memories WHERE id=?", (cursor.lastrowid,)).fetchone()
        record = MemoryRecord.from_row(row)
        logger.info("Souvenir cree id=%s type=%s sensitive=%s source=%s", record.id, record.type, record.is_sensitive, source)
        return record, True

    def auto_capture(self, text: str) -> MemoryRecord | None:
        if self.private_mode or not settings.MEMORY_ENABLED or not settings.MEMORY_AUTO_CAPTURE:
            return None
        text = (text or "").strip()
        if not text or looks_sensitive(text):
            return None
        for memory_type, pattern in _AUTO_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            # Store the user's complete statement for provenance and natural retrieval,
            # but only for narrowly-defined low-risk patterns.
            try:
                record, created = self.remember(
                    text.rstrip(" .!?"),
                    memory_type=memory_type,
                    importance=2 if memory_type == "habit" else 3,
                    source=f"auto_{memory_type}",
                    confidence=0.78,
                    allow_sensitive=False,
                )
            except (ValueError, RuntimeError):
                return None
            return record if created else None
        return None

    def get(self, memory_id: int) -> MemoryRecord | None:
        row = self.db.conn.execute(
            "SELECT * FROM memories WHERE id=? AND status='ACTIVE'", (int(memory_id),)
        ).fetchone()
        return MemoryRecord.from_row(row) if row else None

    def list_memories(self, limit: int = 20, *, include_sensitive: bool = True, track: bool = True) -> list[MemoryRecord]:
        sql = "SELECT * FROM memories WHERE status='ACTIVE'"
        params: list[object] = []
        if not include_sensitive:
            sql += " AND is_sensitive=0"
        sql += " ORDER BY importance DESC, updated_at DESC, created_at DESC LIMIT ?"
        params.append(max(1, int(limit)))
        rows = self.db.conn.execute(sql, params).fetchall()
        records = [MemoryRecord.from_row(r) for r in rows]
        if track:
            self.last_visible_ids = [r.id for r in records]
        return records

    def search(self, query: str, limit: int = 10, *, include_sensitive: bool = True) -> list[MemoryRecord]:
        query = (query or "").strip()
        if not query:
            return self.list_memories(limit, include_sensitive=include_sensitive)
        candidates = self.list_memories(max(50, limit * 5), include_sensitive=include_sensitive, track=False)
        scored = [(self._score(query, rec), rec) for rec in candidates]
        scored = [(s, r) for s, r in scored if s > 0.0]
        scored.sort(key=lambda item: (item[0], item[1].importance, item[1].updated_at or item[1].created_at), reverse=True)
        records = [r for _, r in scored[:limit]]
        self.last_visible_ids = [r.id for r in records]
        return records

    def retrieve_for_context(self, query: str, limit: int | None = None) -> list[MemoryRecord]:
        if self.private_mode or not settings.MEMORY_ENABLED:
            self.last_context_ids = []
            return []
        limit = int(limit or settings.MEMORY_CONTEXT_LIMIT)
        include_sensitive = bool(settings.MEMORY_ALLOW_SENSITIVE_CONTEXT)
        candidates = self.list_memories(max(60, limit * 8), include_sensitive=include_sensitive, track=False)
        scored = [(self._score(query, rec), rec) for rec in candidates]
        scored = [(s, r) for s, r in scored if s >= float(settings.MEMORY_RELEVANCE_THRESHOLD)]

        if not scored and self._looks_personal_query(query):
            # Conservative continuity fallback: only a couple of high-importance,
            # non-sensitive preferences/projects/goals for personal advice.
            fallback = [
                r for r in candidates
                if r.type in {"preference", "project", "goal", "habit"} and r.importance >= 3
            ][: min(2, limit)]
            records = fallback
        else:
            scored.sort(key=lambda item: (item[0], item[1].importance), reverse=True)
            records = [r for _, r in scored[:limit]]

        self._mark_accessed(records)
        self.last_context_ids = [r.id for r in records]
        self.last_visible_ids = list(self.last_context_ids)
        return records

    @classmethod
    def _looks_personal_query(cls, query: str) -> bool:
        q = cls.normalize(query)
        markers = (
            "moi", "mon ", "ma ", "mes ", "me conseille", "pour moi",
            "j aime", "je prefere",
            # P0.6.2.6.1 — direct preference/meta questions must activate the
            # conservative preference/project/goal fallback even when lexical
            # overlap is weak ("répondre" vs stored "réponses").
            "comment dois tu me repondre", "comment dois je te demander",
            "comment me repondre", "comment me reponds tu",
            "mes preferences", "ma preference", "mes habitudes",
            "que sais tu de moi", "qu est ce que tu sais de moi",
            "comment dois tu t adapter", "adapte toi a moi",
        )
        return any(marker in f" {q} " for marker in markers)

    @classmethod
    def _score(cls, query: str, record: MemoryRecord) -> float:
        qn = cls.normalize(query)
        mn = cls.normalize(record.content)
        if not qn or not mn:
            return 0.0
        q_tokens = cls._tokens(qn)
        m_tokens = cls._tokens(mn)
        if not q_tokens or not m_tokens:
            return 0.0
        overlap = len(q_tokens & m_tokens)
        if overlap == 0:
            return 0.0
        coverage = overlap / max(1, len(q_tokens))
        specificity = overlap / max(1, len(m_tokens))
        phrase_bonus = 0.45 if (qn in mn or mn in qn) else 0.0
        importance_bonus = 0.06 * max(1, min(5, record.importance))
        confidence_bonus = 0.18 * max(0.0, min(1.0, record.confidence))
        access_bonus = min(0.08, math.log1p(max(0, record.access_count)) * 0.02)
        return coverage * 0.78 + specificity * 0.22 + phrase_bonus + importance_bonus + confidence_bonus + access_bonus

    def _mark_accessed(self, records: list[MemoryRecord]) -> None:
        if not records:
            return
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        self.db.conn.executemany(
            "UPDATE memories SET last_accessed_at=?, last_used_context_at=?, access_count=COALESCE(access_count,0)+1 WHERE id=?",
            [(now, now, r.id) for r in records],
        )
        self.db.conn.commit()

    def forget(self, raw: str, *, all_matches: bool = False) -> list[MemoryRecord]:
        raw = (raw or "").strip()
        if not raw:
            return []
        if raw.startswith("#"):
            raw = raw[1:]
        if raw.isdigit():
            record = self.get(int(raw))
            if not record:
                return []
            self.db.conn.execute("DELETE FROM memories WHERE id=?", (record.id,))
            self.db.conn.commit()
            return [record]

        matches = self.search(raw, limit=50 if all_matches else 1, include_sensitive=True)
        if not matches:
            return []
        chosen = matches if all_matches else matches[:1]
        self.db.conn.executemany("DELETE FROM memories WHERE id=?", [(r.id,) for r in chosen])
        self.db.conn.commit()
        return chosen

    def forget_all_profile_data(self) -> dict[str, int]:
        """Forget AURA's personal memory/continuity metadata, not user notes/tasks."""
        memory_count = int(self.db.conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
        session_count = int(self.db.conn.execute("SELECT COUNT(*) FROM conversation_sessions").fetchone()[0])
        pref_count = int(self.db.conn.execute(
            "SELECT COUNT(*) FROM preferences WHERE key LIKE 'relationship.%'"
        ).fetchone()[0])
        self.db.conn.execute("DELETE FROM memories")
        self.db.conn.execute("DELETE FROM conversation_sessions")
        self.db.conn.execute("DELETE FROM preferences WHERE key LIKE 'relationship.%'")
        self.db.conn.commit()
        self.last_context_ids = []
        self.last_visible_ids = []
        return {"memories": memory_count, "sessions": session_count, "relationship_preferences": pref_count}

    def explain_last_context(self) -> list[MemoryRecord]:
        ids = self.last_context_ids or self.last_visible_ids[:5]
        records = []
        for memory_id in ids:
            record = self.get(memory_id)
            if record:
                records.append(record)
        return records

    @staticmethod
    def render_for_prompt(records: list[MemoryRecord], *, compact: bool = False) -> str:
        if not records:
            if compact:
                return "MEMORY CONTEXT\n- Aucun souvenir pertinent."
            return "MEMOIRE LONG TERME PERTINENTE\n- Aucun souvenir pertinent n'a ete injecte pour ce message."
        if compact:
            lines = ["MEMORY CONTEXT", "Souvenirs locaux pertinents; n'invente rien au-dela :"]
            for rec in records:
                uncertainty = " (incertain)" if rec.confidence < 1.0 else ""
                lines.append(f"- {rec.content}{uncertainty}")
            return "\n".join(lines)
        lines = [
            "MEMOIRE LONG TERME PERTINENTE",
            "Ces elements viennent de la base locale AURA. Utilise-les uniquement s'ils sont pertinents.",
            "Ne transforme jamais un souvenir incertain en certitude et n'invente rien autour.",
        ]
        for rec in records:
            lines.append(
                f"- [memoire #{rec.id} | {rec.type} | importance {rec.importance}/5 | confiance {rec.confidence:.2f}] {rec.content}"
            )
        return "\n".join(lines)

    @staticmethod
    def source_label(record: MemoryRecord) -> str:
        if record.source == "explicit_user":
            return "tu me l'as demandé explicitement"
        if record.source.startswith("auto_"):
            return "je l'ai retenu à partir d'une préférence/habitude/projet formulé clairement"
        return f"source locale : {record.source}"

# AURA v0.8.7 - MemoryKernel v2 compatibility facade
from memory.kernel_v2 import MemoryKernelV2, MemoryRecordV2, MemoryScope, MemoryType


def _aura_v087_memorykernel_v2(self):
    kernel = getattr(self, "_aura_memorykernel_v2_instance", None)
    if kernel is None:
        kernel = MemoryKernelV2.from_legacy_manager(self)
        setattr(self, "_aura_memorykernel_v2_instance", kernel)
    return kernel


def _aura_v087_remember_v2(self, content, **kwargs):
    return self.memorykernel_v2.remember(content, **kwargs)


def _aura_v087_retrieve_v2(self, query="", **kwargs):
    return self.memorykernel_v2.retrieve(query, **kwargs)


def _aura_v087_update_v2(self, memory_id, **kwargs):
    return self.memorykernel_v2.update(memory_id, **kwargs)


def _aura_v087_merge_v2(self, source_ids, **kwargs):
    return self.memorykernel_v2.merge(source_ids, **kwargs)


def _aura_v087_forget_v2(self, memory_id):
    return self.memorykernel_v2.forget(memory_id)


def _aura_v087_expire_v2(self, **kwargs):
    return self.memorykernel_v2.expire(**kwargs)


MemoryManager.MEMORY_KERNEL_VERSION = "2"
MemoryManager.memorykernel_v2 = property(_aura_v087_memorykernel_v2)
MemoryManager.remember_v2 = _aura_v087_remember_v2
MemoryManager.retrieve_v2 = _aura_v087_retrieve_v2
MemoryManager.update_v2 = _aura_v087_update_v2
MemoryManager.merge_v2 = _aura_v087_merge_v2
MemoryManager.forget_v2 = _aura_v087_forget_v2
MemoryManager.expire_v2 = _aura_v087_expire_v2


# === AURA v2.1 Memory Kernel R7-R2 - compatibility + migration facade BEGIN ===
# MemoryManager remains a compatibility facade only. MemoryKernelV2 stays canonical.
import hashlib as _aura_v21_r7_hashlib
import json as _aura_v21_r7_json
import uuid as _aura_v21_r7_uuid

from runtime.aura_memory_v21_controlled_consolidation_bridge import (
    ConsolidationMapping as _AuraV21R7ConsolidationMapping,
    ControlledMemoryConsolidationBridge as _AuraV21R7Bridge,
)

def _aura_v21_r7_kernel(self):
    resolver = globals().get("_aura_v087_memorykernel_v2")
    if not callable(resolver):
        raise RuntimeError("canonical MemoryKernelV2 resolver is unavailable")
    kernel = resolver(self)
    if kernel.__class__.__name__ != "MemoryKernelV2":
        raise RuntimeError("resolved memory authority is not MemoryKernelV2")

    # R7-R2 repair:
    # A compatibility facade must never expose a half-initialized canonical kernel.
    # ensure_schema() is idempotent and keeps MemoryKernelV2 as the sole authority.
    kernel.ensure_schema()
    return kernel

def _aura_v21_r7_recall(
    self, query, *, scope="user", scope_id=None, at=None, limit=10,
    allow_user_fallback=True, max_relation_hops=1,
    include_sensitive=False, min_score=0.12,
):
    kernel = _aura_v21_r7_kernel(self)
    return kernel.v21_recall_graph(
        query,
        scope=scope,
        scope_id=scope_id,
        at=at,
        limit=limit,
        allow_user_fallback=allow_user_fallback,
        max_relation_hops=max_relation_hops,
        include_sensitive=include_sensitive,
        min_score=min_score,
    )

def _aura_v21_r7_explain_recall(self, recall_result):
    return _aura_v21_r7_kernel(self).v21_explain_recall(recall_result)

def _aura_v21_r7_bridge(self, store):
    return _AuraV21R7Bridge(_aura_v21_r7_kernel(self), store)

def _aura_v21_r7_mapping(mapping):
    if isinstance(mapping, _AuraV21R7ConsolidationMapping):
        return mapping
    if isinstance(mapping, dict):
        return _AuraV21R7ConsolidationMapping(**mapping)
    raise TypeError("mapping must be ConsolidationMapping or dict")

def _aura_v21_r7_preview_consolidation(self, store, candidate_id, mapping):
    bridge = _aura_v21_r7_bridge(self, store)
    candidate = bridge.candidate(candidate_id)
    return bridge.preview(candidate, _aura_v21_r7_mapping(mapping))

def _aura_v21_r7_consolidate_candidate(
    self, store, candidate_id, mapping, *, explicit_confirmation=False,
):
    return _aura_v21_r7_bridge(self, store).consolidate(
        candidate_id,
        _aura_v21_r7_mapping(mapping),
        explicit_confirmation=bool(explicit_confirmation),
    )

def _aura_v21_r7_db_conn(self):
    db = getattr(self, "db", None)
    conn = getattr(db, "conn", None)
    if conn is None:
        raise RuntimeError("legacy MemoryManager database connection unavailable")
    return conn

def _aura_v21_r7_legacy_columns(self):
    conn = _aura_v21_r7_db_conn(self)
    return [
        str(r["name"] if hasattr(r, "keys") else r[1])
        for r in conn.execute("PRAGMA table_info(memories)").fetchall()
    ]

def _aura_v21_r7_row_dict(row):
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {str(k): row[k] for k in row.keys()}
    raise RuntimeError("legacy row factory does not expose named columns")

def _aura_v21_r7_legacy_row(self, legacy_id):
    conn = _aura_v21_r7_db_conn(self)
    row = conn.execute(
        "SELECT * FROM memories WHERE id=? LIMIT 1",
        (int(legacy_id),),
    ).fetchone()
    if row is None:
        raise KeyError(legacy_id)
    return _aura_v21_r7_row_dict(row)

def _aura_v21_r7_stable_memory_id(legacy_id):
    return str(_aura_v21_r7_uuid.uuid5(
        _aura_v21_r7_uuid.NAMESPACE_URL,
        f"aura:legacy-memory:{int(legacy_id)}",
    ))

def _aura_v21_r7_type(value):
    raw = str(value or "").strip().casefold()
    if raw in {"preference", "pref", "style"}:
        return "preference"
    if raw in {"project", "goal", "objective"}:
        return "project"
    if raw in {"episodic", "event", "episode"}:
        return "episodic"
    return "semantic"

def _aura_v21_r7_existing_migration(self, memory_id):
    kernel = _aura_v21_r7_kernel(self)
    conn = kernel._connect()
    try:
        row = conn.execute(
            """
            SELECT memory_id, memory_type, scope, scope_id, content,
                   provenance_json, version, status, is_sensitive
            FROM memory_kernel_v2_records
            WHERE memory_id=?
            LIMIT 1
            """,
            (str(memory_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "memory_id": str(row["memory_id"]),
            "memory_type": str(row["memory_type"]),
            "scope": str(row["scope"]),
            "scope_id": str(row["scope_id"] or ""),
            "content": str(row["content"]),
            "provenance": _aura_v21_r7_json.loads(row["provenance_json"] or "{}"),
            "version": int(row["version"]),
            "status": str(row["status"]),
            "is_sensitive": bool(row["is_sensitive"]),
        }
    finally:
        conn.close()

def _aura_v21_r7_legacy_migration_plan(self, *, limit=100):
    # Bootstrap canonical schema before checking migration targets.
    _aura_v21_r7_kernel(self)

    conn = _aura_v21_r7_db_conn(self)
    columns = _aura_v21_r7_legacy_columns(self)
    if "id" not in columns or "content" not in columns:
        raise RuntimeError("legacy memories schema lacks id/content")

    status_clause = ""
    if "status" in columns:
        status_clause = " WHERE upper(coalesce(status,'ACTIVE'))='ACTIVE'"

    rows = conn.execute(
        "SELECT * FROM memories" + status_clause + " ORDER BY id ASC LIMIT ?",
        (max(1, min(int(limit), 1000)),),
    ).fetchall()

    items = []
    for raw in rows:
        row = _aura_v21_r7_row_dict(raw)
        legacy_id = int(row["id"])
        memory_id = _aura_v21_r7_stable_memory_id(legacy_id)
        existing = _aura_v21_r7_existing_migration(self, memory_id)
        content = str(row.get("content") or "")
        items.append({
            "legacy_id": legacy_id,
            "target_memory_id": memory_id,
            "legacy_type": row.get("type"),
            "target_memory_type": _aura_v21_r7_type(row.get("type")),
            "source": row.get("source"),
            "confidence": float(row.get("confidence") or 1.0),
            "is_sensitive": bool(row.get("is_sensitive") or False),
            "content_sha256": _aura_v21_r7_hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest(),
            "already_migrated": existing is not None,
            "migration_mode": "copy_forward_non_destructive",
            "normalization": "NOT_GUESSED",
        })

    return {
        "schema": "aura.memory-v21.legacy-migration-plan.v1",
        "count": len(items),
        "legacy_table_mutation": False,
        "automatic_bulk_migration": False,
        "items": items,
    }

def _aura_v21_r7_migrate_legacy_record(
    self, legacy_id, *, scope="user", scope_id=None,
    memory_type=None, explicit_confirmation=False,
):
    if explicit_confirmation is not True:
        raise PermissionError(
            "explicit_confirmation=True is required for legacy migration"
        )

    row = _aura_v21_r7_legacy_row(self, legacy_id)
    content = str(row.get("content") or "").strip()
    if not content:
        raise ValueError("legacy memory content is empty")

    memory_id = _aura_v21_r7_stable_memory_id(legacy_id)
    existing = _aura_v21_r7_existing_migration(self, memory_id)
    if existing is not None:
        return {
            "schema": "aura.memory-v21.legacy-migration-result.v1",
            "status": "already_migrated",
            "legacy_id": int(legacy_id),
            "memory_id": memory_id,
            "legacy_mutated": False,
            "idempotent": True,
            "record": existing,
        }

    target_type = str(
        memory_type or _aura_v21_r7_type(row.get("type"))
    ).strip().casefold()
    if target_type not in {"episodic", "semantic", "preference", "project"}:
        raise ValueError("unsupported target memory_type")

    confidence = max(0.0, min(1.0, float(row.get("confidence") or 1.0)))
    provenance = {
        "kernel": "MemoryKernelV2",
        "created_by": "legacy_copy_forward_r7",
        "legacy_table": "memories",
        "legacy_id": int(legacy_id),
        "legacy_type": row.get("type"),
        "legacy_source": row.get("source"),
        "legacy_confidence": confidence,
        "legacy_created_at": row.get("created_at"),
        "legacy_updated_at": row.get("updated_at"),
        "migration_mode": "copy_forward_non_destructive",
        "semantic_normalization_performed": False,
        "requires_future_controlled_normalization": True,
    }

    kernel = _aura_v21_r7_kernel(self)
    record = kernel.remember(
        content,
        memory_type=target_type,
        scope=scope,
        scope_id=scope_id,
        provenance=provenance,
        is_sensitive=bool(row.get("is_sensitive") or False),
        memory_id=memory_id,
    )

    return {
        "schema": "aura.memory-v21.legacy-migration-result.v1",
        "status": "migrated",
        "legacy_id": int(legacy_id),
        "memory_id": memory_id,
        "legacy_mutated": False,
        "idempotent": False,
        "record": {
            "memory_id": record.memory_id,
            "memory_type": record.memory_type.value,
            "scope": record.scope.value,
            "scope_id": record.scope_id,
            "content": record.content,
            "provenance": dict(record.provenance),
            "version": record.version,
            "status": record.status,
            "is_sensitive": bool(record.is_sensitive),
        },
    }

MemoryManager.v21_kernel = _aura_v21_r7_kernel
MemoryManager.v21_recall = _aura_v21_r7_recall
MemoryManager.v21_explain_recall = _aura_v21_r7_explain_recall
MemoryManager.v21_consolidation_bridge = _aura_v21_r7_bridge
MemoryManager.v21_preview_consolidation = _aura_v21_r7_preview_consolidation
MemoryManager.v21_consolidate_candidate = _aura_v21_r7_consolidate_candidate
MemoryManager.v21_legacy_migration_plan = _aura_v21_r7_legacy_migration_plan
MemoryManager.v21_migrate_legacy_record = _aura_v21_r7_migrate_legacy_record
# === AURA v2.1 Memory Kernel R7-R2 - compatibility + migration facade END ===
