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
from integrations.registry import IntegrationRegistry
from runtime.aura_local_media_index_v180 import (
    LocalMediaScanner,
    save_index,
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


road_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_m180_r2_") as td:
    td = Path(td)
    media_root = td / "Media"
    music = media_root / "Music"
    videos = media_root / "Videos"
    music.mkdir(parents=True)
    videos.mkdir(parents=True)

    (music / "Neural Echo - Neon Rain.wav").write_bytes(b"RIFFTEST")
    (music / "Neural Echo - Blue Static.flac").write_bytes(b"fLaCTEST")
    (videos / "Neural Echo - Under My Skin Visualizer.mp4").write_bytes(b"MP4TEST")
    (music / "notes.txt").write_text("ignore", encoding="utf-8")

    index_path = td / "index.json"
    payload = LocalMediaScanner(max_files=100).scan([media_root])
    save_index(index_path, payload)

    assert payload["item_count"] == 3
    assert payload["audio_count"] == 2
    assert payload["video_count"] == 1
    assert payload["filesystem_mutation_performed"] is False
    assert all(
        str(x["path"]).startswith(str(media_root))
        for x in payload["items"]
    )

    os.environ["AURA_M180_MEDIA_INDEX"] = str(index_path)

    receipts = ActionReceiptService(
        store=ActionReceiptStore(td / "receipts.sqlite3")
    )
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

    r1 = disp.handle_text("affiche ma bibliotheque media")
    assert r1.status == "succeeded", r1
    assert receipts.get_receipt(r1.receipt_id).status == "succeeded"
    p1 = build_personal_result_payload_v123(
        r1, getattr(disp, "_last_request", None)
    )
    assert p1["source"] == "MEDIA"
    assert p1["title"] == "BIBLIOTHEQUE MEDIA"
    assert p1["count"] == 4

    r2 = disp.handle_text("cherche Neon Rain dans mes medias")
    assert r2.status == "succeeded", r2
    p2 = build_personal_result_payload_v123(
        r2, getattr(disp, "_last_request", None)
    )
    assert p2["title"] == "RECHERCHE MEDIA"
    assert p2["count"] == 1
    assert p2["items"][0]["title"] == "Neon Rain"

    r3 = disp.handle_text("prepare une file media Neon")
    assert r3.status == "succeeded", r3
    p3 = build_personal_result_payload_v123(
        r3, getattr(disp, "_last_request", None)
    )
    assert p3["title"] == "FILE MEDIA"
    assert p3["count"] >= 1

    r4 = disp.handle_text("prepare une playlist Neural Echo")
    assert r4.status == "succeeded", r4
    p4 = build_personal_result_payload_v123(
        r4, getattr(disp, "_last_request", None)
    )
    assert p4["title"] == "PLAYLIST PROPOSEE"
    assert any(
        x["title"] == "AUCUNE ECRITURE EXTERNE"
        for x in p4["items"]
    )

    r5 = disp.handle_text("prepare la lecture media de Neon Rain")
    assert r5.status == "succeeded", r5
    intent = r5.payload["m180_result"]
    assert intent["state"] == "approval_required"
    assert intent["player_mutation_performed"] is False
    assert intent["external_account_mutation_performed"] is False
    p5 = build_personal_result_payload_v123(
        r5, getattr(disp, "_last_request", None)
    )
    assert p5["title"] == "INTENTION DE LECTURE"
    assert any(x["title"] == "APPROBATION REQUISE" for x in p5["items"])
    assert any(x["title"] == "AUCUNE LECTURE EFFECTUEE" for x in p5["items"])

    r6 = disp.handle_text("bonjour")
    assert r6.handled is False

assert sha(ROADMAP) == road_sha

print("[PASS] safe local audio/video scanner")
print("[PASS] persistent local media index")
print("[PASS] canonical ActionReceipt for media reads/plans")
print("[PASS] catalog-summary conversation route")
print("[PASS] local media search route")
print("[PASS] smart queue route")
print("[PASS] playlist proposal route")
print("[PASS] playback intent remains approval_required")
print("[PASS] typed MEDIA Personal Results")
print("[PASS] no real player mutation")
print("[PASS] no filesystem delete/move/rename")
print("[PASS] no external media-account mutation")
print("[PASS] non-M180 requests untouched")
print("[PASS] live Roadmap unchanged")
