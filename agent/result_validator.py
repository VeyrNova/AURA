from __future__ import annotations

import re

from agent.schemas import AgentPlan
from agent.tool_registry import AgentToolRegistry


class AgentPlanValidationError(ValueError):
    pass


_REF_RE = re.compile(r"\$\{(?P<step>step\d+)\.(?P<path>[A-Za-z0-9_.-]+)\}")


class AgentPlanValidator:
    def __init__(self, registry: AgentToolRegistry, *, max_steps: int = 6):
        self.registry = registry
        self.max_steps = max(2, int(max_steps))

    def validate(self, plan: AgentPlan) -> AgentPlan:
        if not isinstance(plan, AgentPlan):
            raise AgentPlanValidationError("Plan agent invalide")
        if len(plan.steps) < 2:
            raise AgentPlanValidationError("Un plan agent doit contenir au moins deux étapes")
        if len(plan.steps) > self.max_steps:
            raise AgentPlanValidationError(f"Plan agent trop long (max={self.max_steps})")

        seen: set[str] = set()
        for index, step in enumerate(plan.steps, start=1):
            if not step.id or step.id in seen:
                raise AgentPlanValidationError(f"Identifiant d'étape invalide/dupliqué: {step.id!r}")
            seen.add(step.id)
            spec = self.registry.by_action(step.action)
            if spec is None:
                raise AgentPlanValidationError(f"Action non enregistrée: {step.action}")
            if spec.name != step.tool:
                raise AgentPlanValidationError(
                    f"Couple outil/action incohérent à l'étape {index}: {step.tool}/{step.action}"
                )
            if not spec.read_only or not spec.background_safe:
                raise AgentPlanValidationError(f"Outil non autorisé dans l'exécuteur agent: {step.tool}")
            if not isinstance(step.args, dict):
                raise AgentPlanValidationError(f"Arguments invalides à l'étape {index}")
            for key in spec.required_args:
                raw = step.args.get(key)
                # Placeholder references are accepted here and resolved at runtime.
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    raise AgentPlanValidationError(f"Argument requis manquant: {step.tool}.{key}")
            for value in step.args.values():
                if isinstance(value, str) and len(value) > 4096:
                    raise AgentPlanValidationError("Argument agent trop long")
                if isinstance(value, str):
                    for match in _REF_RE.finditer(value):
                        ref_step = match.group("step")
                        if ref_step not in seen or ref_step == step.id:
                            raise AgentPlanValidationError(
                                f"Référence d'étape future/inconnue interdite: {ref_step}"
                            )
        return plan
