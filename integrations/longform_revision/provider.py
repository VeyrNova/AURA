from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from integrations import IntegrationCapability, IntegrationManifest, IntegrationRequest
from runtime.aura_longform_revision_v141 import LongFormRevisionStudio
from runtime.aura_obsidian_creative_studio_v140 import discover_vaults

LONGFORM_PROVIDER_ID = "longform.revision"


class LongFormRevisionProvider:
    def __init__(self, default_vault: str | Path | None = None) -> None:
        self.default_vault = Path(default_vault).expanduser().resolve() if default_vault else None
        self._manifest = IntegrationManifest(
            provider_id=LONGFORM_PROVIDER_ID,
            display_name="AURA Long-form Revision",
            provider_version="1.4.1-o141.r3",
            capabilities=(
                IntegrationCapability("longform.manuscript_outline", "longform.manuscript_outline", "Read ordered manuscript outline.", "low", False, "read", True),
                IntegrationCapability("longform.chapter_context", "longform.chapter_context", "Read previous/current/next chapter context.", "low", False, "read", True),
                IntegrationCapability("longform.continuity_audit", "longform.continuity_audit", "Audit long-form continuity.", "low", False, "read", True),
                IntegrationCapability("longform.revision_brief", "longform.revision_brief", "Build one chapter revision brief.", "low", False, "read", True),
                IntegrationCapability("longform.context_search_pack", "longform.context_search_pack", "Search project context with chapter enrichment.", "low", False, "read", True),
                IntegrationCapability("longform.chapter_transition", "longform.chapter_transition", "Analyze continuity between two adjacent or selected chapters.", "low", False, "read", True),
                IntegrationCapability("longform.chapter_revision_report", "longform.chapter_revision_report", "Build an actionable deterministic revision report for one chapter.", "low", False, "read", True),
                IntegrationCapability("longform.manuscript_revision_report", "longform.manuscript_revision_report", "Build a manuscript-wide deterministic revision report.", "low", False, "read", True),
            ),
            auth_kind="local",
            metadata={
                "receipt_owner": "IntegrationRegistry/ActionReceiptService",
                "read_only": True,
                "note_write": False,
                "note_delete": False,
                "shell_execution": False,
            },
        )

    @property
    def manifest(self) -> IntegrationManifest:
        return self._manifest

    def health_snapshot(self) -> Mapping[str, Any]:
        vaults = discover_vaults()
        return {
            "provider_id": LONGFORM_PROVIDER_ID,
            "available": bool(vaults or self.default_vault),
            "health_state": "healthy",
            "read_only": True,
            "vault_count": len(vaults),
        }

    def _resolve_vault(self, params: Mapping[str, Any]) -> Path:
        raw = str(params.get("vault_path") or "").strip()
        if raw:
            return Path(raw).expanduser().resolve()
        if self.default_vault is not None:
            return self.default_vault
        vaults = discover_vaults()
        if len(vaults) == 1:
            return Path(vaults[0].path)
        if not vaults:
            raise RuntimeError("Aucun vault Obsidian local detecte.")
        raise RuntimeError("Plusieurs vaults sont disponibles; precise vault_path.")

    @staticmethod
    def _resolve_chapter(studio: LongFormRevisionStudio, selector: str) -> str:
        selector = str(selector or "").strip()
        if not selector:
            raise ValueError("chapter selector is required")

        outline = studio.manuscript_outline()
        rows = outline.get("chapters") or []
        if not rows:
            raise RuntimeError("Aucun chapitre detecte.")

        m = re.search(r"\b(\d{1,4})\b", selector)
        if m:
            number = int(m.group(1))
            exact = [r for r in rows if r.get("chapter_number") == number]
            if len(exact) == 1:
                return str(exact[0]["relative_path"])

        normalized = selector.casefold()
        title_hits = [
            r for r in rows
            if normalized in str(r.get("title") or "").casefold()
            or normalized in str(r.get("relative_path") or "").casefold()
        ]
        if len(title_hits) == 1:
            return str(title_hits[0]["relative_path"])
        if len(title_hits) > 1:
            raise RuntimeError("Plusieurs chapitres correspondent a cette demande.")
        raise RuntimeError(f"Chapitre introuvable: {selector}")

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        params = dict(request.params or {})
        studio = LongFormRevisionStudio(self._resolve_vault(params))

        if capability == "longform.manuscript_outline":
            result = studio.manuscript_outline()
        elif capability == "longform.continuity_audit":
            result = studio.continuity_audit()
        elif capability == "longform.chapter_context":
            rel = self._resolve_chapter(studio, str(params.get("chapter") or params.get("relative_path") or ""))
            result = studio.chapter_context(rel, radius=int(params.get("radius") or 1))
        elif capability == "longform.revision_brief":
            rel = self._resolve_chapter(studio, str(params.get("chapter") or params.get("relative_path") or ""))
            result = studio.revision_brief(rel)
        elif capability == "longform.context_search_pack":
            query = str(params.get("query") or "").strip()
            if not query:
                raise ValueError("query is required")
            result = studio.context_search_pack(query, limit=int(params.get("limit") or 8))
        elif capability == "longform.chapter_transition":
            left = self._resolve_chapter(studio, str(params.get("from_chapter") or ""))
            right = self._resolve_chapter(studio, str(params.get("to_chapter") or ""))
            result = studio.chapter_transition(left, right)
        elif capability == "longform.chapter_revision_report":
            rel = self._resolve_chapter(studio, str(params.get("chapter") or params.get("relative_path") or ""))
            result = studio.chapter_revision_report(rel)
        elif capability == "longform.manuscript_revision_report":
            result = studio.manuscript_revision_report()
        else:
            raise ValueError(f"unsupported long-form capability: {capability}")

        return {
            "provider_id": LONGFORM_PROVIDER_ID,
            "capability_id": capability,
            "longform_result": result,
            "evidence_refs": (),
        }
