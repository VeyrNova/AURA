from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from integrations import IntegrationCapability, IntegrationManifest, IntegrationRequest
from runtime.aura_obsidian_creative_studio_v140 import ObsidianCreativeStudio, discover_vaults

OBSIDIAN_PROVIDER_ID = "obsidian.creative"


class ObsidianCreativeProvider:
    def __init__(self, default_vault: str | Path | None = None) -> None:
        self.default_vault = Path(default_vault).expanduser().resolve() if default_vault else None
        self._manifest = IntegrationManifest(
            provider_id=OBSIDIAN_PROVIDER_ID,
            display_name="AURA Obsidian Creative Studio",
            provider_version="1.4.0-o140.r2",
            capabilities=(
                IntegrationCapability("obsidian.discover_vaults", "obsidian.discover_vaults", "Discover local Obsidian vaults.", "low", False, "read", True),
                IntegrationCapability("obsidian.creative_snapshot", "obsidian.creative_snapshot", "Read creative project structure.", "low", False, "read", True),
                IntegrationCapability("obsidian.search_context", "obsidian.search_context", "Search creative context in Markdown notes.", "low", False, "read", True),
                IntegrationCapability("obsidian.read_note", "obsidian.read_note", "Read one exact vault-bound Markdown note.", "low", False, "read", True),
            ),
            auth_kind="local",
            metadata={
                "receipt_owner": "IntegrationRegistry/ActionReceiptService",
                "read_only": True,
                "note_write": False,
                "note_delete": False,
                "shell_execution": False,
                "vault_boundary_enforced": True,
            },
        )

    @property
    def manifest(self) -> IntegrationManifest:
        return self._manifest

    def health_snapshot(self) -> Mapping[str, Any]:
        vaults = discover_vaults()
        return {
            "provider_id": OBSIDIAN_PROVIDER_ID,
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
        raise RuntimeError("Plusieurs vaults Obsidian sont disponibles; precise vault_path.")

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        params = dict(request.params or {})

        if capability == "obsidian.discover_vaults":
            rows = [{"path": v.path, "name": v.name, "config_present": v.config_present} for v in discover_vaults()]
            result = {"kind": "vaults", "count": len(rows), "items": rows, "read_only": True}
        elif capability == "obsidian.creative_snapshot":
            studio = ObsidianCreativeStudio(self._resolve_vault(params))
            studio.build_index(int(params.get("max_notes") or 5000))
            result = studio.creative_snapshot()
            result["kind"] = "creative_snapshot"
        elif capability == "obsidian.search_context":
            query = str(params.get("query") or "").strip()
            if not query:
                raise ValueError("query is required")
            studio = ObsidianCreativeStudio(self._resolve_vault(params))
            studio.build_index(int(params.get("max_notes") or 5000))
            result = studio.search_context(query, int(params.get("limit") or 12))
            result["kind"] = "search"
        elif capability == "obsidian.read_note":
            relative_path = str(params.get("relative_path") or "").strip()
            if not relative_path:
                raise ValueError("relative_path is required")
            studio = ObsidianCreativeStudio(self._resolve_vault(params))
            result = studio.read_note(relative_path)
            result["kind"] = "note"
            result["read_only"] = True
        else:
            raise ValueError(f"unsupported Obsidian capability: {capability}")

        return {
            "provider_id": OBSIDIAN_PROVIDER_ID,
            "capability_id": capability,
            "obsidian_result": result,
            "evidence_refs": (),
        }
