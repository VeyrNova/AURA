"""Legacy prompt compatibility for AURA v0.4.2.

New code should use ConsciousnessContextBuilder. SYSTEM_PROMPT remains available for
older imports but the running application rebuilds a fresh system prompt per request.
"""
from consciousness.context_builder import ConsciousnessContextBuilder

SYSTEM_PROMPT = ConsciousnessContextBuilder().build_system_prompt()
