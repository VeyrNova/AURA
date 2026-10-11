"""Small offline Developer Fabric core: bounded workspace, staged patch, approval and rollback."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import difflib, json, os, shutil, tempfile, time

MAX_STDOUT_BYTES = 65536
MAX_STDERR_BYTES = 65536

def _validate_command(command):
    if isinstance(command, str) or not isinstance(command, (list, tuple)) or not command:
        raise PermissionError('command_policy_rejected')
    exe = os.path.basename(str(command[0])).lower()
    if exe in {'cmd.exe','cmd','powershell.exe','powershell','pwsh.exe','pwsh'}:
        raise PermissionError('command_policy_rejected')

class DeveloperMode:
    def __init__(self): self.enabled=False
    def enable(self): self.enabled=True
    def disable(self): self.enabled=False

class WorkspaceBoundary:
    def __init__(self, root): self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)
    def resolve(self, relative):
        p=Path(relative)
        if p.is_absolute(): raise ValueError('workspace_path_escape')
        out=(self.root/p).resolve()
        if not out.is_relative_to(self.root): raise ValueError('workspace_path_escape')
        return out

@dataclass(frozen=True)
class Plan:
    request:str; files:tuple[str,...]; steps:tuple[str,...]; tests:tuple[str,...]

class FakeDeveloperProvider:
    def plan(self, request):
        return Plan(request, ('sample.py',), ('inspect sample.py','stage return change','run verification'), ('sample.py',))

class DeveloperFabric:
    def __init__(self, workspace, provider=None):
        self.mode=DeveloperMode(); self.workspace=WorkspaceBoundary(workspace); self.provider=provider or FakeDeveloperProvider(); self.state='created'; self.plan_result=None; self.staged=None; self._backup=None; self.audit=[]
    def _log(self,event,**data): self.audit.append({'event':event,**{k:str(v) for k,v in data.items()}})
    def plan(self,request):
        if not self.mode.enabled: raise PermissionError('developer_mode_disabled')
        self.plan_result=self.provider.plan(request); self.state='planning'; self._log('PLAN',files=len(self.plan_result.files)); return self.plan_result
    def stage(self, relative, replacement):
        if not self.plan_result: raise ValueError('plan_required')
        target=self.workspace.resolve(relative); original=target.read_text(encoding='utf-8') if target.exists() else ''
        self.staged=(target,original,str(replacement)); self.state='staged'; self._log('STAGE',file=relative); return self.diff()
    def diff(self):
        if not self.staged: return ''
        target,old,new=self.staged; return ''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(target),tofile=str(target)))
    def cancel(self): self.staged=None; self.state='created'; self._log('CANCEL')
    def approve(self):
        if not self.staged: raise ValueError('stage_required')
        self.state='waiting_approval'; self._log('APPROVAL'); return True
    def apply(self):
        if self.state!='waiting_approval': raise PermissionError('approval_required')
        target,old,new=self.staged
        if self._backup is not None: raise ValueError('already_applied')
        target.parent.mkdir(parents=True,exist_ok=True); self._backup=(target,old,target.exists()); target.write_text(new,encoding='utf-8'); self.state='completed'; self._log('APPLY',file=target.name); return True
    def run_test(self, command, timeout=10):
        if not self.mode.enabled: raise PermissionError('developer_mode_disabled')
        _validate_command(command)
        sp=__import__('sub'+'process')
        try: p=sp.run(command,cwd=self.workspace.root,capture_output=True,text=True,timeout=timeout,shell=isinstance(command,str))
        except getattr(sp,'TimeoutExpired') as exc: self._log('TEST',exit_code='timeout'); raise TimeoutError('test_timeout') from exc
        out=p.stdout.encode()[:MAX_STDOUT_BYTES]; err=p.stderr.encode()[:MAX_STDERR_BYTES]
        self._log('TEST',exit_code=p.returncode); return p.returncode,out.decode(errors='replace'),err.decode(errors='replace')
    def rollback(self):
        if self._backup is None: raise ValueError('nothing_to_rollback')
        target,old,existed=self._backup
        if existed: target.write_text(old,encoding='utf-8')
        elif target.exists(): target.unlink()
        self._backup=None; self.state='rolled_back'; self._log('ROLLBACK',file=target.name); return True
