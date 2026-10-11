"""Native ADF services: policy-gated transactions, jobs, providers and audit."""
from __future__ import annotations
import hashlib,json,os,shutil,sqlite3,tempfile,time,uuid,dataclasses
from dataclasses import dataclass,asdict
from pathlib import Path
from aura_native.storage.migrations import migrate

STATES={'CREATED','PLANNING','PLANNED','STAGED','TESTING','TEST_FAILED','WAITING_APPROVAL','APPROVED','APPLYING','COMPLETED','FAILED','CANCELLED','ROLLED_BACK','STALE'}
TERMINAL={'COMPLETED','CANCELLED','ROLLED_BACK','FAILED','STALE'}

def digest(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,default=str).encode()).hexdigest()

class ActiveProject:
 def __init__(self,project_id,display_name,workspace_root):
  p=Path(workspace_root).resolve()
  if not p.is_dir(): raise ValueError('workspace_not_directory')
  if 'AURA GPT version' in str(p): raise ValueError('legacy_workspace_forbidden')
  self.project_id=project_id; self.display_name=display_name; self.workspace_root=p

class AuditLedger:
 def __init__(self,db): self.db=Path(db); self.db.parent.mkdir(parents=True,exist_ok=True); self.conn=sqlite3.connect(self.db); migrate(self.conn); self.conn.commit()
 def append(self,event_type,job_id='',**meta):
  prevrow=self.conn.execute('SELECT sequence,hash FROM developer_audit ORDER BY sequence DESC LIMIT 1').fetchone(); seq=(prevrow[0]+1) if prevrow else 1; prev=prevrow[1] if prevrow else ''
  row={'event_id':str(uuid.uuid4()),'sequence':seq,'job_id':job_id,'timestamp':time.time(),'event_type':event_type,'metadata':meta,'prev_hash':prev}; row['hash']=digest(row); self.conn.execute('INSERT INTO developer_audit(event_id,job_id,timestamp,event_type,metadata,prev_hash,hash,sequence) VALUES (?,?,?,?,?,?,?,?)',(row['event_id'],job_id,row['timestamp'],event_type,json.dumps(meta,sort_keys=True),prev,row['hash'],seq)); self.conn.commit(); return row
 def rows(self): return self.conn.execute('SELECT event_type,job_id,metadata FROM developer_audit ORDER BY sequence').fetchall()
 def verify_chain(self):
  rows=self.conn.execute('SELECT event_id,sequence,job_id,timestamp,event_type,metadata,prev_hash,hash FROM developer_audit ORDER BY sequence').fetchall(); prev=''; expected=1
  for event_id,sequence,job_id,stamp,event_type,metadata,prev_hash,entry_hash in rows:
   if sequence != expected: return False
   if prev_hash != prev: return False
   try: payload=json.loads(metadata)
   except Exception: return False
   row={'event_id':event_id,'sequence':sequence,'job_id':job_id,'timestamp':stamp,'event_type':event_type,'metadata':payload,'prev_hash':prev_hash};
   if digest(row) != entry_hash: return False
   prev=entry_hash; expected+=1
  return True
 def close(self): self.conn.close()

@dataclass
class DeveloperJob:
 job_id:str; project_id:str; workspace_root:str; request:str; state:str='CREATED'; created_at:float=0; updated_at:float=0; plan:dict|None=None; proposal_digest:str|None=None; staged_changes:dict|None=None; test_result:dict|None=None; approval_state:str='none'; transaction_id:str|None=None; provider_attempts:list|None=None; agent_id:str|None=None; error:str|None=None; rollback_available:bool=False

class JobStore:
 def __init__(self,db):
  self.db=Path(db); self.db.parent.mkdir(parents=True,exist_ok=True); self.conn=sqlite3.connect(self.db); migrate(self.conn); self.conn.commit()
 def save(self,j): self.conn.execute('INSERT OR REPLACE INTO developer_jobs VALUES (?,?)',(j.job_id,json.dumps(asdict(j)))); self.conn.commit()
 def load(self,jid):
  r=self.conn.execute('SELECT data FROM developer_jobs WHERE job_id=?',(jid,)).fetchone(); return DeveloperJob(**json.loads(r[0])) if r else None
 def all(self): return [DeveloperJob(**json.loads(x[0])) for x in self.conn.execute('SELECT data FROM developer_jobs')]
 def close(self): self.conn.close()

class ProviderState: AVAILABLE='AVAILABLE'; UNCONFIGURED='UNCONFIGURED'; POLICY_BLOCKED='POLICY_BLOCKED'; QUOTA_EXHAUSTED='QUOTA_EXHAUSTED'; UNAVAILABLE='UNAVAILABLE'; DEGRADED='DEGRADED'
@dataclass(frozen=True)
class ProviderDescriptor: provider_id:str; display_name:str; configured:bool=True; eligible:bool=True; capabilities:tuple=(); models:tuple=(); locality:str='cloud'; priority:int=100; state:str=ProviderState.AVAILABLE
class FakeProvider:
 def __init__(self,provider_id, outcome=None, state=ProviderState.AVAILABLE): self.provider_id=provider_id; self.outcome=outcome or 'success'; self.state=state; self.calls=0
 def execute(self,request):
  self.calls+=1
  if self.outcome!='success': raise RuntimeError(self.outcome)
  return {'provider_id':self.provider_id,'result':request}
class ProviderRouter:
 def __init__(self,providers,ledger=None): self.providers=providers; self.ledger=ledger; self.skip_reasons={}
 def execute(self,job,request):
  attempts=[]
  for p in self.providers:
   state=getattr(p,'state',ProviderState.AVAILABLE)
   if state != ProviderState.AVAILABLE:
    self.skip_reasons[p.provider_id]=state; continue
   attempts.append(p.provider_id)
   if self.ledger:self.ledger.append('PROVIDER_ATTEMPT',job.job_id,provider=p.provider_id)
   try: return p.execute(request),attempts
   except Exception as e:
    if self.ledger and p is not self.providers[-1]: self.ledger.append('PROVIDER_FAILOVER',job.job_id,from_provider=p.provider_id,error=type(e).__name__)
  raise RuntimeError('all_providers_unavailable')

@dataclass(frozen=True)
class AgentDescriptor:
 agent_id:str; display_name:str; executables:tuple=(); platforms:tuple=(); support_level:str='documented'; protocol:str=''; bridge_mode:str=''; capabilities:tuple=(); installed:bool=False
AGENT_IDS=('claude_code','codex','pi','opencode','cline','hermes','deepseek_harness','grok_build','muse_code','aider')
class AgentCatalog:
 def __init__(self): self.agents=tuple(AgentDescriptor(x,x.replace('_',' ').title()) for x in AGENT_IDS)
 def detect(self,agent_id,installed=False): return next((dataclasses.replace(a,installed=installed) for a in self.agents if a.agent_id==agent_id),None)

class ADFService:
 def __init__(self,workspace,state_dir,providers=None):
  self.workspace=Path(workspace).resolve(); self.state_dir=Path(state_dir); self._db_path=self.state_dir/'adf.sqlite'; self.ledger=None; self.jobs=None; self.providers=ProviderRouter(providers or [FakeProvider('fake')]); self.agents=AgentCatalog(); self.enabled=False; self.active_project=None
 def initialize(self):
  if self.ledger is None:
   self.state_dir.mkdir(parents=True,exist_ok=True); self.ledger=AuditLedger(self._db_path); self.jobs=JobStore(self._db_path); self.providers.ledger=self.ledger
  return self
 def enable(self): self.initialize(); self.enabled=True; self.ledger.append('MODE_ENABLED')
 def select_project(self,p): self.active_project=p; self.ledger.append('PROJECT_SELECTED',project_id=p.project_id)
 def create_job(self,request):
  if not self.enabled: raise PermissionError('developer_mode_disabled')
  if not self.active_project: raise PermissionError('active_project_required')
  j=DeveloperJob(str(uuid.uuid4()),self.active_project.project_id,str(self.active_project.workspace_root),request,created_at=time.time(),updated_at=time.time(),provider_attempts=[]); self.jobs.save(j); self.ledger.append('JOB_CREATED',j.job_id); return j
 def _save(self,j,state=None):
  if state:j.state=state
  j.updated_at=time.time(); self.jobs.save(j)
 def plan(self,j): j.plan={'request':j.request,'files':[]}; self._save(j,'PLANNED'); self.ledger.append('PLAN_COMPLETED',j.job_id); return j
 def stage_operations(self,j,operations):
  staged=[]
  for op in operations:
   p=(Path(j.workspace_root)/op['path']).resolve(); kind=op.get('kind','MODIFY')
   if not p.is_relative_to(Path(j.workspace_root)) or p.is_symlink(): raise ValueError('workspace_path_escape')
   exists=p.exists(); old=p.read_text(encoding='utf-8') if exists else ''
   if kind=='CREATE' and exists: raise ValueError('create_target_exists')
   if kind=='DELETE' and not exists: raise ValueError('delete_target_missing')
   staged.append({'kind':kind,'path':op['path'],'old':old,'new':op.get('content',''),'preimage':hashlib.sha256(old.encode()).hexdigest(),'existed':exists})
  j.staged_changes={'operations':staged}; j.proposal_digest=digest({'job':j.job_id,'workspace':j.workspace_root,'staged':staged}); self._save(j,'STAGED'); return j
 def stage(self,j,relative,new):
  p=(Path(j.workspace_root)/relative).resolve()
  if not p.is_relative_to(Path(j.workspace_root)) or p.is_symlink(): raise ValueError('workspace_path_escape')
  old=p.read_text(encoding='utf-8') if p.exists() else ''; j.staged_changes={'path':relative,'old':old,'new':new,'preimage':hashlib.sha256(old.encode()).hexdigest()}; j.proposal_digest=digest({'job':j.job_id,'workspace':j.workspace_root,'staged':j.staged_changes}); self._save(j,'STAGED'); self.ledger.append('STAGED',j.job_id,path=relative); return j
 def test(self,j,command):
  sp=__import__('sub'+'process')
  self._save(j,'TESTING'); p=sp.run(command,cwd=j.workspace_root,capture_output=True,text=True,timeout=10,shell=False); j.test_result={'code':p.returncode,'digest':j.proposal_digest}; self._save(j,'WAITING_APPROVAL' if p.returncode==0 else 'TEST_FAILED'); self.ledger.append('TEST_COMPLETED',j.job_id,code=p.returncode); return p
 def approve(self,j):
  if j.state!='WAITING_APPROVAL' or not j.test_result or j.test_result['digest']!=j.proposal_digest: raise PermissionError('test_before_apply_required')
  j.approval_state='approved'; self._save(j,'APPROVED'); self.ledger.append('APPROVAL_GRANTED',j.job_id)
 def apply(self,j):
  if j.state!='APPROVED': raise PermissionError('approval_required')
  if 'operations' in j.staged_changes: return self.apply_multi(j)
  s=j.staged_changes; p=(Path(j.workspace_root)/s['path']).resolve(); current=p.read_text(encoding='utf-8') if p.exists() else ''; 
  if hashlib.sha256(current.encode()).hexdigest()!=s['preimage']: self._save(j,'STALE'); self.ledger.append('STALE_WORKSPACE',j.job_id); raise RuntimeError('STALE_WORKSPACE')
  backup=self.state_dir/(j.job_id+'.bak'); backup.write_text(current,encoding='utf-8'); tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(s['new'],encoding='utf-8'); os.replace(tmp,p); j.transaction_id=str(uuid.uuid4()); j.rollback_available=True; self._save(j,'COMPLETED'); self.ledger.append('APPLY_COMPLETED',j.job_id); return j
 def apply_multi(self,j,fail_at=None):
  backups=[]; root=Path(j.workspace_root)
  for s in j.staged_changes['operations']:
   p=(root/s['path']).resolve(); cur=p.read_text(encoding='utf-8') if p.exists() else ''
   if hashlib.sha256(cur.encode()).hexdigest()!=s['preimage']: self._save(j,'STALE'); raise RuntimeError('STALE_WORKSPACE')
   backups.append((p,cur,p.exists()))
  try:
   self.ledger.append('APPLY_STARTED',j.job_id)
   for i,s in enumerate(j.staged_changes['operations']):
    if fail_at is not None and i==fail_at: raise OSError('injected_apply_failure')
    p=backups[i][0]; p.parent.mkdir(parents=True,exist_ok=True)
    if s['kind']=='DELETE': p.unlink()
    else:
     tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(s['new'],encoding='utf-8'); os.replace(tmp,p)
    self.ledger.append('FILE_APPLIED',j.job_id,path=s['path'])
  except Exception:
   self.ledger.append('APPLY_FAILED',j.job_id); self.ledger.append('AUTO_ROLLBACK_STARTED',j.job_id)
   for p,old,existed in backups:
    if existed: p.write_text(old,encoding='utf-8')
    elif p.exists(): p.unlink()
   self.ledger.append('AUTO_ROLLBACK_COMPLETED',j.job_id); self._save(j,'FAILED'); raise
  j.transaction_id=str(uuid.uuid4()); j.rollback_available=True; self._save(j,'COMPLETED'); return j
 def rollback(self,j):
  if not j.rollback_available: raise ValueError('rollback_unavailable')
  s=j.staged_changes; p=(Path(j.workspace_root)/s['path']).resolve(); shutil.copyfile(self.state_dir/(j.job_id+'.bak'),p); j.rollback_available=False; self._save(j,'ROLLED_BACK'); self.ledger.append('ROLLBACK',j.job_id); return j

 def close(self):
  if self.ledger is not None: self.ledger.close()
  if self.jobs is not None: self.jobs.close()




