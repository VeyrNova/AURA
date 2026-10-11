from pathlib import Path
class ProjectPickerService:
 def __init__(self,root=None): self.root=Path(root).resolve() if root else None
 def validate(self,path):
  p=Path(path).resolve()
  if not p.is_dir(): raise ValueError('project_not_directory')
  if 'AURA GPT version' in str(p): raise ValueError('legacy_workspace_forbidden')
  if self.root and not p.is_relative_to(self.root): raise ValueError('project_outside_allowed_root')
  return p
 def choose(self,path=None): return self.validate(path) if path else None
class FakeProjectPicker(ProjectPickerService):
 def __init__(self,result=None,root=None): super().__init__(root); self.result=result
 def choose(self,path=None): return super().choose(path or self.result)
