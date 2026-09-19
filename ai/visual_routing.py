"""Visual-generation routing for AURA v0.7.0.15.4.

Real-world visual requests are expected to have been offered to deterministic
Internet tools first. Remaining visual prompts stay on the warm voice brain by
default; only an explicitly requested deep analysis may cold-load the text brain.
"""
from __future__ import annotations

from config.settings import settings
from tools.search_intent import is_complex_visual_analysis, is_structured_visual_request


def _request_profile(resource_guardian, *, voice_output: bool, user_text: str) -> dict:
    """Request the modern profile while tolerating legacy guardian adapters."""
    try:
        return dict(resource_guardian.llm_request_profile(voice_output=voice_output, user_text=user_text))
    except TypeError as exc:
        # Older extension/test adapters only accept voice_output. Keep this
        # compatibility path so the hybrid privacy context does not break them.
        if "user_text" not in str(exc):
            raise
        return dict(resource_guardian.llm_request_profile(voice_output=voice_output))


def select_visual_profile(resource_guardian, user_text: str) -> dict:
    """Choose a visual LLM profile without inheriting spoken-answer brevity."""
    if is_complex_visual_analysis(user_text):
        profile = _request_profile(resource_guardian, voice_output=False, user_text=user_text)
        profile["name"] = "visual-deep"
        profile["num_predict"] = max(
            int(profile.get("num_predict", 0)),
            int(settings.LLM_VISUAL_NUM_PREDICT),
        )
        return profile

    # Request the already-resident fast brain profile even though the final
    # answer itself will not be spoken in full. This preserves XTTS co-residency.
    profile = _request_profile(resource_guardian, voice_output=True, user_text=user_text)
    structured = is_structured_visual_request(user_text)
    profile["name"] = "visual-structured" if structured else "visual-fast"
    profile["num_predict"] = max(
        int(profile.get("num_predict", 0)),
        int(settings.LLM_VISUAL_STRUCTURED_NUM_PREDICT if structured else settings.LLM_VISUAL_FAST_NUM_PREDICT),
    )
    profile["compact"] = not structured
    return profile
