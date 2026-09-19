"""AURA consciousness foundation (v0.5).

This package contains AURA's identity, personality, self-model and dynamic
system-context builder. It does not grant execution permissions; security
remains enforced by the deterministic SecurityPolicyEngine.
"""

from consciousness.context_builder import ConsciousnessContextBuilder
from consciousness.identity import AuraIdentity
from consciousness.personality import PersonalityEngine, PersonalityProfile
from consciousness.self_model import SelfModel

__all__ = [
    "AuraIdentity",
    "PersonalityEngine",
    "PersonalityProfile",
    "SelfModel",
    "ConsciousnessContextBuilder",
]
