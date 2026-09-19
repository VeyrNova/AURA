"""AURA v0.8.8 canonical Mission Engine.

Goal -> Plan -> TaskGraph -> ToolExecution -> Evidence -> Recovery -> Completion.

The engine owns mission state, DAG semantics, evidence and recovery.
Existing routers/tools are injected as execution adapters.
SecurityPolicyEngine v2 remains the authorization authority.
MemoryKernel v2 may supply planning context but is never execution evidence.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence


MISSION_STATES = (
    "draft", "planned", "ready", "running", "waiting_confirmation",
    "blocked", "recovering", "completed", "failed", "cancelled",
)

TASK_STATES = (
    "pending", "ready", "running", "waiting_confirmation",
    "succeeded", "failed", "skipped", "cancelled",
)

TERMINAL_TASK_STATES = {"succeeded", "failed", "skipped", "cancelled"}
TERMINAL_MISSION_STATES = {"completed", "failed", "cancelled"}

ALLOW = "ALLOW"
DENY = "DENY"
REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"


class MissionError(RuntimeError):
    pass


class MissionStateError(MissionError):
    pass


class MissionGraphError(MissionError):
    pass


class MissionPolicyError(MissionError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _deterministic_id(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha256(_canonical_json(parts).encode("utf-8")).hexdigest()[:20]


def _normalize_decision(value: Any) -> str:
    if value is None:
        return DENY
    candidates = (getattr(value, "name", None), getattr(value, "value", None), value)
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).upper().strip()
        for expected in (ALLOW, DENY, REQUIRE_CONFIRMATION):
            if text == expected or text.endswith("." + expected):
                return expected
    return DENY


@dataclass(frozen=True)
class Goal:
    goal_id: str
    text: str
    success_criteria: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolCall:
    tool_name: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskDependency:
    upstream_task_id: str
    downstream_task_id: str


@dataclass(frozen=True)
class TaskEvidence:
    evidence_id: str
    mission_id: str
    task_id: str
    kind: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class MissionEvent:
    event_id: str
    mission_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: str


@dataclass
class Task:
    task_id: str
    key: str
    title: str
    tool_call: ToolCall
    dependencies: list[str] = field(default_factory=list)
    required: bool = True
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 2
    result: Any = None
    error: Optional[str] = None
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "key": self.key,
            "title": self.title,
            "tool_call": {
                "tool_name": self.tool_call.tool_name,
                "action": self.tool_call.action,
                "params": dict(self.tool_call.params),
            },
            "dependencies": list(self.dependencies),
            "required": self.required,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "result": self.result,
            "error": self.error,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Task":
        tc = value["tool_call"]
        return cls(
            task_id=str(value["task_id"]),
            key=str(value["key"]),
            title=str(value["title"]),
            tool_call=ToolCall(
                tool_name=str(tc["tool_name"]),
                action=str(tc["action"]),
                params=dict(tc.get("params") or {}),
            ),
            dependencies=list(value.get("dependencies") or []),
            required=bool(value.get("required", True)),
            status=str(value.get("status", "pending")),
            attempts=int(value.get("attempts", 0)),
            max_attempts=int(value.get("max_attempts", 2)),
            result=value.get("result"),
            error=value.get("error"),
            evidence_ids=list(value.get("evidence_ids") or []),
        )


@dataclass(frozen=True)
class Plan:
    plan_id: str
    mission_id: str
    task_ids: tuple[str, ...]
    revision: int = 1


@dataclass
class Mission:
    mission_id: str
    goal: Goal
    status: str = "draft"
    plan: Optional[Plan] = None
    tasks: dict[str, Task] = field(default_factory=dict)
    evidence: dict[str, TaskEvidence] = field(default_factory=dict)
    events: list[MissionEvent] = field(default_factory=list)
    planning_context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "goal": {
                "goal_id": self.goal.goal_id,
                "text": self.goal.text,
                "success_criteria": list(self.goal.success_criteria),
            },
            "status": self.status,
            "plan": None if self.plan is None else {
                "plan_id": self.plan.plan_id,
                "mission_id": self.plan.mission_id,
                "task_ids": list(self.plan.task_ids),
                "revision": self.plan.revision,
            },
            "tasks": {key: task.to_dict() for key, task in self.tasks.items()},
            "evidence": {
                key: {
                    "evidence_id": ev.evidence_id,
                    "mission_id": ev.mission_id,
                    "task_id": ev.task_id,
                    "kind": ev.kind,
                    "payload": dict(ev.payload),
                    "created_at": ev.created_at,
                }
                for key, ev in self.evidence.items()
            },
            "events": [
                {
                    "event_id": ev.event_id,
                    "mission_id": ev.mission_id,
                    "event_type": ev.event_type,
                    "payload": dict(ev.payload),
                    "created_at": ev.created_at,
                }
                for ev in self.events
            ],
            "planning_context": dict(self.planning_context),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Mission":
        gv = value["goal"]
        goal = Goal(
            goal_id=str(gv["goal_id"]),
            text=str(gv["text"]),
            success_criteria=tuple(gv.get("success_criteria") or ()),
        )

        pv = value.get("plan")
        plan = None
        if pv:
            plan = Plan(
                plan_id=str(pv["plan_id"]),
                mission_id=str(pv["mission_id"]),
                task_ids=tuple(pv.get("task_ids") or ()),
                revision=int(pv.get("revision", 1)),
            )

        tasks = {str(k): Task.from_dict(v) for k, v in (value.get("tasks") or {}).items()}

        evidence = {}
        for key, ev in (value.get("evidence") or {}).items():
            evidence[str(key)] = TaskEvidence(
                evidence_id=str(ev["evidence_id"]),
                mission_id=str(ev["mission_id"]),
                task_id=str(ev["task_id"]),
                kind=str(ev["kind"]),
                payload=dict(ev.get("payload") or {}),
                created_at=str(ev["created_at"]),
            )

        events = [
            MissionEvent(
                event_id=str(ev["event_id"]),
                mission_id=str(ev["mission_id"]),
                event_type=str(ev["event_type"]),
                payload=dict(ev.get("payload") or {}),
                created_at=str(ev["created_at"]),
            )
            for ev in (value.get("events") or [])
        ]

        return cls(
            mission_id=str(value["mission_id"]),
            goal=goal,
            status=str(value.get("status", "draft")),
            plan=plan,
            tasks=tasks,
            evidence=evidence,
            events=events,
            planning_context=dict(value.get("planning_context") or {}),
            created_at=str(value.get("created_at") or _utc_now()),
            updated_at=str(value.get("updated_at") or _utc_now()),
        )


class SQLiteMissionStore:
    """Companion persistence. D2 uses synthetic temporary DB files only."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS mission_engine_missions (
                    mission_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_engine_events (
                    event_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mission_engine_events_mission
                    ON mission_engine_events(mission_id, created_at);
                CREATE TABLE IF NOT EXISTS mission_engine_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mission_engine_evidence_task
                    ON mission_engine_evidence(mission_id, task_id, created_at);
                """
            )

    def save(self, mission: Mission) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO mission_engine_missions(mission_id, state, snapshot_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(mission_id) DO UPDATE SET
                    state=excluded.state,
                    snapshot_json=excluded.snapshot_json,
                    updated_at=excluded.updated_at
                """,
                (mission.mission_id, mission.status, _canonical_json(mission.to_dict()), mission.updated_at),
            )
            for ev in mission.events:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO mission_engine_events
                    (event_id, mission_id, event_type, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (ev.event_id, ev.mission_id, ev.event_type, _canonical_json(ev.payload), ev.created_at),
                )
            for ev in mission.evidence.values():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO mission_engine_evidence
                    (evidence_id, mission_id, task_id, kind, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ev.evidence_id, ev.mission_id, ev.task_id, ev.kind, _canonical_json(ev.payload), ev.created_at),
                )

    def load(self, mission_id: str) -> Optional[Mission]:
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT snapshot_json FROM mission_engine_missions WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
        return None if row is None else Mission.from_dict(json.loads(row["snapshot_json"]))

    def count(self) -> int:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM mission_engine_missions").fetchone()
        return int(row["n"])


class MissionEngine:
    """Canonical mission state, DAG, evidence and recovery authority."""

    def __init__(
        self,
        *,
        security_engine: Any,
        tool_executor: Callable[[ToolCall], Any],
        store: Optional[SQLiteMissionStore] = None,
        planning_context_provider: Optional[Callable[[Goal], Mapping[str, Any]]] = None,
    ):
        self.security_engine = security_engine
        self.tool_executor = tool_executor
        self.store = store
        self.planning_context_provider = planning_context_provider
        self._missions: dict[str, Mission] = {}

    def _mission(self, mission_id: str) -> Mission:
        mission = self._missions.get(mission_id)
        if mission is None and self.store is not None:
            mission = self.store.load(mission_id)
            if mission is not None:
                self._missions[mission_id] = mission
        if mission is None:
            raise KeyError(mission_id)
        return mission

    def _persist(self, mission: Mission) -> None:
        mission.updated_at = _utc_now()
        self._missions[mission.mission_id] = mission
        if self.store is not None:
            self.store.save(mission)

    def _event(self, mission: Mission, event_type: str, payload: Mapping[str, Any]) -> MissionEvent:
        seq = len(mission.events) + 1
        event = MissionEvent(
            event_id=_deterministic_id("evt_", mission.mission_id, seq, event_type, payload),
            mission_id=mission.mission_id,
            event_type=event_type,
            payload=dict(payload),
            created_at=_utc_now(),
        )
        mission.events.append(event)
        return event

    def create_mission(self, goal_text: str, success_criteria: Sequence[str] = ()) -> Mission:
        goal_text = str(goal_text).strip()
        if not goal_text:
            raise ValueError("goal_text is required")
        criteria = tuple(str(x).strip() for x in success_criteria if str(x).strip())
        goal_id = _deterministic_id("goal_", goal_text, criteria)
        mission_id = _deterministic_id("mis_", goal_id)

        existing = self._missions.get(mission_id)
        if existing is None and self.store is not None:
            existing = self.store.load(mission_id)
        if existing is not None:
            self._missions[mission_id] = existing
            return existing

        mission = Mission(
            mission_id=mission_id,
            goal=Goal(goal_id=goal_id, text=goal_text, success_criteria=criteria),
        )
        self._event(mission, "mission_created", {"goal_id": goal_id})
        self._persist(mission)
        return mission

    def _build_tasks(
        self,
        mission: Mission,
        specs: Sequence[Mapping[str, Any]],
        external_key_to_id: Optional[Mapping[str, str]] = None,
    ) -> dict[str, Task]:
        if not specs:
            raise MissionGraphError("a plan requires at least one task")

        external_key_to_id = dict(external_key_to_id or {})
        key_to_id: dict[str, str] = {}
        normalized = []

        for index, raw in enumerate(specs):
            key = str(raw.get("key") or ("task_" + str(index + 1))).strip()
            if not key:
                raise MissionGraphError("task key is required")
            if key in key_to_id or key in external_key_to_id:
                raise MissionGraphError("duplicate/reserved task key: " + key)

            title = str(raw.get("title") or key).strip()
            tool_name = str(raw.get("tool_name") or "").strip()
            action = str(raw.get("action") or tool_name).strip()
            params = dict(raw.get("params") or {})
            required = bool(raw.get("required", True))
            max_attempts = int(raw.get("max_attempts", 2))

            if not tool_name or not action:
                raise MissionGraphError("tool_name and action are required for " + key)
            if max_attempts < 1:
                raise MissionGraphError("max_attempts must be >= 1")

            task_id = _deterministic_id(
                "task_", mission.mission_id, index, key, title, tool_name, action, params
            )
            key_to_id[key] = task_id
            normalized.append(
                {
                    "key": key,
                    "title": title,
                    "tool_name": tool_name,
                    "action": action,
                    "params": params,
                    "required": required,
                    "max_attempts": max_attempts,
                    "depends_on": list(raw.get("depends_on") or []),
                    "task_id": task_id,
                }
            )

        tasks: dict[str, Task] = {}
        for raw in normalized:
            dep_ids = []
            for dep_key in raw["depends_on"]:
                dep_key = str(dep_key)
                if dep_key in key_to_id:
                    dep_ids.append(key_to_id[dep_key])
                elif dep_key in external_key_to_id:
                    dep_ids.append(external_key_to_id[dep_key])
                else:
                    raise MissionGraphError("unknown dependency " + dep_key + " for " + raw["key"])

            tasks[raw["task_id"]] = Task(
                task_id=raw["task_id"],
                key=raw["key"],
                title=raw["title"],
                tool_call=ToolCall(
                    tool_name=raw["tool_name"],
                    action=raw["action"],
                    params=raw["params"],
                ),
                dependencies=dep_ids,
                required=raw["required"],
                max_attempts=raw["max_attempts"],
            )

        if not external_key_to_id:
            self._validate_dag(tasks)
        return tasks

    @staticmethod
    def _validate_dag(tasks: Mapping[str, Task]) -> None:
        ids = set(tasks)
        for task in tasks.values():
            if task.task_id in task.dependencies:
                raise MissionGraphError("self dependency: " + task.task_id)
            missing = [dep for dep in task.dependencies if dep not in ids]
            if missing:
                raise MissionGraphError("missing dependencies: " + repr(missing))

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            if task_id in visiting:
                raise MissionGraphError("cycle detected at " + task_id)
            visiting.add(task_id)
            for dep in tasks[task_id].dependencies:
                visit(dep)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in tasks:
            visit(task_id)

    def plan_mission(
        self,
        mission_id: str,
        task_specs: Sequence[Mapping[str, Any]],
        planning_context: Optional[Mapping[str, Any]] = None,
    ) -> Mission:
        mission = self._mission(mission_id)
        if mission.status not in {"draft", "planned", "recovering", "blocked"}:
            raise MissionStateError("cannot plan mission in state " + mission.status)

        context = dict(planning_context or {})
        if self.planning_context_provider is not None:
            supplied = self.planning_context_provider(mission.goal)
            if supplied:
                context.update(dict(supplied))

        tasks = self._build_tasks(mission, task_specs)
        revision = 1 if mission.plan is None else mission.plan.revision + 1
        plan_id = _deterministic_id(
            "plan_", mission.mission_id, revision, [task.to_dict() for task in tasks.values()]
        )

        mission.tasks = tasks
        mission.plan = Plan(
            plan_id=plan_id,
            mission_id=mission.mission_id,
            task_ids=tuple(tasks),
            revision=revision,
        )
        mission.planning_context = context
        mission.status = "planned"
        self._event(
            mission,
            "mission_planned",
            {"plan_id": plan_id, "revision": revision, "task_count": len(tasks)},
        )
        self._persist(mission)
        return mission

    def start_mission(self, mission_id: str) -> Mission:
        mission = self._mission(mission_id)
        if mission.status not in {"planned", "ready", "recovering"}:
            raise MissionStateError("cannot start mission in state " + mission.status)
        mission.status = "running"
        self._event(mission, "mission_started", {})
        self.next_ready_tasks(mission_id)
        self._persist(mission)
        return mission

    def next_ready_tasks(self, mission_id: str) -> list[Task]:
        mission = self._mission(mission_id)
        ready = []
        for task in mission.tasks.values():
            if task.status not in {"pending", "ready"}:
                continue
            deps = [mission.tasks[dep] for dep in task.dependencies]
            if all(dep.status == "succeeded" for dep in deps):
                task.status = "ready"
                ready.append(task)
            elif any(dep.status in {"failed", "cancelled"} for dep in deps):
                task.status = "cancelled"
                task.error = "dependency_failed"

        if ready and mission.status in {"planned", "ready", "recovering"}:
            mission.status = "running"
        self._persist(mission)
        return ready

    def _authorize(self, task: Task, *, user_confirmed: bool) -> tuple[str, Any]:
        if self.security_engine is None:
            return DENY, None
        authorize = getattr(self.security_engine, "authorize", None)
        if not callable(authorize):
            return DENY, None
        try:
            raw = authorize(
                task.tool_call.action,
                dict(task.tool_call.params),
                user_confirmed=user_confirmed,
            )
        except TypeError:
            try:
                raw = authorize(task.tool_call.action, dict(task.tool_call.params))
            except Exception:
                return DENY, None
        except Exception:
            return DENY, None
        return _normalize_decision(raw), raw

    def record_evidence(
        self,
        mission_id: str,
        task_id: str,
        kind: str,
        payload: Mapping[str, Any],
    ) -> TaskEvidence:
        mission = self._mission(mission_id)
        task = mission.tasks[task_id]
        sequence = len(task.evidence_ids) + 1
        evidence_id = _deterministic_id(
            "evi_", mission_id, task_id, sequence, kind, payload
        )
        existing = mission.evidence.get(evidence_id)
        if existing is not None:
            return existing

        evidence = TaskEvidence(
            evidence_id=evidence_id,
            mission_id=mission_id,
            task_id=task_id,
            kind=str(kind),
            payload=dict(payload),
            created_at=_utc_now(),
        )
        mission.evidence[evidence_id] = evidence
        task.evidence_ids.append(evidence_id)
        self._event(
            mission,
            "task_evidence_recorded",
            {"task_id": task_id, "evidence_id": evidence_id, "kind": kind},
        )
        self._persist(mission)
        return evidence

    def execute_task(
        self,
        mission_id: str,
        task_id: str,
        *,
        user_confirmed: bool = False,
    ) -> Task:
        mission = self._mission(mission_id)
        if mission.status in TERMINAL_MISSION_STATES:
            raise MissionStateError("mission is terminal")

        task = mission.tasks[task_id]
        if task.status not in {"ready", "waiting_confirmation"}:
            raise MissionStateError("task is not executable: " + task.status)

        deps = [mission.tasks[dep] for dep in task.dependencies]
        if not all(dep.status == "succeeded" for dep in deps):
            raise MissionStateError("dependencies are not satisfied")

        decision, raw_decision = self._authorize(task, user_confirmed=user_confirmed)
        self.record_evidence(
            mission_id,
            task_id,
            "authorization",
            {
                "decision": decision,
                "raw": str(raw_decision),
                "user_confirmed": bool(user_confirmed),
                "action": task.tool_call.action,
            },
        )

        if decision == REQUIRE_CONFIRMATION:
            task.status = "waiting_confirmation"
            mission.status = "waiting_confirmation"
            self._event(mission, "task_waiting_confirmation", {"task_id": task_id})
            self._persist(mission)
            return task

        if decision != ALLOW:
            task.status = "failed"
            task.error = "policy_denied"
            mission.status = "blocked"
            self._event(
                mission,
                "task_policy_denied",
                {"task_id": task_id, "decision": decision},
            )
            self._persist(mission)
            return task

        if not callable(self.tool_executor):
            task.status = "failed"
            task.error = "tool_executor_missing"
            mission.status = "blocked"
            self.record_evidence(
                mission_id, task_id, "execution_error", {"error": task.error}
            )
            self._persist(mission)
            return task

        task.status = "running"
        task.attempts += 1
        mission.status = "running"
        self._event(
            mission,
            "task_execution_started",
            {"task_id": task_id, "attempt": task.attempts},
        )
        self._persist(mission)

        try:
            result = self.tool_executor(task.tool_call)
        except Exception as exc:
            task.status = "failed"
            task.error = repr(exc)
            mission.status = "recovering" if task.attempts < task.max_attempts else "blocked"
            self.record_evidence(
                mission_id,
                task_id,
                "execution_error",
                {
                    "attempt": task.attempts,
                    "error": task.error,
                    "tool_name": task.tool_call.tool_name,
                },
            )
            self._event(
                mission,
                "task_execution_failed",
                {"task_id": task_id, "attempt": task.attempts},
            )
            self._persist(mission)
            return task

        task.result = result
        task.error = None
        self.record_evidence(
            mission_id,
            task_id,
            "execution_result",
            {
                "attempt": task.attempts,
                "tool_name": task.tool_call.tool_name,
                "action": task.tool_call.action,
                "result": result,
            },
        )
        task.status = "succeeded"
        self._event(
            mission,
            "task_succeeded",
            {"task_id": task_id, "attempt": task.attempts},
        )
        self.next_ready_tasks(mission_id)
        self._persist(mission)
        return task

    def retry_task(self, mission_id: str, task_id: str) -> Task:
        mission = self._mission(mission_id)
        task = mission.tasks[task_id]
        if task.status != "failed":
            raise MissionStateError("only failed tasks can be retried")
        if task.attempts >= task.max_attempts:
            raise MissionStateError("retry limit reached")
        task.status = "ready"
        task.error = None
        mission.status = "recovering"
        self._event(
            mission,
            "task_retry_scheduled",
            {"task_id": task_id, "next_attempt": task.attempts + 1},
        )
        self._persist(mission)
        return task

    def replan(
        self,
        mission_id: str,
        future_task_specs: Sequence[Mapping[str, Any]],
    ) -> Mission:
        mission = self._mission(mission_id)
        if mission.status in TERMINAL_MISSION_STATES:
            raise MissionStateError("cannot replan terminal mission")

        succeeded = {
            task.key: task
            for task in mission.tasks.values()
            if task.status == "succeeded"
        }
        succeeded_key_to_id = {task.key: task.task_id for task in succeeded.values()}

        provisional = self._build_tasks(
            mission,
            future_task_specs,
            external_key_to_id=succeeded_key_to_id,
        )

        combined = {task.task_id: task for task in succeeded.values()}
        combined.update(provisional)
        self._validate_dag(combined)

        revision = 1 if mission.plan is None else mission.plan.revision + 1
        plan_id = _deterministic_id(
            "plan_", mission.mission_id, revision, [task.to_dict() for task in combined.values()]
        )

        mission.tasks = combined
        mission.plan = Plan(
            plan_id=plan_id,
            mission_id=mission.mission_id,
            task_ids=tuple(combined),
            revision=revision,
        )
        mission.status = "planned"
        self._event(
            mission,
            "mission_replanned",
            {
                "plan_id": plan_id,
                "revision": revision,
                "preserved_succeeded": sorted(succeeded),
            },
        )
        self._persist(mission)
        return mission

    def resume(self, mission_id: str) -> Mission:
        mission = self._mission(mission_id)
        if mission.status not in {"waiting_confirmation", "blocked", "recovering", "planned"}:
            raise MissionStateError("mission cannot resume from " + mission.status)
        mission.status = "running"
        self._event(mission, "mission_resumed", {})
        self.next_ready_tasks(mission_id)
        self._persist(mission)
        return mission

    def cancel(self, mission_id: str) -> Mission:
        mission = self._mission(mission_id)
        if mission.status in TERMINAL_MISSION_STATES:
            return mission
        for task in mission.tasks.values():
            if task.status not in TERMINAL_TASK_STATES:
                task.status = "cancelled"
        mission.status = "cancelled"
        self._event(mission, "mission_cancelled", {})
        self._persist(mission)
        return mission

    def complete(self, mission_id: str) -> Mission:
        mission = self._mission(mission_id)
        if not mission.tasks:
            raise MissionStateError("mission has no tasks")
        for task in mission.tasks.values():
            if task.required and task.status != "succeeded":
                raise MissionStateError("required task not satisfied: " + task.key)
            if not task.required and task.status not in TERMINAL_TASK_STATES:
                raise MissionStateError("optional task is not terminal: " + task.key)
        mission.status = "completed"
        self._event(mission, "mission_completed", {})
        self._persist(mission)
        return mission

    def get_mission(self, mission_id: str) -> Mission:
        return self._mission(mission_id)


__all__ = [
    "MISSION_STATES",
    "TASK_STATES",
    "MissionError",
    "MissionStateError",
    "MissionGraphError",
    "MissionPolicyError",
    "Goal",
    "Plan",
    "Task",
    "TaskDependency",
    "ToolCall",
    "TaskEvidence",
    "MissionEvent",
    "Mission",
    "SQLiteMissionStore",
    "MissionEngine",
]
