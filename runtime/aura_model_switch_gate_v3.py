from __future__ import annotations

"""AURA Model Switch Gate v3.

Pure session-stability gate inspired by the model-switch gating pattern studied
in vLLM Semantic Router. The gate does not choose a provider/model, probe
hardware, call providers, or mutate runtime state. It only decides whether a
proposed eligible route may replace the currently active eligible route.

The caller remains responsible for:
- hard eligibility (EligibilityFilterV3),
- route/model policy (ModelPolicyEngineV3),
- provider health facts,
- session-state persistence,
- actual provider/model switching.
"""

from dataclasses import asdict, dataclass
from typing import Any, Mapping

SCHEMA = "aura.model_switch_gate.v3"
VERSION = "3.0.0"


@dataclass(frozen=True)
class RouteIdentityV3:
    provider: str
    model: str = ""

    @property
    def key(self) -> str:
        provider = str(self.provider or "").strip().casefold()
        model = str(self.model or "").strip().casefold()
        return f"{provider}:{model}"


@dataclass(frozen=True)
class ModelSwitchSessionStateV3:
    current: RouteIdentityV3 | None = None
    turns_on_current: int = 0
    turns_since_switch: int = 0
    current_warm: bool = False


@dataclass(frozen=True)
class ModelSwitchRequestV3:
    proposed: RouteIdentityV3
    current_eligible: bool = True
    proposed_eligible: bool = True
    explicit_user_preference: bool = False
    hard_constraint_requires_switch: bool = False
    current_unhealthy: bool = False
    proposed_warm: bool = False

    # The scoring owner supplies a normalized benefit signal. The switch gate
    # never invents provider/model quality scores itself.
    advantage_score: float = 0.0

    # Positive cost/penalty supplied by the caller, e.g. cold-start or context
    # handoff cost. It is subtracted from the proposed advantage.
    switch_penalty: float = 0.0

    # Optional extra benefit when the proposed route is already warm/resident.
    warm_bonus: float = 0.0


@dataclass(frozen=True)
class ModelSwitchPolicyV3:
    min_turns_on_current: int = 2
    min_turns_between_switches: int = 2
    min_effective_advantage: float = 0.15
    emergency_advantage: float = 0.90


@dataclass(frozen=True)
class ModelSwitchDecisionV3:
    schema: str
    version: str
    allow_switch: bool
    selected: RouteIdentityV3
    current: RouteIdentityV3 | None
    proposed: RouteIdentityV3
    effective_advantage: float
    threshold: float
    reason_codes: tuple[str, ...]
    facts: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _route(value: RouteIdentityV3 | Mapping[str, Any] | None) -> RouteIdentityV3 | None:
    if value is None:
        return None
    if isinstance(value, RouteIdentityV3):
        return value
    if isinstance(value, Mapping):
        return RouteIdentityV3(
            provider=str(value.get("provider") or ""),
            model=str(value.get("model") or ""),
        )
    raise TypeError("route must be RouteIdentityV3, mapping or None")


def _state(value: ModelSwitchSessionStateV3 | Mapping[str, Any] | None) -> ModelSwitchSessionStateV3:
    if value is None:
        return ModelSwitchSessionStateV3()
    if isinstance(value, ModelSwitchSessionStateV3):
        return value
    if isinstance(value, Mapping):
        return ModelSwitchSessionStateV3(
            current=_route(value.get("current")),
            turns_on_current=max(0, int(value.get("turns_on_current") or 0)),
            turns_since_switch=max(0, int(value.get("turns_since_switch") or 0)),
            current_warm=bool(value.get("current_warm", False)),
        )
    raise TypeError("state must be ModelSwitchSessionStateV3, mapping or None")


def _request(value: ModelSwitchRequestV3 | Mapping[str, Any]) -> ModelSwitchRequestV3:
    if isinstance(value, ModelSwitchRequestV3):
        return value
    if isinstance(value, Mapping):
        data = dict(value)
        data["proposed"] = _route(data.get("proposed"))
        if data["proposed"] is None:
            raise ValueError("proposed route is required")
        return ModelSwitchRequestV3(**data)
    raise TypeError("request must be ModelSwitchRequestV3 or mapping")


class ModelSwitchGateV3:
    """Prevent unnecessary route thrashing while respecting hard constraints."""

    def evaluate(
        self,
        state: ModelSwitchSessionStateV3 | Mapping[str, Any] | None,
        request: ModelSwitchRequestV3 | Mapping[str, Any],
        policy: ModelSwitchPolicyV3 | Mapping[str, Any] | None = None,
    ) -> ModelSwitchDecisionV3:
        session = _state(state)
        req = _request(request)

        if policy is None:
            pol = ModelSwitchPolicyV3()
        elif isinstance(policy, ModelSwitchPolicyV3):
            pol = policy
        elif isinstance(policy, Mapping):
            pol = ModelSwitchPolicyV3(**dict(policy))
        else:
            raise TypeError("policy must be ModelSwitchPolicyV3, mapping or None")

        current = session.current
        proposed = req.proposed

        advantage = float(req.advantage_score or 0.0)
        penalty = max(0.0, float(req.switch_penalty or 0.0))
        warm_bonus = max(0.0, float(req.warm_bonus or 0.0)) if req.proposed_warm else 0.0
        effective = advantage - penalty + warm_bonus
        threshold = max(0.0, float(pol.min_effective_advantage))

        reasons: list[str] = []

        # No current route: there is nothing to destabilize.
        if current is None:
            reasons.append("NO_CURRENT_ROUTE")
            return self._decision(
                allow=True,
                selected=proposed,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        # Same provider/model is not a switch; keep the active route.
        if current.key == proposed.key:
            reasons.append("SAME_ROUTE")
            return self._decision(
                allow=False,
                selected=current,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        # A proposed route that is not eligible can never replace the current one.
        if not req.proposed_eligible:
            reasons.append("PROPOSED_ROUTE_INELIGIBLE")
            return self._decision(
                allow=False,
                selected=current,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        # Hard safety/privacy eligibility always wins over stability.
        if not req.current_eligible:
            reasons.append("CURRENT_ROUTE_INELIGIBLE")
            return self._decision(
                allow=True,
                selected=proposed,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        if req.hard_constraint_requires_switch:
            reasons.append("HARD_CONSTRAINT_REQUIRES_SWITCH")
            return self._decision(
                allow=True,
                selected=proposed,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        if req.current_unhealthy:
            reasons.append("CURRENT_ROUTE_UNHEALTHY")
            return self._decision(
                allow=True,
                selected=proposed,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        if req.explicit_user_preference:
            reasons.append("EXPLICIT_USER_PREFERENCE")
            return self._decision(
                allow=True,
                selected=proposed,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        emergency = max(threshold, float(pol.emergency_advantage))

        # Do not oscillate immediately after a recent switch unless the supplied
        # advantage is exceptional.
        if (
            session.turns_since_switch < max(0, int(pol.min_turns_between_switches))
            and effective < emergency
        ):
            reasons.append("SWITCH_COOLDOWN_ACTIVE")
            return self._decision(
                allow=False,
                selected=current,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        # Give a newly selected route a minimum stable residence period.
        if (
            session.turns_on_current < max(0, int(pol.min_turns_on_current))
            and effective < emergency
        ):
            reasons.append("MINIMUM_ROUTE_RESIDENCE")
            return self._decision(
                allow=False,
                selected=current,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        if effective >= threshold:
            reasons.append("ADVANTAGE_THRESHOLD_MET")
            if req.proposed_warm and warm_bonus > 0:
                reasons.append("PROPOSED_ROUTE_WARM")
            return self._decision(
                allow=True,
                selected=proposed,
                current=current,
                proposed=proposed,
                effective=effective,
                threshold=threshold,
                reasons=reasons,
                session=session,
                req=req,
                pol=pol,
            )

        reasons.append("ADVANTAGE_TOO_SMALL")
        return self._decision(
            allow=False,
            selected=current,
            current=current,
            proposed=proposed,
            effective=effective,
            threshold=threshold,
            reasons=reasons,
            session=session,
            req=req,
            pol=pol,
        )

    @staticmethod
    def _decision(
        *,
        allow: bool,
        selected: RouteIdentityV3,
        current: RouteIdentityV3 | None,
        proposed: RouteIdentityV3,
        effective: float,
        threshold: float,
        reasons: list[str],
        session: ModelSwitchSessionStateV3,
        req: ModelSwitchRequestV3,
        pol: ModelSwitchPolicyV3,
    ) -> ModelSwitchDecisionV3:
        return ModelSwitchDecisionV3(
            schema=SCHEMA,
            version=VERSION,
            allow_switch=bool(allow),
            selected=selected,
            current=current,
            proposed=proposed,
            effective_advantage=float(effective),
            threshold=float(threshold),
            reason_codes=tuple(dict.fromkeys(reasons)),
            facts={
                "turns_on_current": int(session.turns_on_current),
                "turns_since_switch": int(session.turns_since_switch),
                "current_warm": bool(session.current_warm),
                "proposed_warm": bool(req.proposed_warm),
                "current_eligible": bool(req.current_eligible),
                "proposed_eligible": bool(req.proposed_eligible),
                "current_unhealthy": bool(req.current_unhealthy),
                "switch_penalty": float(req.switch_penalty or 0.0),
                "warm_bonus_applied": (
                    max(0.0, float(req.warm_bonus or 0.0))
                    if req.proposed_warm
                    else 0.0
                ),
                "min_turns_on_current": int(pol.min_turns_on_current),
                "min_turns_between_switches": int(pol.min_turns_between_switches),
                "emergency_advantage": float(pol.emergency_advantage),
            },
        )
