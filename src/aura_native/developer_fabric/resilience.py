from __future__ import annotations
import os,platform,shutil,tempfile
from pathlib import Path
from dataclasses import dataclass
class CircuitBreaker:
 def __init__(self,threshold=3,cooldown=30,clock=None): self.threshold=threshold; self.cooldown=cooldown; self.clock=clock or __import__('time').monotonic; self.failures=0; self.opened_at=None; self.state='CLOSED'
 def allow(self):
  if self.state=='OPEN' and self.clock()-self.opened_at>=self.cooldown: self.state='HALF_OPEN'
  return self.state!='OPEN'
 def success(self): self.failures=0; self.state='CLOSED'; self.opened_at=None
 def failure(self):
  self.failures+=1
  if self.state=='HALF_OPEN' or self.failures>=self.threshold: self.state='OPEN'; self.opened_at=self.clock()
@dataclass(frozen=True)
class AgentDetection: installed:bool; available:bool; reason:str=''
def detect_agent(executables,platforms,which=shutil.which,system=platform.system):
 if platforms and system() not in platforms:return AgentDetection(False,False,'unsupported_platform')
 found=any(which(x) for x in executables); return AgentDetection(found,found,'installed' if found else 'missing')
class AgentSandbox:
 def __init__(self,source_root): self.source=Path(source_root).resolve(); self.root=Path(tempfile.mkdtemp(prefix='aura-agent-'))
 def prepare(self):
  target=self.root/'workspace'; shutil.copytree(self.source,target,dirs_exist_ok=True); return target
 def harvest(self,workspace):
  out={}
  for p in Path(workspace).rglob('*'):
   if p.is_file(): out[str(p.relative_to(workspace))]=p.read_text(encoding='utf-8',errors='replace')
  return out
 def env(self,base=None):
  allow={'SystemRoot','WINDIR','PATH','TEMP','TMP','PYTHONPATH'}; src=base or os.environ; return {k:v for k,v in src.items() if k in allow}
 def close(self): shutil.rmtree(self.root,ignore_errors=True)
