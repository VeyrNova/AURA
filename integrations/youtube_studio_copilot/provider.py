from integrations import IntegrationCapability,IntegrationManifest,IntegrationRequest
from runtime.aura_youtube_snapshot_adapter_v150 import YouTubeSnapshotAdapter
YOUTUBE_PROVIDER_ID="youtube.studio-copilot"
class YouTubeStudioCopilotProvider:
 def __init__(self,path): self.path=path; self._manifest=IntegrationManifest(provider_id=YOUTUBE_PROVIDER_ID,display_name="AURA YouTube Studio Copilot",provider_version="1.5.0-y150.r2",capabilities=(IntegrationCapability("youtube.channel_snapshot","youtube.channel_snapshot","Read channel snapshot.","low",False,"read",True),IntegrationCapability("youtube.opportunity_board","youtube.opportunity_board","Read opportunities.","low",False,"read",True),IntegrationCapability("youtube.next_upload_brief","youtube.next_upload_brief","Read next upload brief.","low",False,"read",True),IntegrationCapability("youtube.publishing_cadence","youtube.publishing_cadence","Read cadence.","low",False,"read",True),IntegrationCapability("youtube.scorecards","youtube.scorecards","Read rankings.","low",False,"read",True)),auth_kind="local_snapshot",metadata={"read_only":True,"upload_video":False,"edit_video":False,"delete_video":False,"reply_comment":False})
 @property
 def manifest(self): return self._manifest
 def health_snapshot(self): return {"provider_id":YOUTUBE_PROVIDER_ID,"available":True,"health_state":"healthy","read_only":True}
 def execute(self,request):
  a=YouTubeSnapshotAdapter(self.path); c=str(request.capability_id or "")
  if c=="youtube.channel_snapshot": r=a.snapshot()
  elif c=="youtube.opportunity_board": r=a.opportunity_board()
  elif c=="youtube.next_upload_brief": r=a.brief()
  elif c=="youtube.publishing_cadence": r=a.cadence()
  elif c=="youtube.scorecards": r={"kind":"scorecards","count":len(a.scorecards()),"items":a.scorecards(),"read_only":True}
  else: raise ValueError(c)
  return {"provider_id":YOUTUBE_PROVIDER_ID,"capability_id":c,"youtube_result":r,"evidence_refs":()}
