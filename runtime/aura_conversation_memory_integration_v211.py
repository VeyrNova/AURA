from __future__ import annotations

"""
AURA v2.1.1 R3 — ConversationMemoryIntegration.

Deterministic conversation-to-memory adapter. This module classifies and
orchestrates only; MemoryKernelV2 remains the sole durable semantic authority.

R3 deliberately fails closed for UPDATE persistence until the canonical
supersession primitive is bound in the next gate. It never silently overwrites
or invents a second source of truth.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import calendar
import re
import unicodedata
import uuid
from typing import Any, Mapping


class ConversationMemoryError(RuntimeError):
    pass


class MemoryAuthorizationRequired(ConversationMemoryError):
    pass


class CanonicalUpdateBindingRequired(ConversationMemoryError):
    """Raised when UPDATE is classified but canonical supersession is not bound."""


@dataclass(frozen=True)
class MemoryFactCandidate:
    subject: str
    predicate: str
    object_text: str
    scope: str = "user"
    scope_id: str | None = None
    observed_at: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: float = 1.0
    explicit_user_authorization: bool = False
    correction_signal: bool = False
    source_text: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryDecision:
    operation: str
    candidate: MemoryFactCandidate | None
    existing_fact_ids: tuple[str, ...] = ()
    reason: str = ""
    requires_canonical_supersession: bool = False

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["existing_fact_ids"] = list(self.existing_fact_ids)
        return out


class ConversationMemoryIntegration:
    SCHEMA = "aura.v2.1.1.conversation-memory.integration.v1"
    OPERATIONS = {
        "NEW",
        "UPDATE",
        "CONTRADICTION",
        "TEMPORAL_TRANSITION",
        "UNCHANGED",
        "IGNORE",
    }

    _MONTHS = {
        "janvier": 1, "février": 2, "fevrier": 2, "mars": 3,
        "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
        "décembre": 12, "decembre": 12,
    }

    def __init__(self, memory_manager: Any):
        if memory_manager is None:
            raise ValueError("memory_manager is required")
        self.memory_manager = memory_manager
        kernel = memory_manager.v21_kernel()
        if kernel.__class__.__name__ != "MemoryKernelV2":
            raise RuntimeError("ConversationMemoryIntegration requires canonical MemoryKernelV2")
        self.kernel = kernel

    @staticmethod
    def _fold(value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", text).strip().casefold()

    @staticmethod
    def _clean(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n.,;:!?\"'")

    @classmethod
    def classify_explicit_memory_intent(cls, text: str) -> dict[str, Any]:
        raw = cls._clean(text)
        folded = cls._fold(raw)
        correction = bool(re.match(r"^(correction|rectification|mise a jour)\s*[:\-]", folded))
        remember = bool(re.match(
            r"^(retiens|retiens bien|souviens-toi|souviens toi|memorise|mémorise)\b",
            folded,
        ))
        return {
            "explicit_user_authorization": bool(correction or remember),
            "correction_signal": correction,
            "memory_command": bool(correction or remember),
        }

    @classmethod
    def _strip_command_prefix(cls, text: str) -> tuple[str, bool, bool]:
        raw = cls._clean(text)
        folded = cls._fold(raw)

        correction = False
        explicit = False

        if re.match(r"^(correction|rectification|mise a jour)\s*[:\-]", folded):
            correction = True
            explicit = True
            raw = re.sub(
                r"^\s*(?:correction|rectification|mise\s+[àa]\s+jour)\s*[:\-]\s*",
                "",
                raw,
                count=1,
                flags=re.I,
            )
        else:
            m = re.match(
                r"^\s*(?:retiens(?:\s+bien)?|souviens[\s-]*toi|m[ée]morise)\s+(?:que\s+)?",
                raw,
                flags=re.I,
            )
            if m:
                explicit = True
                raw = raw[m.end():]

        return cls._clean(raw), explicit, correction

    @classmethod
    def _month_interval(cls, month_name: str, year: str) -> tuple[str, str]:
        month = cls._MONTHS[cls._fold(month_name)]
        yr = int(year)
        last = calendar.monthrange(yr, month)[1]
        start = datetime(yr, month, 1, tzinfo=timezone.utc).isoformat()
        end = datetime(yr, month, last, 23, 59, 59, tzinfo=timezone.utc).isoformat()
        return start, end

    @classmethod
    def _extract_temporal_prefix(cls, statement: str) -> tuple[str, str | None, str | None]:
        # "En janvier 2026, X ..." -> bounded historical interval.
        m = re.match(
            r"^\s*En\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\s*,\s*(.+)$",
            statement,
            flags=re.I,
        )
        if m and cls._fold(m.group(1)) in cls._MONTHS:
            start, end = cls._month_interval(m.group(1), m.group(2))
            return cls._clean(m.group(3)), start, end

        # "Depuis septembre 2026, X ..." -> open-ended interval.
        m = re.match(
            r"^\s*Depuis\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})\s*,\s*(.+)$",
            statement,
            flags=re.I,
        )
        if m and cls._fold(m.group(1)) in cls._MONTHS:
            month = cls._MONTHS[cls._fold(m.group(1))]
            start = datetime(int(m.group(2)), month, 1, tzinfo=timezone.utc).isoformat()
            return cls._clean(m.group(3)), start, None

        return statement, None, None

    @classmethod
    def extract_explicit_fact(
        cls,
        text: str,
        *,
        scope: str = "user",
        scope_id: str | None = None,
        observed_at: str | None = None,
    ) -> MemoryFactCandidate | None:
        statement, explicit, correction = cls._strip_command_prefix(text)
        statement, valid_from, valid_to = cls._extract_temporal_prefix(statement)
        statement = cls._clean(statement)
        if not statement:
            return None

        subject = predicate = object_text = None

        patterns = [
            (
                r"^(?:la\s+)?version(?:\s+actuelle)?\s+de\s+(.+?)\s+est\s+(.+)$",
                "version",
            ),
            (
                r"^(?:le\s+)?code\s+de\s+(.+?)\s+est\s+(.+)$",
                "code",
            ),
            (
                r"^(?:la\s+)?couleur\s+de\s+(.+?)\s+est\s+(.+)$",
                "color",
            ),
            (
                r"^(.+?)\s+fonctionne\s+(?:uniquement\s+)?(?:en|dans\s+le|dans|sur)\s+(.+)$",
                "operating_mode",
            ),
            (
                r"^(.+?)\s+utilis(?:ait|e)\s+(?:le\s+)?moteur\s+(.+)$",
                "engine",
            ),
            (
                r"^(.+?)\s+a\s+pour\s+(?:version|code|couleur)\s+(.+)$",
                None,
            ),
        ]

        for pattern, fixed_predicate in patterns:
            m = re.match(pattern, statement, flags=re.I)
            if not m:
                continue
            subject = cls._clean(m.group(1))
            object_text = cls._clean(m.group(2))
            predicate = fixed_predicate
            if predicate is None:
                folded = cls._fold(statement)
                if " version " in f" {folded} ":
                    predicate = "version"
                elif " code " in f" {folded} ":
                    predicate = "code"
                elif " couleur " in f" {folded} ":
                    predicate = "color"
            break

        # Generic "SUBJECT est VALUE" fallback is intentionally conservative:
        # it uses predicate="attribute" only when the subject looks like a named entity.
        if not subject:
            m = re.match(r"^([A-Z0-9][A-Za-z0-9_.\- ]{1,80}?)\s+est\s+(.+)$", statement)
            if m:
                subject = cls._clean(m.group(1))
                predicate = "attribute"
                object_text = cls._clean(m.group(2))

        if not subject or not predicate or not object_text:
            return None

        now = observed_at or datetime.now(timezone.utc).isoformat()
        return MemoryFactCandidate(
            subject=subject,
            predicate=predicate,
            object_text=object_text,
            scope=scope,
            scope_id=scope_id,
            observed_at=now,
            valid_from=valid_from,
            valid_to=valid_to,
            confidence=1.0,
            explicit_user_authorization=explicit,
            correction_signal=correction,
            source_text=text,
            provenance={
                "kernel": "MemoryKernelV2",
                "source": "conversation_explicit_fact_v211",
                "adapter_schema": cls.SCHEMA,
                "source_text_present": True,
            },
        )

    def _scope_values(self, candidate: MemoryFactCandidate) -> tuple[str, str]:
        scope = self.kernel._scope(candidate.scope)
        scope_id = self.kernel._scope_id(scope, candidate.scope_id)
        return scope.value, scope_id

    def _find_entity(self, candidate: MemoryFactCandidate) -> dict[str, Any] | None:
        scope, scope_id = self._scope_values(candidate)
        conn = self.kernel._connect()
        try:
            row = conn.execute(
                """
                SELECT entity_id, entity_type, canonical_name, scope, scope_id, confidence
                FROM memory_v21_entities
                WHERE lower(canonical_name)=lower(?)
                  AND scope=? AND scope_id=? AND status='active'
                ORDER BY updated_at DESC LIMIT 1
                """,
                (candidate.subject, scope, scope_id),
            ).fetchone()
            if row is None:
                return None
            return {
                "entity_id": str(row["entity_id"]),
                "entity_type": str(row["entity_type"]),
                "canonical_name": str(row["canonical_name"]),
                "scope": str(row["scope"]),
                "scope_id": str(row["scope_id"]),
                "confidence": float(row["confidence"]),
            }
        finally:
            conn.close()

    def _existing_facts(self, candidate: MemoryFactCandidate) -> list[dict[str, Any]]:
        entity = self._find_entity(candidate)
        if entity is None:
            return []
        return self.kernel.v21_list_facts(
            subject_entity_id=entity["entity_id"],
            predicate=candidate.predicate,
            status="active",
            limit=500,
        )

    def classify_change(self, candidate: MemoryFactCandidate | None) -> MemoryDecision:
        if candidate is None:
            return MemoryDecision("IGNORE", None, (), "no deterministic fact extracted")

        existing = self._existing_facts(candidate)
        if not existing:
            return MemoryDecision("NEW", candidate, (), "no active canonical fact for subject/predicate")

        same = [
            f for f in existing
            if self._fold(f.get("object_text")) == self._fold(candidate.object_text)
        ]
        if same:
            return MemoryDecision(
                "UNCHANGED",
                candidate,
                tuple(str(f["fact_id"]) for f in same),
                "equivalent canonical fact already active",
            )

        ids = tuple(str(f["fact_id"]) for f in existing)

        if candidate.correction_signal:
            return MemoryDecision(
                "UPDATE",
                candidate,
                ids,
                "explicit correction signal supersedes current value",
                requires_canonical_supersession=True,
            )

        # Temporal transition wins only when every existing active value is
        # non-overlapping with the candidate interval.
        if candidate.valid_from or candidate.valid_to:
            overlaps = []
            for fact in existing:
                overlaps.append(
                    bool(self.kernel.v21_temporal_overlap(
                        fact.get("valid_from"),
                        fact.get("valid_to"),
                        candidate.valid_from,
                        candidate.valid_to,
                    ))
                )
            if overlaps and not any(overlaps):
                return MemoryDecision(
                    "TEMPORAL_TRANSITION",
                    candidate,
                    ids,
                    "different value has a non-overlapping validity interval",
                )

        return MemoryDecision(
            "CONTRADICTION",
            candidate,
            ids,
            "incompatible value overlaps existing canonical truth",
        )

    def plan_message(
        self,
        text: str,
        *,
        scope: str = "user",
        scope_id: str | None = None,
        observed_at: str | None = None,
    ) -> MemoryDecision:
        candidate = self.extract_explicit_fact(
            text,
            scope=scope,
            scope_id=scope_id,
            observed_at=observed_at,
        )
        return self.classify_change(candidate)

    @staticmethod
    def _stable_fact_key(candidate: MemoryFactCandidate) -> str:
        basis = (
            f"{candidate.scope}|{candidate.scope_id or ''}|"
            f"{candidate.subject.casefold()}|{candidate.predicate.casefold()}|"
            f"{candidate.object_text.casefold()}|{candidate.valid_from or ''}|"
            f"{candidate.valid_to or ''}"
        )
        return "v211:" + str(uuid.uuid5(uuid.NAMESPACE_URL, basis))

    def _ensure_entity(self, candidate: MemoryFactCandidate) -> dict[str, Any]:
        entity = self._find_entity(candidate)
        if entity is not None:
            return entity
        return self.kernel.v21_upsert_entity(
            candidate.subject,
            entity_type="conversation_subject",
            scope=candidate.scope,
            scope_id=candidate.scope_id,
            confidence=candidate.confidence,
        )

    def commit_explicit_fact(
        self,
        decision: MemoryDecision,
        *,
        explicit_user_authorization: bool | None = None,
    ) -> dict[str, Any]:
        if decision.operation not in self.OPERATIONS:
            raise ValueError("unknown memory operation")
        if decision.operation == "IGNORE":
            return {"status": "ignored", "operation": "IGNORE"}

        candidate = decision.candidate
        if candidate is None:
            raise ConversationMemoryError("decision has no candidate")

        authorized = (
            candidate.explicit_user_authorization
            if explicit_user_authorization is None
            else bool(explicit_user_authorization)
        )
        if not authorized:
            raise MemoryAuthorizationRequired(
                "durable conversation memory requires explicit user authorization or approved L170 route"
            )

        if decision.operation == "UPDATE":
            # R3 invariant: never degrade an explicit correction into a contradictory
            # append or a legacy overwrite. R4 must bind a canonical supersession
            # primitive before UPDATE can commit.
            raise CanonicalUpdateBindingRequired(
                "UPDATE correctly classified; canonical supersession binding required before commit"
            )

        if decision.operation == "UNCHANGED":
            return {
                "status": "unchanged",
                "operation": "UNCHANGED",
                "existing_fact_ids": list(decision.existing_fact_ids),
                "canonical_write": False,
            }

        entity = self._ensure_entity(candidate)
        stored = self.kernel.v21_store_temporal_fact(
            entity["entity_id"],
            candidate.predicate,
            object_text=candidate.object_text,
            fact_key=self._stable_fact_key(candidate),
            confidence=candidate.confidence,
            observed_at=candidate.observed_at,
            valid_from=candidate.valid_from,
            valid_to=candidate.valid_to,
            provenance={
                **dict(candidate.provenance),
                "conversation_operation": decision.operation,
                "explicit_user_authorization": True,
                "source_text_sha_only": True,
            },
        )

        fact = stored["fact"]
        conflicts = list(stored.get("conflicts") or [])

        if decision.operation == "CONTRADICTION" and not conflicts:
            raise ConversationMemoryError(
                "contradiction classified but canonical kernel produced no conflict ledger entry"
            )
        if decision.operation == "TEMPORAL_TRANSITION" and conflicts:
            raise ConversationMemoryError(
                "non-overlapping temporal transition unexpectedly produced a conflict"
            )

        return {
            "status": "committed",
            "operation": decision.operation,
            "entity_id": entity["entity_id"],
            "fact": fact,
            "conflicts": conflicts,
            "canonical_write": True,
            "authority": "MemoryKernelV2",
        }

    def recall_for_conversation(
        self,
        query: str,
        *,
        scope: str = "user",
        scope_id: str | None = None,
        at: str | None = None,
        limit: int = 10,
        include_sensitive: bool = False,
        allow_user_fallback: bool = True,
    ) -> dict[str, Any]:
        return self.memory_manager.v21_recall(
            query,
            scope=scope,
            scope_id=scope_id,
            at=at,
            limit=limit,
            include_sensitive=include_sensitive,
            allow_user_fallback=allow_user_fallback,
        )

    def explain_recall(self, recall_result: Mapping[str, Any]) -> list[dict[str, Any]]:
        return self.memory_manager.v21_explain_recall(recall_result)

# === AURA v2.1.1 R4 canonical UPDATE supersession BEGIN ===
# Extends R3 orchestration only. MemoryKernelV2 remains the sole durable authority.

_AURA_V211_R4_PREVIOUS_COMMIT_EXPLICIT_FACT = ConversationMemoryIntegration.commit_explicit_fact


def _aura_v211_r4_commit_explicit_fact(
    self,
    decision: MemoryDecision,
    *,
    explicit_user_authorization: bool | None = None,
) -> dict[str, Any]:
    if decision.operation != "UPDATE":
        return _AURA_V211_R4_PREVIOUS_COMMIT_EXPLICIT_FACT(
            self,
            decision,
            explicit_user_authorization=explicit_user_authorization,
        )

    candidate = decision.candidate
    if candidate is None:
        raise ConversationMemoryError("UPDATE decision has no candidate")

    authorized = (
        candidate.explicit_user_authorization
        if explicit_user_authorization is None
        else bool(explicit_user_authorization)
    )
    if not authorized:
        raise MemoryAuthorizationRequired(
            "durable conversation UPDATE requires explicit user authorization"
        )

    if not decision.existing_fact_ids:
        raise ConversationMemoryError(
            "UPDATE requires at least one existing canonical fact"
        )

    entity = self._ensure_entity(candidate)

    # First append the new value through the already-certified temporal/conflict
    # primitive. An explicit UPDATE is then resolved in favor of the new fact.
    stored = self.kernel.v21_store_temporal_fact(
        entity["entity_id"],
        candidate.predicate,
        object_text=candidate.object_text,
        fact_key=self._stable_fact_key(candidate),
        confidence=candidate.confidence,
        observed_at=candidate.observed_at,
        valid_from=candidate.valid_from,
        valid_to=candidate.valid_to,
        provenance={
            **dict(candidate.provenance),
            "conversation_operation": "UPDATE",
            "explicit_user_authorization": True,
            "canonical_supersession": True,
            "supersedes_fact_ids": list(decision.existing_fact_ids),
        },
    )

    new_fact = stored["fact"]
    new_fact_id = str(new_fact["fact_id"])
    conflicts = list(stored.get("conflicts") or [])

    if not conflicts:
        raise ConversationMemoryError(
            "UPDATE produced no canonical conflict; refusing silent supersession"
        )

    resolved = []
    resolved_old_ids = set()

    for conflict in conflicts:
        left_id = str(conflict["left_fact_id"])
        right_id = str(conflict["right_fact_id"])

        if new_fact_id == right_id:
            resolution = "keep_right"
            loser = left_id
        elif new_fact_id == left_id:
            resolution = "keep_left"
            loser = right_id
        else:
            raise ConversationMemoryError(
                "UPDATE conflict does not include newly created fact"
            )

        row = self.kernel.v21_resolve_conflict(
            conflict["conflict_id"],
            resolution=resolution,
            note="explicit conversation correction/update",
        )
        resolved.append(row)
        resolved_old_ids.add(loser)

    expected_old = set(str(x) for x in decision.existing_fact_ids)
    missing = expected_old - resolved_old_ids
    if missing:
        raise ConversationMemoryError(
            "UPDATE did not canonically supersede all previous current facts: "
            + ", ".join(sorted(missing))
        )

    refreshed = self.kernel.v21_fact_by_id(new_fact_id)
    if not refreshed or refreshed.get("status") != "active":
        raise ConversationMemoryError("new UPDATE fact is not active after resolution")

    for old_id in expected_old:
        old = self.kernel.v21_fact_by_id(old_id)
        if old is None or old.get("status") != "superseded":
            raise ConversationMemoryError(
                f"previous canonical fact {old_id} was not superseded"
            )

    open_conflicts = {
        str(row["conflict_id"])
        for row in self.kernel.v21_list_conflicts(state="open", limit=500)
    }
    unresolved = [
        str(row["conflict_id"])
        for row in resolved
        if str(row["conflict_id"]) in open_conflicts
    ]
    if unresolved:
        raise ConversationMemoryError(
            "UPDATE left conflict(s) open: " + ", ".join(unresolved)
        )

    return {
        "status": "updated",
        "operation": "UPDATE",
        "entity_id": entity["entity_id"],
        "fact": refreshed,
        "superseded_fact_ids": sorted(expected_old),
        "resolved_conflicts": resolved,
        "canonical_write": True,
        "authority": "MemoryKernelV2",
    }


ConversationMemoryIntegration.commit_explicit_fact = _aura_v211_r4_commit_explicit_fact
# === AURA v2.1.1 R4 canonical UPDATE supersession END ===

# === AURA v2.1.1 R6 canonical answers + explainability BEGIN ===
import json as _aura_v211_r6_json


def _aura_v211_r6_fold(value: Any) -> str:
    return ConversationMemoryIntegration._fold(value)


def _aura_v211_r6_provenance(fact: Mapping[str, Any]) -> dict[str, Any]:
    value = fact.get("provenance")
    if isinstance(value, dict):
        return dict(value)
    value = fact.get("provenance_json")
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            decoded = _aura_v211_r6_json.loads(value)
            if isinstance(decoded, dict):
                return decoded
        except Exception:
            pass
    return {}


def _aura_v211_r6_conflict_flag(row: Mapping[str, Any]) -> bool:
    if bool(row.get("open_conflict")):
        return True
    for key in ("open_conflicts", "conflicts"):
        value = row.get(key)
        if isinstance(value, (list, tuple, set)) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


def _aura_v211_r6_predicate_label(predicate: str) -> str:
    labels = {
        "version": "version",
        "code": "code",
        "color": "couleur",
        "operating_mode": "mode de fonctionnement",
        "engine": "moteur",
        "attribute": "information",
    }
    return labels.get(str(predicate or "").strip(), str(predicate or "information"))



_AURA_V211_R6R3_STOPWORDS = {
    "alors", "avec", "cette", "dans", "depuis", "des", "elle", "elles",
    "est", "et", "faire", "fait", "fois", "ils", "les", "leur", "leurs",
    "mais", "mes", "mon", "nos", "notre", "nous", "par", "pas", "plus",
    "pour", "que", "quel", "quelle", "quels", "quelles", "qui", "quoi",
    "sans", "ses", "son", "sont", "sur", "tes", "ton", "tous", "tout",
    "toute", "toutes", "une", "vos", "votre", "vous", "actuel",
    "actuelle", "actuellement", "sais", "sais-tu", "souviens", "rappelle",
    "memoire", "mémoire", "information", "informations",
}


def _aura_v211_r6r3_tokens(value: Any) -> set[str]:
    folded = _aura_v211_r6_fold(value)
    raw = re.findall(r"[a-z0-9][a-z0-9_.-]{1,}", folded)
    return {
        token
        for token in raw
        if len(token) >= 3 and token not in _AURA_V211_R6R3_STOPWORDS
    }


def _aura_v211_r6r3_predicate_tokens(predicate: str) -> set[str]:
    mapping = {
        "version": {"version"},
        "code": {"code"},
        "color": {"couleur", "color"},
        "operating_mode": {"mode", "fonctionnement", "local", "cloud"},
        "engine": {"moteur", "engine"},
        "attribute": set(),
    }
    return mapping.get(str(predicate or "").strip(), _aura_v211_r6r3_tokens(predicate))


def _aura_v211_r6r3_row_relevant(query: str, row: Mapping[str, Any]) -> bool:
    fact = dict(row.get("fact") or {})
    entity = dict(row.get("entity") or {})

    subject = str(
        entity.get("canonical_name")
        or entity.get("name")
        or fact.get("subject")
        or ""
    ).strip()
    predicate = str(fact.get("predicate") or "").strip()
    value = str(
        fact.get("object_text")
        or fact.get("value")
        or fact.get("content")
        or ""
    ).strip()

    q_fold = _aura_v211_r6_fold(query)
    s_fold = _aura_v211_r6_fold(subject)

    # Strongest signal: the user explicitly names the canonical subject.
    if s_fold and len(s_fold) >= 3 and s_fold in q_fold:
        return True

    q_tokens = _aura_v211_r6r3_tokens(query)
    s_tokens = _aura_v211_r6r3_tokens(subject)
    v_tokens = _aura_v211_r6r3_tokens(value)
    p_tokens = _aura_v211_r6r3_predicate_tokens(predicate)

    subject_overlap = q_tokens & s_tokens
    value_overlap = q_tokens & v_tokens
    predicate_overlap = q_tokens & p_tokens

    # A predicate word alone ("version", "code", ...) is insufficient:
    # require a subject/value anchor too.
    if predicate_overlap and (subject_overlap or value_overlap):
        return True

    # Two meaningful lexical anchors are enough for a free-form canonical
    # question, but one generic token is deliberately rejected.
    semantic_overlap = q_tokens & (s_tokens | v_tokens | p_tokens)
    if len(semantic_overlap) >= 2:
        return True

    return False



def _aura_v211_r6_answer_personal_query(
    self,
    query: str,
    *,
    scope: str = "user",
    scope_id: str | None = None,
    at: str | None = None,
    limit: int = 12,
    include_sensitive: bool = False,
) -> dict[str, Any]:
    if bool(getattr(self.memory_manager, "private_mode", False)):
        result = {
            "schema": "aura.v2.1.1.canonical-memory-answer.v1",
            "status": "private",
            "answer": None,
            "canonical": True,
        }
        self._aura_v211_r6_last_answer = result
        return result

    try:
        recall = self.recall_for_conversation(
            str(query or ""),
            scope=scope,
            scope_id=scope_id,
            at=at,
            limit=max(1, int(limit or 12)),
            include_sensitive=bool(include_sensitive),
            allow_user_fallback=(scope != "project"),
        )
        explanation = self.explain_recall(recall)
    except Exception as exc:
        result = {
            "schema": "aura.v2.1.1.canonical-memory-answer.v1",
            "status": "canonical_error",
            "answer": None,
            "canonical": True,
            "error_type": type(exc).__name__,
        }
        self._aura_v211_r6_last_answer = result
        return result

    rows = list((recall or {}).get("results") or [])
    if not rows:
        result = {
            "schema": "aura.v2.1.1.canonical-memory-answer.v1",
            "status": "empty",
            "answer": None,
            "canonical": True,
            "reason": "no_canonical_results",
            "recall": recall,
            "explanation": explanation,
        }
        self._aura_v211_r6_last_answer = result
        return result

    # R6-R3: graph recall can legitimately return low-score candidates.
    # Direct personal answers have a stricter contract: a canonical row must
    # be deterministically relevant to the user's question before it is
    # allowed to suppress the legacy compatibility fallback.
    relevant_rows = [
        row for row in rows
        if _aura_v211_r6r3_row_relevant(str(query or ""), row)
    ]
    if not relevant_rows:
        result = {
            "schema": "aura.v2.1.1.canonical-memory-answer.v1",
            "status": "empty",
            "answer": None,
            "canonical": True,
            "reason": "no_relevant_canonical_results",
            "recall": recall,
            "explanation": explanation,
        }
        self._aura_v211_r6_last_answer = result
        return result

    rows = relevant_rows
    primary = rows[0]
    primary_fact = dict(primary.get("fact") or {})
    primary_entity = dict(primary.get("entity") or {})

    subject = str(
        primary_entity.get("canonical_name")
        or primary_entity.get("name")
        or primary_fact.get("subject")
        or "ce sujet"
    ).strip()
    predicate = str(primary_fact.get("predicate") or "information").strip()
    entity_id = (
        primary_entity.get("entity_id")
        or primary_fact.get("subject_entity_id")
    )

    same_group = []
    for row in rows:
        fact = dict(row.get("fact") or {})
        entity = dict(row.get("entity") or {})
        row_subject = str(
            entity.get("canonical_name")
            or entity.get("name")
            or fact.get("subject")
            or ""
        ).strip()
        if (
            _aura_v211_r6_fold(row_subject) == _aura_v211_r6_fold(subject)
            and str(fact.get("predicate") or "").strip() == predicate
        ):
            same_group.append(row)

    has_conflict = any(_aura_v211_r6_conflict_flag(row) for row in same_group)

    # When recall reports an open conflict, rebuild the conflict values from the
    # canonical ledger so the answer cannot omit the other side of the conflict.
    conflict_fact_ids: set[str] = set()
    if has_conflict and entity_id:
        try:
            active = self.kernel.v21_list_facts(
                subject_entity_id=str(entity_id),
                predicate=predicate,
                status="active",
                limit=500,
            )
            active_by_id = {
                str(f["fact_id"]): f
                for f in active
            }
            for conflict in self.kernel.v21_list_conflicts(state="open", limit=500):
                left = str(conflict.get("left_fact_id") or "")
                right = str(conflict.get("right_fact_id") or "")
                if left in active_by_id or right in active_by_id:
                    if left in active_by_id:
                        conflict_fact_ids.add(left)
                    if right in active_by_id:
                        conflict_fact_ids.add(right)

            if conflict_fact_ids:
                rebuilt = []
                for fid in sorted(conflict_fact_ids):
                    fact = active_by_id.get(fid)
                    if fact is None:
                        continue
                    rebuilt.append({
                        "fact": fact,
                        "entity": {
                            "entity_id": str(entity_id),
                            "canonical_name": subject,
                        },
                        "open_conflict": True,
                    })
                if rebuilt:
                    same_group = rebuilt
        except Exception:
            pass

    values = []
    selected = []
    seen_values = set()

    for row in same_group:
        fact = dict(row.get("fact") or {})
        value = str(
            fact.get("object_text")
            or fact.get("value")
            or fact.get("content")
            or ""
        ).strip()
        if not value:
            continue
        folded = _aura_v211_r6_fold(value)
        if folded in seen_values:
            continue
        seen_values.add(folded)
        values.append(value)

        provenance = _aura_v211_r6_provenance(fact)
        selected.append({
            "fact_id": str(fact.get("fact_id") or ""),
            "subject": subject,
            "predicate": predicate,
            "value": value,
            "confidence": fact.get("confidence"),
            "valid_from": fact.get("valid_from"),
            "valid_to": fact.get("valid_to"),
            "source": (
                provenance.get("source")
                or provenance.get("created_by")
                or provenance.get("conversation_operation")
                or "MemoryKernelV2"
            ),
            "provenance": provenance,
            "open_conflict": bool(has_conflict),
        })

    if not values:
        result = {
            "schema": "aura.v2.1.1.canonical-memory-answer.v1",
            "status": "empty",
            "answer": None,
            "canonical": True,
            "recall": recall,
            "explanation": explanation,
        }
        self._aura_v211_r6_last_answer = result
        return result

    label = _aura_v211_r6_predicate_label(predicate)

    if has_conflict and len(values) >= 2:
        joined = " ; ".join(values)
        answer = (
            f"Ma mémoire canonique contient des informations contradictoires "
            f"pour {subject} ({label}) : {joined}. "
            "Je conserve ces versions comme conflit ouvert et je ne choisis pas "
            "arbitrairement laquelle est vraie."
        )
    else:
        answer = (
            f"Dans ma mémoire canonique, {subject} — {label} = {values[0]}."
        )

    result = {
        "schema": "aura.v2.1.1.canonical-memory-answer.v1",
        "status": "answered",
        "answer": answer,
        "canonical": True,
        "conflict": bool(has_conflict and len(values) >= 2),
        "subject": subject,
        "predicate": predicate,
        "values": values,
        "selected": selected,
        "recall": recall,
        "explanation": explanation,
    }
    self._aura_v211_r6_last_answer = result
    return result


def _aura_v211_r6_can_answer_personal_query(
    self,
    query: str,
    *,
    scope: str = "user",
    scope_id: str | None = None,
) -> bool:
    result = self.answer_personal_query(
        query,
        scope=scope,
        scope_id=scope_id,
        limit=8,
        include_sensitive=False,
    )
    if result.get("status") != "answered":
        return False

    folded_query = _aura_v211_r6_fold(query)
    subject = _aura_v211_r6_fold(result.get("subject"))

    explicit_markers = (
        "souviens",
        "memoire",
        "mémoire",
        "rappelle",
        "que sais-tu",
        "que sais tu",
        "quel est",
        "quelle est",
        "quels sont",
        "quelles sont",
        "version",
        "code",
        "couleur",
        "moteur",
        "mode de fonctionnement",
    )
    if subject and subject in folded_query:
        return True
    return any(_aura_v211_r6_fold(marker) in folded_query for marker in explicit_markers)


def _aura_v211_r6_explain_last_answer(self) -> str | None:
    last = getattr(self, "_aura_v211_r6_last_answer", None)
    if not isinstance(last, dict) or last.get("status") != "answered":
        return None

    selected = list(last.get("selected") or [])
    if not selected:
        return (
            "J'ai utilisé la mémoire canonique MemoryKernelV2, "
            "mais je n'ai pas de détail de provenance supplémentaire."
        )

    if last.get("conflict"):
        prefix = (
            "J'ai utilisé MemoryKernelV2. Le rappel canonique signale un conflit "
            "ouvert, donc je conserve les valeurs contradictoires au lieu d'en "
            "inventer une comme vérité."
        )
    else:
        prefix = (
            "J'ai utilisé MemoryKernelV2 parce que ce souvenir est le fait "
            "canonique actif le plus pertinent pour ta question."
        )

    details = []
    for item in selected[:4]:
        parts = [
            f"{item.get('subject')} / "
            f"{_aura_v211_r6_predicate_label(item.get('predicate'))} = "
            f"{item.get('value')}"
        ]
        source = item.get("source")
        if source:
            parts.append(f"source={source}")
        confidence = item.get("confidence")
        if confidence is not None:
            try:
                parts.append(f"confiance={float(confidence):.2f}")
            except Exception:
                pass
        if item.get("valid_from"):
            parts.append(f"valide_depuis={item.get('valid_from')}")
        if item.get("valid_to"):
            parts.append(f"valide_jusqu_a={item.get('valid_to')}")
        details.append(" ; ".join(parts))

    return prefix + " " + " | ".join(details)


ConversationMemoryIntegration.answer_personal_query = _aura_v211_r6_answer_personal_query
ConversationMemoryIntegration.can_answer_personal_query = _aura_v211_r6_can_answer_personal_query
ConversationMemoryIntegration.explain_last_answer = _aura_v211_r6_explain_last_answer
# === AURA v2.1.1 R6 canonical answers + explainability END ===

# === AURA v2.1.1 R7-D2 live routing repair BEGIN ===
# Direct-answer predicate selection + shared ephemeral explainability evidence.

_AURA_V211_D2_PREVIOUS_ROW_RELEVANT = _aura_v211_r6r3_row_relevant
_AURA_V211_D2_PREVIOUS_ANSWER_PERSONAL = ConversationMemoryIntegration.answer_personal_query
_AURA_V211_D2_PREVIOUS_EXPLAIN_LAST = ConversationMemoryIntegration.explain_last_answer

_AURA_V211_D2_QUERY_PREDICATES = {
    "version": {"version"},
    "code": {"code"},
    "color": {"couleur", "color"},
    "operating_mode": {"mode", "fonctionnement", "local", "cloud"},
    "engine": {"moteur", "engine"},
}


def _aura_v211_d2_query_predicates(query: str) -> set[str]:
    q_tokens = _aura_v211_r6r3_tokens(query)
    wanted = set()
    for predicate, markers in _AURA_V211_D2_QUERY_PREDICATES.items():
        if q_tokens & markers:
            wanted.add(predicate)
    return wanted


def _aura_v211_d2_row_relevant(query: str, row: Mapping[str, Any]) -> bool:
    fact = dict(row.get("fact") or {})
    predicate = str(fact.get("predicate") or "").strip()
    wanted = _aura_v211_d2_query_predicates(query)

    if wanted and predicate not in wanted:
        return False

    return _AURA_V211_D2_PREVIOUS_ROW_RELEVANT(query, row)


def _aura_v211_d2_answer_personal_query(self, *args, **kwargs):
    result = _AURA_V211_D2_PREVIOUS_ANSWER_PERSONAL(self, *args, **kwargs)
    try:
        self._aura_v211_r6_last_answer = result
        setattr(self.memory_manager, "_aura_v211_last_canonical_answer", result)
    except Exception:
        pass
    return result


def _aura_v211_d2_explain_last_answer(self) -> str | None:
    try:
        shared = getattr(self.memory_manager, "_aura_v211_last_canonical_answer", None)
        if isinstance(shared, dict):
            self._aura_v211_r6_last_answer = shared
    except Exception:
        pass
    return _AURA_V211_D2_PREVIOUS_EXPLAIN_LAST(self)


_aura_v211_r6r3_row_relevant = _aura_v211_d2_row_relevant
ConversationMemoryIntegration.answer_personal_query = _aura_v211_d2_answer_personal_query
ConversationMemoryIntegration.explain_last_answer = _aura_v211_d2_explain_last_answer
# === AURA v2.1.1 R7-D2 live routing repair END ===
