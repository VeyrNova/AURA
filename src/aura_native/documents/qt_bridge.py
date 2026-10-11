from __future__ import annotations

from pathlib import Path
from threading import Thread

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from .service import DocumentsError


class NativeDocumentsBridge(QObject):
    changed=Signal(); _loaded=Signal(object,str,str,int)
    def __init__(self,service,parent=None,opener=None):
        super().__init__(parent); self.service=service; self._opener=opener or QDesktopServices.openUrl
        self._items=[]; self._path=""; self._state="idle"; self._error=""; self._query=""; self._generation=0; self._document={}; self._dirty=False; self._pending={}
        self._loaded.connect(self._apply_loaded)
    @Property('QVariantList',notify=changed)
    def items(self): return list(self._items)
    @Property(str,notify=changed)
    def currentPath(self): return self._path
    @Property(str,notify=changed)
    def searchQuery(self): return self._query
    @Property(str,notify=changed)
    def selectedIdentity(self): return str(self._document.get("path") or "")
    @Property(str,notify=changed)
    def openedIdentity(self): return str(self._document.get("path") or "")
    @Property(str,notify=changed)
    def state(self): return self._state
    @Property(str,notify=changed)
    def errorCode(self): return self._error
    @Property('QVariantMap',notify=changed)
    def document(self): return dict(self._document)
    @Property(bool,notify=changed)
    def dirty(self): return self._dirty
    @Property('QVariantMap',notify=changed)
    def pendingAction(self): return dict(self._pending)
    def _async(self,kind,operation):
        self._generation+=1; generation=self._generation; self._state="loading"; self._error=""; self.changed.emit()
        def worker():
            try: rows=operation(); error=""
            except DocumentsError as exc: rows=[]; error=exc.code
            self._loaded.emit(rows,error,kind,generation)
        Thread(target=worker,daemon=True,name="AuraNativeDocuments").start()
    @Slot(str)
    def listDirectory(self,path=""):
        target=str(path or "")
        if not target: self.service.ensure_root()
        self._async("list",lambda:[x.to_dict() for x in self.service.list_directory(target)]); self._path=target
    @Slot(str)
    def search(self,query):
        text=str(query or "").strip()
        if not text: self.listDirectory(self._path); return
        self._query=text
        self._async("search",lambda:[x.to_dict() for x in self.service.search(text,cancelled=lambda:self._generation<=0)])
    @Slot(object,str,str,int)
    def _apply_loaded(self,rows,error,kind,generation):
        if generation!=self._generation:return
        self._items=list(rows); self._error=error; self._state="error" if error else "ready" if self._items else "empty"; self.changed.emit()
    @Slot(str)
    def openItem(self,path):
        try:
            doc=self.service.read_text(path); self._document=doc.to_dict(); self._dirty=False; self._error=""; self._state="detail"
        except DocumentsError as exc:
            self._document={"path":str(path or ""),"binary":exc.code in {"UNSUPPORTED_BINARY","FILE_TOO_LARGE"}}; self._error=exc.code; self._state="detail" if self._document.get("binary") else "error"
        self.changed.emit()
    @Slot(str)
    def setEditorText(self,text):
        if self._document: self._document["content"]=str(text); self._dirty=True; self.changed.emit()
    @Slot(bool,result=bool)
    def saveDocument(self,overwrite_external=False):
        if not self._document:return False
        try: doc=self.service.save_text(self._document["path"],self._document.get("content",""),self._document.get("fingerprint",""),overwrite_external=bool(overwrite_external)); self._document=doc.to_dict(); self._dirty=False; self._error=""; self._state="saved"
        except DocumentsError as exc: self._error=exc.code; self._state="error"; self.changed.emit(); return False
        self.changed.emit(); return True
    @Slot(str,str,str,result=bool)
    def createText(self,parent,name,content=""):
        try:self.service.create_text(parent,name,content);self.listDirectory(parent);return True
        except DocumentsError as exc:self._error=exc.code;self._state="error";self.changed.emit();return False
    @Slot(str,str,result=bool)
    def createFolder(self,parent,name):
        try:self.service.create_folder(parent,name);self.listDirectory(parent);return True
        except DocumentsError as exc:self._error=exc.code;self._state="error";self.changed.emit();return False
    @Slot(str,str,result=bool)
    def moveItem(self,source,destination):
        try:self.service.move(source,destination);self.listDirectory(self._path);return True
        except DocumentsError as exc:self._error=exc.code;self._state="error";self.changed.emit();return False
    @Slot(str,str,bool)
    def requestDelete(self,path,name,is_folder=False): self._pending={"kind":"delete","path":str(path),"name":str(name),"isFolder":bool(is_folder)};self.changed.emit()
    @Slot()
    def cancelPending(self):self._pending={};self.changed.emit()
    @Slot(bool,result=bool)
    def confirmDelete(self,recursive=False):
        if self._pending.get("kind")!="delete":return False
        try:self.service.delete(self._pending["path"],confirmed=True,recursive_confirmed=bool(recursive));self._pending={};self.listDirectory(self._path);return True
        except DocumentsError as exc:self._error=exc.code;self._state="error";self.changed.emit();return False
    @Slot(str,result=bool)
    def openExternal(self,path):
        try: target=self.service.repository.resolve(path,must_exist=True)
        except Exception:return False
        return bool(self._opener(QUrl.fromLocalFile(str(target))))
    @Slot()
    def cancelOperation(self):self._generation+=1;self._state="idle";self.changed.emit()
