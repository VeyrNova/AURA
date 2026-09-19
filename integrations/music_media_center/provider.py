from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from integrations import IntegrationCapability, IntegrationManifest, IntegrationRequest
from runtime.aura_music_media_center_v180 import MusicMediaCenter

PROVIDER_ID = "music.media-center"


class MusicMediaCenterProvider:
    def __init__(self, index_path: str | Path | None = None) -> None:
        default_index = Path(
            os.environ.get(
                "AURA_M180_MEDIA_INDEX",
                r"C:\AURA GPT version\data\media\local_media_index_v180.json",
            )
        )
        self.index_path = Path(index_path or default_index).expanduser().resolve()
        self._manifest = IntegrationManifest(
            provider_id=PROVIDER_ID,
            display_name="AURA Music & Media Center",
            provider_version="1.8.0-m180.r2",
            capabilities=(
                IntegrationCapability("media.catalog_summary", "media.catalog_summary", "Summarize the local media catalog.", "low", False, "read", True),
                IntegrationCapability("media.search", "media.search", "Search the local media index.", "low", False, "read", True),
                IntegrationCapability("media.smart_queue", "media.smart_queue", "Build an explainable queue proposal.", "low", False, "read", True),
                IntegrationCapability("media.playlist_proposal", "media.playlist_proposal", "Build a local playlist proposal without writing externally.", "low", False, "read", True),
                IntegrationCapability("media.playback_intent", "media.playback_intent", "Prepare a playback intent that remains approval_required.", "low", False, "read", True),
            ),
            auth_kind="local_media_index",
            metadata={
                "index_path": str(self.index_path),
                "real_player_control": False,
                "filesystem_delete": False,
                "filesystem_move": False,
                "filesystem_rename": False,
                "external_playlist_write": False,
                "external_account_mutation": False,
            },
        )

    @property
    def manifest(self) -> IntegrationManifest:
        return self._manifest

    def _load(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {
                "schema": "aura.local-media-index.v180",
                "items": [],
                "item_count": 0,
            }
        data = json.loads(self.index_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise RuntimeError("invalid M180 media index")
        return data

    def health_snapshot(self) -> Mapping[str, Any]:
        try:
            data = self._load()
            return {
                "provider_id": PROVIDER_ID,
                "available": True,
                "health_state": "healthy",
                "index_path": str(self.index_path),
                "item_count": int(data.get("item_count") or len(data.get("items") or [])),
                "captured_at": data.get("captured_at"),
                "real_player_control": False,
            }
        except Exception as exc:
            return {
                "provider_id": PROVIDER_ID,
                "available": False,
                "health_state": "degraded",
                "error": type(exc).__name__,
            }

    def execute(self, request: IntegrationRequest) -> Any:
        data = self._load()
        center = MusicMediaCenter(data.get("items") or [])
        capability = str(request.capability_id or "")
        params = dict(request.params or {})

        if capability == "media.catalog_summary":
            result = center.catalog_summary()
            result["index_captured_at"] = data.get("captured_at")
            result["index_roots"] = data.get("roots") or []
        elif capability == "media.search":
            result = center.search(
                str(params.get("query") or ""),
                media_type=params.get("media_type"),
                genre=params.get("genre"),
                artist=params.get("artist"),
                limit=int(params.get("limit") or 20),
            )
        elif capability == "media.smart_queue":
            result = center.smart_queue(
                mood=str(params.get("mood") or ""),
                genre=str(params.get("genre") or ""),
                media_type=str(params.get("media_type") or "audio"),
                max_items=int(params.get("max_items") or 10),
            )
        elif capability == "media.playlist_proposal":
            result = center.playlist_proposal(
                str(params.get("name") or "AURA Playlist"),
                query=str(params.get("query") or ""),
                genre=str(params.get("genre") or ""),
                max_items=int(params.get("max_items") or 20),
            )
        elif capability == "media.playback_intent":
            media_id = str(params.get("media_id") or "").strip()
            query = str(params.get("query") or "").strip()
            if not media_id and query:
                found = center.search(query, limit=1)
                if found["items"]:
                    media_id = str(found["items"][0].get("media_id") or "")
            if not media_id:
                raise ValueError("no matching media item")
            result = center.playback_intent(
                media_id,
                action=str(params.get("action") or "play"),
            )
        else:
            raise ValueError(f"unsupported M180 capability: {capability}")

        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "m180_result": result,
            "player_mutation_performed": False,
            "external_account_mutation_performed": False,
        }

# AURA_M180_R3_CONTROLLED_LOCAL_PLAYER
_AURA_M180_R3_BASE_PROVIDER = MusicMediaCenterProvider


class MusicMediaCenterProvider(_AURA_M180_R3_BASE_PROVIDER):
    def __init__(self, index_path=None):
        super().__init__(index_path=index_path)
        from integrations import IntegrationCapability, IntegrationManifest
        old = self._manifest
        metadata = dict(old.metadata or {})
        metadata.update({
            "controlled_local_player": True,
            "explicit_confirmation_required_for_launch": True,
            "stop_pause_not_exposed_in_r3": True,
        })
        self._manifest = IntegrationManifest(
            provider_id=old.provider_id,
            display_name=old.display_name,
            provider_version="1.8.0-m180.r3",
            capabilities=tuple(old.capabilities) + (
                IntegrationCapability("media.list_items", "media.list_items", "List indexed local media items.", "low", False, "read", True),
                IntegrationCapability("media.play_confirmed", "media.play_confirmed", "Launch one indexed local media item after explicit user confirmation.", "medium", True, "launch", True),
                IntegrationCapability("media.player_status", "media.player_status", "Read the last controlled local player session.", "low", False, "read", True),
            ),
            auth_kind=old.auth_kind,
            metadata=metadata,
        )

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        params = dict(request.params or {})

        if capability == "media.list_items":
            data = self._load()
            rows = [
                dict(x)
                for x in data.get("items") or []
                if isinstance(x, Mapping)
            ]
            limit = max(1, min(int(params.get("limit") or 20), 100))
            result = {
                "kind": "media_item_list",
                "count": min(len(rows), limit),
                "items": rows[:limit],
                "index_captured_at": data.get("captured_at"),
                "player_mutation_performed": False,
            }

        elif capability == "media.play_confirmed":
            from runtime.aura_controlled_local_player_v180 import (
                ControlledLocalPlayer,
            )
            player = ControlledLocalPlayer(
                index_path=self.index_path,
                session_path=Path(
                    os.environ.get(
                        "AURA_M180_PLAYER_SESSION",
                        r"C:\AURA GPT version\data\media\player_session_v180.json",
                    )
                ),
            )
            result = player.launch(
                media_id=str(params.get("media_id") or ""),
                query=str(params.get("query") or ""),
                first=bool(params.get("first")),
                user_confirmed=bool(params.get("explicit_confirmation")),
            )

        elif capability == "media.player_status":
            from runtime.aura_controlled_local_player_v180 import (
                ControlledLocalPlayer,
            )
            player = ControlledLocalPlayer(
                index_path=self.index_path,
                session_path=Path(
                    os.environ.get(
                        "AURA_M180_PLAYER_SESSION",
                        r"C:\AURA GPT version\data\media\player_session_v180.json",
                    )
                ),
            )
            result = player.status()

        else:
            return super().execute(request)

        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "m180_result": result,
            "filesystem_mutation_performed": False,
            "external_account_mutation_performed": False,
        }

# AURA_M180_UI1_MUSIC_PLAYER_PANEL
_AURA_M180_UI1_BASE_PROVIDER = MusicMediaCenterProvider

class MusicMediaCenterProvider(_AURA_M180_UI1_BASE_PROVIDER):
    def __init__(self, index_path=None):
        super().__init__(index_path=index_path)
        old = self._manifest
        metadata = dict(old.metadata or {})
        metadata.update({
            "music_player_ui": True,
            "windows_media_keys": True,
            "post_certification_ui_enhancement": True,
        })
        self._manifest = IntegrationManifest(
            provider_id=old.provider_id,
            display_name=old.display_name,
            provider_version="1.8.0-m180.ui1",
            capabilities=tuple(old.capabilities) + (
                IntegrationCapability(
                    "media.player_key",
                    "media.player_key",
                    "Send one controlled Windows media key to the active local player.",
                    "medium",
                    True,
                    "local_control",
                    True,
                ),
            ),
            auth_kind=old.auth_kind,
            metadata=metadata,
        )

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        if capability != "media.player_key":
            return super().execute(request)
        from runtime.aura_windows_media_keys_v180 import send_media_key
        result = send_media_key(str((request.params or {}).get("action") or ""))
        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "m180_result": result,
            "filesystem_mutation_performed": False,
            "external_account_mutation_performed": False,
        }

# AURA_M180_UI3_PC_BROWSER
_AURA_M180_UI3_BASE_PROVIDER = MusicMediaCenterProvider

class MusicMediaCenterProvider(_AURA_M180_UI3_BASE_PROVIDER):
    def __init__(self, index_path=None):
        super().__init__(index_path=index_path)
        old = self._manifest
        metadata = dict(old.metadata or {})
        metadata.update({
            "native_pc_browser": True,
            "pick_music_anywhere": True,
            "pick_playlist_anywhere": True,
            "pick_folder_anywhere": True,
        })
        self._manifest = IntegrationManifest(
            provider_id=old.provider_id,
            display_name=old.display_name,
            provider_version="1.8.0-m180.ui3",
            capabilities=tuple(old.capabilities) + (
                IntegrationCapability("media.pick_local_music","media.pick_local_music","Choose local media files with a native Windows picker.","medium",True,"local_read",True),
                IntegrationCapability("media.pick_local_playlist","media.pick_local_playlist","Choose a local M3U/M3U8/PLS playlist with a native Windows picker.","medium",True,"local_read",True),
                IntegrationCapability("media.pick_local_folder","media.pick_local_folder","Choose a local folder and index its media files.","medium",True,"local_read",True),
            ),
            auth_kind=old.auth_kind,
            metadata=metadata,
        )

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        if capability not in {
            "media.pick_local_music",
            "media.pick_local_playlist",
            "media.pick_local_folder",
        }:
            return super().execute(request)

        from runtime.aura_music_pc_browser_v180 import (
            browse_music, browse_playlist, browse_folder
        )

        if capability == "media.pick_local_music":
            result = browse_music()
        elif capability == "media.pick_local_playlist":
            result = browse_playlist()
        else:
            result = browse_folder()

        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "m180_result": result,
            "media_file_mutation_performed": False,
            "external_account_mutation_performed": False,
        }

# AURA_M180_UI4_R3_R1_R1_VLC_PREMIUM_PLAYER
_AURA_M180_UI4_R3_R1_BASE_PROVIDER = MusicMediaCenterProvider

class MusicMediaCenterProvider(_AURA_M180_UI4_R3_R1_BASE_PROVIDER):
    def __init__(self, index_path=None):
        super().__init__(index_path=index_path)
        old = self._manifest
        metadata = dict(old.metadata or {})
        metadata.update({
            "premium_vlc_rc_control": True,
            "stop_pause_not_exposed_in_r3": False,
            "premium_live_status": True,
        })
        self._manifest = IntegrationManifest(
            provider_id=old.provider_id,
            display_name=old.display_name,
            provider_version="1.8.0-m180.ui4.r3",
            capabilities=tuple(old.capabilities) + (
                IntegrationCapability(
                    "media.player_control",
                    "media.player_control",
                    "Control the confirmed local VLC session (pause/resume/stop/seek/volume).",
                    "low",
                    True,
                    "local_control",
                    True,
                ),
            ),
            auth_kind=old.auth_kind,
            metadata=metadata,
        )

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        if capability != "media.player_control":
            return super().execute(request)

        from runtime.aura_controlled_local_player_v180 import ControlledLocalPlayer
        player = ControlledLocalPlayer(
            index_path=self.index_path,
            session_path=Path(
                os.environ.get(
                    "AURA_M180_PLAYER_SESSION",
                    r"C:\AURA GPT version\data\media\player_session_v180.json",
                )
            ),
        )
        params = dict(request.params or {})
        result = player.control(
            str(params.get("action") or ""),
            params.get("value"),
        )
        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "m180_result": result,
            "filesystem_mutation_performed": False,
            "external_account_mutation_performed": False,
        }

# AURA_M180_UI4_R3_R2_VLC_PREMIUM_PLAYER
_AURA_M180_UI4_R3_BASE_PROVIDER = MusicMediaCenterProvider

class MusicMediaCenterProvider(_AURA_M180_UI4_R3_BASE_PROVIDER):
    def __init__(self, index_path=None):
        super().__init__(index_path=index_path)
        old = self._manifest
        metadata = dict(old.metadata or {})
        metadata.update({
            "premium_vlc_rc_control": True,
            "stop_pause_not_exposed_in_r3": False,
            "premium_live_status": True,
        })
        self._manifest = IntegrationManifest(
            provider_id=old.provider_id,
            display_name=old.display_name,
            provider_version="1.8.0-m180.ui4.r3",
            capabilities=tuple(old.capabilities) + (
                IntegrationCapability(
                    "media.player_control",
                    "media.player_control",
                    "Control the confirmed local VLC session (pause/resume/stop/seek/volume).",
                    "low",
                    True,
                    "local_control",
                    True,
                ),
            ),
            auth_kind=old.auth_kind,
            metadata=metadata,
        )

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        if capability != "media.player_control":
            return super().execute(request)

        from runtime.aura_controlled_local_player_v180 import ControlledLocalPlayer
        player = ControlledLocalPlayer(
            index_path=self.index_path,
            session_path=Path(
                os.environ.get(
                    "AURA_M180_PLAYER_SESSION",
                    r"C:\AURA GPT version\data\media\player_session_v180.json",
                )
            ),
        )
        params = dict(request.params or {})
        result = player.control(
            str(params.get("action") or ""),
            params.get("value"),
        )
        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "m180_result": result,
            "filesystem_mutation_performed": False,
            "external_account_mutation_performed": False,
        }
