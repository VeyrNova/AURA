"""AURA A200-R21 deployed composer seam discovery/binding descriptor.

Read-only discovery companion. It does not execute tools and does not mutate
the deployed UI itself. The installer owns the bounded UI transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
from typing import Iterable


A200_R21_MARKER = "AURA_A200_R21_ACTUAL_COMPOSER_SEAM_BINDING_V1"

DEFAULT_UI_ROOT = Path(
    r"C:\Users\leclerc\AppData\Local\AURA\ui\v0.7.2.2-rc4.2"
)
EXPECTED_COMPOSER_RELATIVE = Path(
    r"dist\assets\aura-p0823-composer-single-surface.js"
)
EXPECTED_COMPOSER_SHA256 = (
    "1697cf5f05e174347f022e72b26e083ba5be1a8b01ad67b3a483cd65177c8552"
)

READ_ONLY_DISCOVERY = True
DIRECT_EXECUTION_ENABLED = False
COMPOSER_SUBMIT_INTERCEPTION_ENABLED = False
COMPOSER_TEXT_MUTATION_ENABLED = False
ARBITRARY_DOM_CAPTURE_ENABLED = False


class ComposerSeamDiscoveryError(RuntimeError):
    pass


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ComposerSeamDescriptor:
    schema: str
    ui_root: str
    relative_path: str
    absolute_path: str
    sha256: str
    size: int
    composer_token_count: int
    input_token_count: int
    event_token_count: int
    binding_mode: str
    submit_interception: bool
    direct_execution: bool

    def to_dict(self):
        return asdict(self)


def discover_composer_seam(
    ui_root: str | Path = DEFAULT_UI_ROOT,
) -> ComposerSeamDescriptor:
    root = Path(ui_root)
    target = root / EXPECTED_COMPOSER_RELATIVE
    if not target.is_file():
        raise ComposerSeamDiscoveryError(
            f"certified composer asset missing: {target}"
        )

    actual_hash = sha256_file(target)
    if actual_hash != EXPECTED_COMPOSER_SHA256:
        raise ComposerSeamDiscoveryError(
            "certified composer asset hash mismatch"
        )

    text = target.read_text(
        encoding="utf-8-sig",
        errors="replace",
    ).lower()

    composer_tokens = sum(
        text.count(token)
        for token in (
            "composer",
            "single-surface",
            "single_surface",
        )
    )
    input_tokens = sum(
        text.count(token)
        for token in (
            "textarea",
            "contenteditable",
            "input",
        )
    )
    event_tokens = sum(
        text.count(token)
        for token in (
            "keydown",
            "submit",
            "click",
        )
    )

    if composer_tokens < 1:
        raise ComposerSeamDiscoveryError(
            "certified asset no longer exposes composer semantics"
        )

    return ComposerSeamDescriptor(
        schema="aura.a200.r21.composer-seam-descriptor.v1",
        ui_root=str(root),
        relative_path=str(EXPECTED_COMPOSER_RELATIVE).replace("\\", "/"),
        absolute_path=str(target),
        sha256=actual_hash,
        size=target.stat().st_size,
        composer_token_count=composer_tokens,
        input_token_count=input_tokens,
        event_token_count=event_tokens,
        binding_mode="adjacent-explicit-plan-button",
        submit_interception=False,
        direct_execution=False,
    )


def assert_r21_discovery_contract() -> None:
    if not READ_ONLY_DISCOVERY:
        raise RuntimeError("R21 discovery must remain read-only")
    if DIRECT_EXECUTION_ENABLED:
        raise RuntimeError("R21 discovery cannot execute")
    if COMPOSER_SUBMIT_INTERCEPTION_ENABLED:
        raise RuntimeError("R21 must not intercept composer submit")
    if COMPOSER_TEXT_MUTATION_ENABLED:
        raise RuntimeError("R21 must not alter composer text")
    if ARBITRARY_DOM_CAPTURE_ENABLED:
        raise RuntimeError("R21 must not use arbitrary DOM capture")


if __name__ == "__main__":
    assert_r21_discovery_contract()
    print(json.dumps(
        discover_composer_seam().to_dict(),
        indent=2,
        ensure_ascii=False,
    ))
