"""Canonical AURA release identity.

v0.7.2.1 starts the consolidation line: every runtime surface imports the
version from this module instead of carrying its own historical hotfix number.
"""
from __future__ import annotations

AURA_VERSION = "2.2"
AURA_BUILD = "2026.08.22.60"
AURA_RELEASE_CHANNEL = "universal-windows-p0.8.5.4.1.1"
AURA_RELEASE_DATE = "2026-08-22"


def version_string() -> str:
    return AURA_VERSION


def build_identity() -> str:
    return f"{AURA_VERSION}+{AURA_BUILD}"
