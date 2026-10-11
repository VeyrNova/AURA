from __future__ import annotations
from PySide6.QtCore import QObject, Property, Signal, Slot
from .service import ContactsError

class NativeContactsBridge(QObject):
    changed=Signal()
    def __init__(self,service,parent=None):
        super().__init__(parent); self.service=service; self._items=[]; self._selected={}; self._state="idle"; self._error=""; self._pending={}
    @Property('QVariantList',notify=changed)
    def items(self): return list(self._items)
    @Property('QVariantMap',notify=changed)
    def selected(self): return dict(self._selected)
    @Property(str,notify=changed)
    def state(self): return self._state
    @Property(str,notify=changed)
    def errorCode(self): return self._error
    @Property('QVariantMap',notify=changed)
    def pendingAction(self): return dict(self._pending)
    def _run(self, fn):
        try: self._error=""; result=fn(); self._state="ready"; return result
        except ContactsError as e: self._error=e.code; self._state="error"; return None
    @Slot()
    def refresh(self):
        rows=self._run(self.service.list_contacts); self._items=[x.to_dict() for x in (rows or [])]; self.changed.emit()
    @Slot(str)
    def search(self,q):
        rows=self._run(lambda:self.service.search_contacts(q)); self._items=[x.to_dict() for x in (rows or [])]; self.changed.emit()
    @Slot(str)
    def selectContact(self,cid):
        c=self._run(lambda:self.service.get_contact(cid)); self._selected=c.to_dict() if c else {}; self.changed.emit()
    @Slot(str,str,str,str,str,result=bool)
    def createContact(self,name,emails="",phones="",organization="",notes=""):
        c=self._run(lambda:self.service.create_contact(name,[x for x in str(emails).split(',') if x.strip()],[x for x in str(phones).split(',') if x.strip()],organization,notes));
        if not c:return False
        self._selected=c.to_dict(); self.refresh(); return True
    @Slot(str,str,str,str,str,str,int,result=bool)
    def updateContact(self,cid,name,emails,phones,organization,notes,version=1):
        c=self._run(lambda:self.service.update_contact(cid,name,[x for x in str(emails).split(',') if x.strip()],[x for x in str(phones).split(',') if x.strip()],organization,notes,version));
        if not c:return False
        self._selected=c.to_dict(); self.refresh(); return True
    @Slot(str,str)
    def requestDelete(self,cid,name): self._pending={"kind":"delete","contactId":cid,"displayName":name}; self.changed.emit()
    @Slot()
    def cancelPending(self): self._pending={}; self.changed.emit()
    @Slot(result=bool)
    def confirmDelete(self):
        if not self._pending:return False
        ok=self._run(lambda:self.service.delete_contact(self._pending['contactId'],confirmed=True));
        if not ok:return False
        self._pending={}; self._selected={}; self.refresh(); return True
