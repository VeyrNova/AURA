from __future__ import annotations
from pathlib import Path
try:
 from PySide6.QtCore import QObject, Signal, Slot, Property, QAbstractListModel, QModelIndex, Qt
except ImportError:
 QObject=object
class DeveloperFabricBridge(QObject):
 developerModeChanged=Signal(bool); activeProjectChanged=Signal(); jobChanged=Signal()
 def __init__(self,service=None,parent=None):
  super().__init__(parent) if parent else super().__init__(); self.service=service; self._mode=False; self._project=None; self._job=None
 @Property(bool,notify=developerModeChanged)
 def developerModeEnabled(self): return self._mode
 @Property(bool,notify=activeProjectChanged)
 def hasActiveProject(self): return self._project is not None
 @Property(str,notify=activeProjectChanged)
 def activeProjectId(self): return getattr(self._project,'project_id','')
 @Property(str,notify=activeProjectChanged)
 def activeProjectName(self): return getattr(self._project,'display_name','')
 @Property(str,notify=activeProjectChanged)
 def activeWorkspace(self): return str(getattr(self._project,'workspace_root',''))
 @Property(str,notify=jobChanged)
 def currentJobId(self): return getattr(self._job,'job_id','')
 @Property(str,notify=jobChanged)
 def currentJobState(self): return getattr(self._job,'state','')
 @Property(bool,notify=jobChanged)
 def currentJobHasDiff(self): return bool(getattr(self._job,'staged_changes',None))
 @Property(bool,notify=jobChanged)
 def currentJobCanApprove(self): return getattr(self._job,'state','')=='WAITING_APPROVAL'
 @Property(bool,notify=jobChanged)
 def currentJobCanRollback(self): return bool(getattr(self._job,'rollback_available',False))
 @Slot()
 def enableDeveloperMode(self): self.service.enable(); self._mode=True; self.developerModeChanged.emit(True)
 @Slot()
 def disableDeveloperMode(self): self._mode=False; self.service.enabled=False; self.developerModeChanged.emit(False)
 @Slot(str,str)
 def setActiveProject(self,path,name): self._project=self.service.active_project=__import__('aura_native.developer_fabric.adf',fromlist=['ActiveProject']).ActiveProject(Path(path).name,name,path); self.activeProjectChanged.emit()
 @Slot()
 def clearActiveProject(self): self._project=None; self.service.active_project=None; self.activeProjectChanged.emit()
 @Slot(str)
 def createDeveloperJob(self,request): self._job=self.service.create_job(request); self.jobChanged.emit()
 @Slot(str)
 def selectDeveloperJob(self,job_id): self._job=self.service.jobs.load(job_id); self.jobChanged.emit()
 @Slot(str)
 def planDeveloperJob(self,job_id): self._job=self.service.plan(self.service.jobs.load(job_id)); self.jobChanged.emit()
 @Slot(str)
 def stageDeveloperJob(self,job_id):
  self._job=self.service.jobs.load(job_id); target=Path(self._job.workspace_root)/'sample.py'; content=target.read_text(encoding='utf-8') if target.exists() else 'def answer():\n    return 42\n'; self.service.stage(self._job,'sample.py',content); self.jobChanged.emit()
 @Slot(str)
 def runDeveloperJobTests(self,job_id): self._job=self.service.jobs.load(job_id); self.service.test(self._job,['python','-c','pass']); self.jobChanged.emit()
 @Slot(str)
 def approveDeveloperJob(self,job_id): self._job=self.service.jobs.load(job_id); self.service.approve(self._job); self.jobChanged.emit()
 @Slot(str)
 def approveAndApplyDeveloperJob(self,job_id): self.approveDeveloperJob(job_id); self._job=self.service.apply(self._job); self.jobChanged.emit()
 @Slot(str)
 def cancelDeveloperJob(self,job_id): self._job=self.service.jobs.load(job_id); self._job.state='CANCELLED'; self.service.jobs.save(self._job); self.jobChanged.emit()
 @Slot(str)
 def rollbackDeveloperJob(self,job_id): self._job=self.service.jobs.load(job_id); self.service.rollback(self._job); self.jobChanged.emit()

class _Model(QAbstractListModel):
 countChanged=Signal()
 def __init__(self,items=(),parent=None): super().__init__(parent); self.items=list(items)
 def rowCount(self,parent=QModelIndex()): return 0 if parent.isValid() else len(self.items)
 def data(self,index,role=Qt.DisplayRole):
  if not index.isValid() or index.model() is not self or index.column()!=0 or not 0<=index.row()<len(self.items): return None
  name=self.roleNames().get(role)
  if name is None: return None
  key=name.decode(); item=self.items[index.row()]; return item.get(key, '') if isinstance(item,dict) else getattr(item,key,'')
 def roleNames(self): return {Qt.UserRole+i:n.encode() for i,n in enumerate(self.role_names)}
 @Property(int,notify=countChanged)
 def count(self): return len(self.items)
 def replace_items(self,items):
  replacement=list(items)
  self.beginResetModel(); self.items=replacement; self.endResetModel(); self.countChanged.emit()
 def append_item(self,item):
  self.beginInsertRows(QModelIndex(),len(self.items),len(self.items)); self.items.append(item); self.endInsertRows(); self.countChanged.emit()
class DeveloperProjectsModel(_Model): role_names=('projectId','displayName','workspace','lastOpenedAt','isActive')
class DeveloperJobsModel(_Model): role_names=('jobId','requestSummary','state','updatedAt','providerId','agentId','testStatus','approvalStatus','hasDiff','rollbackAvailable')
class DeveloperProvidersModel(_Model): role_names=('providerId','displayName','state','configured','eligible','quotaState','health','selected')
class DeveloperAgentsModel(_Model): role_names=('agentId','displayName','installed','available','supportLevel','protocol','bridgeMode')
