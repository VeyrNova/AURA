from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from .summary import MailSummaryService
from .links import gmail_url, tasks_url

class DailyHubActions(QObject):
    summaryReady = Signal(str, str, int)
    def __init__(self, summary_service=None, parent=None, opener=None):
        super().__init__(parent); self.summary_service = summary_service or MailSummaryService(); self._generation = 0; self._opener = opener or QDesktopServices.openUrl
    @Slot(str, result=bool)
    def openGmail(self, thread_id): return bool(self._opener(QUrl(gmail_url(thread_id))))
    @Slot(result=bool)
    def openTasks(self): return bool(self._opener(QUrl(tasks_url())))
    def summarize(self, messages):
        self._generation += 1; generation = self._generation
        for message in messages:
            self.summary_service.summarize_async(message, self._completed, generation=generation)
        return generation
    def _completed(self, message, summary, generation, computed):
        if generation != self._generation: return
        self.summaryReady.emit(str(getattr(message, 'message_id', '')), str(summary), generation)
