from __future__ import annotations

import json
from collections import Counter

from agent.schemas import AgentPlan


class AgentLoopGuardError(ValueError):
    pass


class AgentLoopGuard:
    """Reject obviously looping plans before any tool executes.

    The guard compares canonical tool+argument signatures, not just action names,
    so legitimate repeated calls such as weather for several different cities
    remain possible.
    """

    def __init__(self, *, max_same_signature: int = 2, max_same_action: int = 4):
        self.max_same_signature = max(1, int(max_same_signature))
        self.max_same_action = max(2, int(max_same_action))

    @staticmethod
    def _signature(step) -> str:
        try:
            args = json.dumps(step.args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except Exception:
            args = repr(step.args)
        return f"{step.tool}|{args}"

    def validate(self, plan: AgentPlan) -> AgentPlan:
        signatures = [self._signature(step) for step in plan.steps]
        repeated = Counter(signatures)
        if repeated and max(repeated.values()) > self.max_same_signature:
            raise AgentLoopGuardError("Plan agent répétitif : même appel d'outil répété trop souvent")

        actions = Counter(str(step.action or "").upper() for step in plan.steps)
        if actions and max(actions.values()) > self.max_same_action:
            raise AgentLoopGuardError("Plan agent répétitif : budget par action dépassé")

        # Exact A-B-A-B / A-B-C-A-B-C cycles are almost certainly planner loops.
        total = len(signatures)
        for width in range(1, total // 2 + 1):
            if 2 * width <= total and signatures[-2 * width:-width] == signatures[-width:]:
                if width > 1 or len(set(signatures[-width:])) == 1:
                    raise AgentLoopGuardError("Plan agent cyclique détecté")
        return plan
