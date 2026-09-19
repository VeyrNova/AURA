from __future__ import annotations
import json,statistics
from datetime import datetime,timezone
from pathlib import Path
from runtime.aura_youtube_studio_copilot_v150 import YouTubeStudioCopilot

class YouTubeSnapshotAdapter:
 def __init__(self,path):
  self.path=Path(path); self.data=json.loads(self.path.read_text(encoding="utf-8-sig")); self.channel=self.data.get("channel") or {}; self.videos=list(self.data.get("videos") or [])
 def _rows(self):
  start=str((self.data.get("analytics_period") or {}).get("start_date") or "")
  out=[]
  for row in self.videos:
   r=dict(row); pct=float(r.get("average_view_percentage") or 0); avd=float(r.get("average_view_duration_seconds") or 0)
   r["published_at"]=start+"T00:00:00Z"
   if pct>0 and avd>0: r["duration_seconds"]=avd/(pct/100.0)
   r["impressions"]=0; r["ctr_percent"]=0; out.append(r)
  return out
 def studio(self): return YouTubeStudioCopilot(self._rows(),channel_name=str(self.channel.get("title") or ""))
 def scorecards(self):
  rows=self.studio().scorecards()
  for r in rows: r["score"]=round(min(100.0,float(r.get("score") or 0)/0.75),2); r["ctr_status"]="unavailable"
  return rows
 def opportunity_board(self):
  s=self.studio(); b=s.benchmarks(); scores={x["video_id"]:x for x in self.scorecards()}; items=[]
  for r in s._rows():
   ret=float(r.get("retention_percent") or 0); vel=float(r.get("views_per_day") or 0)
   if ret<float(b.get("median_retention_percent") or 0) and vel>=float(b.get("median_views_per_day") or 0): action="hook_retention"; reason="Vitesse solide mais retention sous la mediane: renforcer le hook."
   elif ret>=float(b.get("median_retention_percent") or 0) and vel>=float(b.get("median_views_per_day") or 0): action="double_down"; reason="Retention et vitesse au-dessus des medianes; CTR indisponible."
   elif ret>=float(b.get("median_retention_percent") or 0): action="distribution"; reason="Retention solide mais vitesse faible."
   else: action="monitor"; reason="Signaux mixtes; CTR indisponible, aucune conclusion packaging n'est fabriquee."
   items.append({"video_id":r["video_id"],"title":r["title"],"score":scores[r["video_id"]]["score"],"action":action,"reason":reason})
  items.sort(key=lambda x:(-x["score"],x["title"].casefold()))
  return {"kind":"opportunity_board","count":len(items),"items":items,"ctr_available":False,"read_only":True}
 def cadence(self):
  ds=[]
  for r in self.videos:
   try: ds.append(datetime.fromisoformat(str(r.get("published_at")).replace("Z","+00:00")).astimezone(timezone.utc))
   except Exception: pass
  ds.sort(); gaps=[(ds[i]-ds[i-1]).total_seconds()/86400 for i in range(1,len(ds))]
  return {"kind":"publishing_cadence","dated_video_count":len(ds),"median_gap_days":round(float(statistics.median(gaps)) if gaps else 0,2),"average_gap_days":round(sum(gaps)/len(gaps) if gaps else 0,2),"read_only":True}
 def brief(self):
  sc=self.scorecards(); tags={}
  for src in self.videos:
   score=next((x["score"] for x in sc if x["video_id"]==src["video_id"]),0)
   for tag in src.get("tags") or []: tags.setdefault(str(tag).casefold(),[]).append(score)
  topics=[{"tag":k,"mean_score":round(sum(v)/len(v),2),"sample_size":len(v)} for k,v in tags.items()]
  topics.sort(key=lambda x:(-x["mean_score"],-x["sample_size"],x["tag"]))
  return {"kind":"next_upload_brief","top_reference_videos":[{"video_id":x["video_id"],"title":x["title"],"score":x["score"]} for x in sc[:3]],"priority_topics":topics[:8],"recommended_focus":"Prioriser les angles des meilleures videos selon retention et vitesse; CTR non disponible.","cadence":self.cadence(),"read_only":True}
 def snapshot(self):
  return {"kind":"channel_snapshot","real_channel":self.channel,"analytics_period":self.data.get("analytics_period"),"metric_availability":self.data.get("metric_availability"),"captured_at":self.data.get("captured_at"),"top_videos":self.scorecards()[:10],"read_only":True}
