from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from .models import MailMessagesModel
from aura_native.google.models import PreparedAction
from uuid import uuid4
from .links import gmail_url
from .summary import MailSummaryService
from threading import Thread

class NativeMailBridge(QObject):
    changed=Signal()
    _searchReady=Signal(object,str,int)
    def __init__(self, service, parent=None, repository=None):
        super().__init__(parent); self.service=service; self.repository=repository; self.model=MailMessagesModel(); self._query=''; self._loading=False; self._error=''; self._selected=None; self._thread=None; self._prepared=None; self._mode='inbox'; self._generation=0; self._pending_search=None; self._summary_service=MailSummaryService(); self._searchReady.connect(self._apply_search); self._poll=QTimer(self); self._poll.setInterval(10); self._poll.timeout.connect(self._drain_search); self._poll.start()
    @Property(str,notify=changed)
    def selectedSummary(self):
        return self._summary_service.summarize(self._selected) if self._selected else ''
    @Property(str,notify=changed)
    def selectedSummaryLabel(self):
        return 'RÉSUMÉ LOCAL' if self._summary_service.summarizer is not None else 'EXTRAIT DU MESSAGE'
    @Property(str,notify=changed)
    def mode(self): return self._mode
    @Property(bool,notify=changed)
    def readOnly(self): return self.permissionState != 'test'
    @Property(int,notify=changed)
    def unreadCount(self): return sum(bool(m.unread) for m in self.model.items)
    @Property(bool,notify=changed)
    def loading(self): return self._loading
    @Property(str,notify=changed)
    def state(self):
        if self._loading: return 'LOADING'
        if self.permissionState == 'permission_required': return 'PERMISSION_REQUIRED'
        if self._error:
            return {'PERMISSION_REQUIRED':'PERMISSION_REQUIRED','AUTH_UNAVAILABLE':'AUTH_ERROR'}.get(self._error, 'API_ERROR')
        return 'READY'
    @Property(str, notify=changed)
    def permissionState(self):
        name = self.service.backend.__class__.__name__
        return 'connected' if name == 'GmailMailBackend' else 'test' if name == 'FakeMailBackend' else 'permission_required'
    @Property(str,notify=changed)
    def error(self): return self._error
    @Property(str,notify=changed)
    def searchQuery(self): return self._query
    @Property('QVariantList',notify=changed)
    def messages(self): return [m.__dict__ for m in self.model.items]
    @Property('QVariantMap',notify=changed)
    def selectedMessage(self): return self._selected.__dict__ if self._selected else {}
    @Property('QVariantList',notify=changed)
    def threadMessages(self): return [m.__dict__ for m in (self._thread.messages if self._thread else ())]
    @Slot(str)
    def search(self, query):
        self._query=str(query or ''); self._loading=True; self._error=''; self._generation += 1; generation=self._generation; self.changed.emit()
        def work():
            try: rows=list(self.service.search(self._query)); error=''
            except Exception as exc: rows=[]; error=type(exc).__name__
            self._pending_search=(rows,error,generation)
            self._searchReady.emit(rows,error,generation)
        Thread(target=work, daemon=True, name='AuraMailLoad').start()
    def _drain_search(self):
        pending=self._pending_search
        if pending is not None:
            self._pending_search=None; self._apply_search(*pending)
    @Slot(object,str,int)
    def _apply_search(self, rows, error, generation):
        if generation != self._generation: return
        self.model.items=list(rows); self._error=error; self._loading=False; self.changed.emit()
    @Slot()
    def refresh(self): self.search(self._query)
    @Slot()
    def openInbox(self): self.search("")
    @Slot(str)
    def setMode(self, mode):
        self._mode = str(mode) if mode in ('inbox', 'search', 'draft', 'send', 'unread') else 'inbox'
        self.changed.emit()
        if self._mode in ('inbox', 'unread') and self.permissionState != 'permission_required': self.openInbox()
    @Slot(str, result=bool)
    def openInGmail(self, thread_id): return bool(QDesktopServices.openUrl(QUrl(gmail_url(thread_id))))
    @Slot(str)
    def selectMessage(self, message_id):
        self._selected=self.service.get_message(message_id); self._thread=self.service.get_thread(self._selected.thread_id) if self._selected else None; self.changed.emit()
    @Slot(str)
    def selectThread(self, thread_id): self._thread=self.service.get_thread(thread_id); self.changed.emit()
    @Slot(str,str,result='QVariantMap')
    def prepareSend(self, recipient, body):
        self._prepared={'kind':'mail.send','to':str(recipient),'body':str(body)}
        if self.repository:
            action=PreparedAction(str(uuid4()),'mail.send','mail.send',dict(self._prepared),f'Envoyer un mail à {recipient}',True)
            self.repository.create(action); self._prepared_id=action.action_id
        self.changed.emit(); return dict(self._prepared)
    @Slot(result=bool)
    def cancelPrepared(self):
        if self.repository and getattr(self,'_prepared_id',None): self.repository.cancel(self._prepared_id)
        self._prepared=None; self.changed.emit(); return True
    @Slot(result=bool)
    def confirmPrepared(self):
        if not self._prepared: return False
        if self.repository and getattr(self,'_prepared_id',None):
            action=self.repository.get(self._prepared_id); self.repository.confirm(action.action_id)
        self.service.execute_send(self._prepared)
        if self.repository and getattr(self,'_prepared_id',None): self.repository.mark_executed(self._prepared_id)
        self._prepared=None; self.changed.emit(); return True
