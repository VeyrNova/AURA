"""Helpers for historical regression tests across monotonic AURA releases."""
from __future__ import annotations
import re


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(value))
    return tuple(int(p) for p in parts)


def assert_version_at_least(case, current: str, minimum: str) -> None:
    """Historical feature tests stay valid on later AURA releases.

    A feature regression test should assert that the running build is not older
    than the generation that introduced the feature; it must not pin the whole
    application to the old release string forever.
    """
    case.assertGreaterEqual(
        _version_tuple(current), _version_tuple(minimum),
        f"AURA {current} est antérieure à la génération requise {minimum}",
    )
