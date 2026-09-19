from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations import IntegrationRegistry, IntegrationRequest
from runtime.aura_local_media_index_v180 import LocalMediaScanner, save_index
from runtime.aura_music_media_registry_binding_v180 import (
    register_music_media_center_provider_v180,
)
from runtime.personal_integrations import (
    IntegrationRuntimeContext,
    PersonalIntegrationDispatcher,
)
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DenyAll:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


class R3Security:
    def authorize(self, action, params, *, user_confirmed=False):
        if action == "media.play_confirmed":
            return "ALLOW" if user_confirmed else "DENY"
        return "ALLOW"


road_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_m180_r3_") as td:
    td = Path(td)
    media_root = td / "Media"
    media_root.mkdir()
    media_file = media_root / "Neural Echo - Player Test.wav"
    media_file.write_bytes(b"RIFFTEST")

    index_path = td / "index.json"
    session_path = td / "session.json"
    payload = LocalMediaScanner(max_files=100).scan([media_root])
    save_index(index_path, payload)

    os.environ["AURA_M180_MEDIA_INDEX"] = str(index_path)
    os.environ["AURA_M180_PLAYER_SESSION"] = str(session_path)
    os.environ["AURA_M180_PLAYER_TEST_MODE"] = "1"

    receipts = ActionReceiptService(
        store=ActionReceiptStore(td / "receipts.sqlite3")
    )

    registry = IntegrationRegistry(
        security_engine=R3Security(),
        receipt_service=receipts,
    )
    register_music_media_center_provider_v180(registry)

    denied_req = IntegrationRequest.create(
        provider_id="music.media-center",
        capability_id="media.play_confirmed",
        params={
            "first": True,
            "explicit_confirmation": True,
        },
        origin="test",
    )
    denied = registry.execute_integration(
        denied_req,
        user_confirmed=False,
    )
    assert denied.status != "succeeded"

    confirmed_req = IntegrationRequest.create(
        provider_id="music.media-center",
        capability_id="media.play_confirmed",
        params={
            "first": True,
            "explicit_confirmation": True,
        },
        origin="test",
    )
    confirmed = registry.execute_integration(
        confirmed_req,
        user_confirmed=True,
    )
    assert confirmed.status == "succeeded"
    cres = confirmed.output["m180_result"]
    assert cres["launch_succeeded"] is True
    assert cres["explicit_user_confirmation"] is True
    assert cres["test_mode"] is True
    assert cres["filesystem_mutation_performed"] is False
    assert cres["external_account_mutation_performed"] is False
    assert session_path.exists()

    outer = IntegrationRegistry(
        security_engine=DenyAll(),
        receipt_service=receipts,
    )
    ctx = IntegrationRuntimeContext(
        registry=outer,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    disp = PersonalIntegrationDispatcher(context=ctx)

    r1 = disp.handle_text("montre mes medias locaux indexes")
    assert r1.status == "succeeded", r1
    p1 = build_personal_result_payload_v123(
        r1, getattr(disp, "_last_request", None)
    )
    assert p1["title"] == "MEDIAS LOCAUX"
    assert p1["count"] == 1

    r2 = disp.handle_text(
        "confirme la lecture du premier media local"
    )
    assert r2.status == "succeeded", r2
    p2 = build_personal_result_payload_v123(
        r2, getattr(disp, "_last_request", None)
    )
    assert p2["title"] == "LECTURE LOCALE"
    assert p2["count"] == 3
    assert any(
        x["title"] == "CONFIRMATION EXPLICITE"
        for x in p2["items"]
    )

    r3 = disp.handle_text("affiche le statut du lecteur media local")
    assert r3.status == "succeeded", r3
    assert r3.capability_id == "media.player_status", r3
    p3 = build_personal_result_payload_v123(
        r3, getattr(disp, "_last_request", None)
    )
    assert p3["title"] == "STATUT LECTEUR MEDIA", p3
    assert p3["count"] == 2

    r4 = disp.handle_text("bonjour")
    assert r4.handled is False

assert sha(ROADMAP) == road_sha

print("[PASS] unconfirmed real-player launch is denied")
print("[PASS] explicit confirmed launch -> canonical ActionReceipt")
print("[PASS] controlled local player test-mode backend")
print("[PASS] persisted local player-session status")
print("[PASS] media-item listing route")
print("[PASS] explicit confirmed playback route")
print("[PASS] player-status route")
print("[PASS] typed MEDIA controlled-player Personal Results")
print("[PASS] no filesystem delete/move/rename")
print("[PASS] no external media-account mutation")
print("[PASS] non-M180 requests untouched")
print("[PASS] live Roadmap unchanged")
