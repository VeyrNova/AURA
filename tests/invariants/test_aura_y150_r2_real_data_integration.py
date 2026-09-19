from __future__ import annotations
import hashlib,json,sys,tempfile
from pathlib import Path
ROOT=Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from action_receipts import ActionReceiptService,ActionReceiptStore
from integrations.registry import IntegrationRegistry
from runtime.personal_integrations import IntegrationRuntimeContext,PersonalIntegrationDispatcher
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123
from runtime.aura_youtube_snapshot_adapter_v150 import YouTubeSnapshotAdapter
DATA=ROOT/"data"/"youtube"/"neural_echo_youtube_snapshot_v150.json";ROADMAP=ROOT/"data"/"roadmap"/"aura_master_roadmap_v2.json"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class DenyAll:
 def authorize(self,action,params,*,user_confirmed=False):return "DENY"
road_sha=sha(ROADMAP);d=json.loads(DATA.read_text(encoding="utf-8-sig"))
assert d["channel"]["current_stats"]=={"subscribers":116,"views":56294,"videos":87}
assert d["channel"]["period_growth"]=={"subscribers_gained":21,"views_gained":5304,"videos_published":4}
assert len(d["videos"])==10 and d["metric_availability"]["impression_ctr"] is False
a=YouTubeSnapshotAdapter(DATA);b=a.opportunity_board();assert b["count"]==10 and b["ctr_available"] is False and all(x["action"]!="packaging" for x in b["items"])
with tempfile.TemporaryDirectory(prefix="aura_y150_r2_") as td:
 receipts=ActionReceiptService(store=ActionReceiptStore(Path(td)/"r.sqlite3"));outer=IntegrationRegistry(security_engine=DenyAll(),receipt_service=receipts);ctx=IntegrationRuntimeContext(registry=outer,receipt_service=receipts,email_backend=None,calendar_backend=None,timezone_name="Europe/Paris");disp=PersonalIntegrationDispatcher(context=ctx)
 r=disp.handle_text("analyse ma chaine youtube");assert r.status=="succeeded";assert receipts.get_receipt(r.receipt_id).status=="succeeded";p=build_personal_result_payload_v123(r,getattr(disp,"_last_request",None));assert p["source"]=="YOUTUBE" and p["title"]=="BILAN YOUTUBE" and any(x["title"]=="ABONNES" and x["snippet"]=="116" for x in p["items"])
 r=disp.handle_text("montre mes opportunites youtube");assert r.status=="succeeded";p=build_personal_result_payload_v123(r,getattr(disp,"_last_request",None));assert p["title"]=="OPPORTUNITES YOUTUBE" and p["count"]==10
 r=disp.handle_text("que dois-je publier ensuite sur youtube");assert r.status=="succeeded";p=build_personal_result_payload_v123(r,getattr(disp,"_last_request",None));assert p["title"]=="PROCHAINE VIDEO"
assert sha(ROADMAP)==road_sha
print("[PASS] real Neural Echo Music snapshot: 116 subs / 56294 views / 87 videos")
print("[PASS] real 29-day growth: +21 subs / +5304 views / 4 uploads")
print("[PASS] 10 real per-video analytics rows")
print("[PASS] missing CTR is truthful; packaging is not fabricated")
print("[PASS] dedicated read-only YouTube registry + canonical receipts")
print("[PASS] natural-language YouTube commands + source YOUTUBE")
print("[PASS] live Roadmap unchanged")
