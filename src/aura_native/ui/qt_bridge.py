import os
import queue
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QThread
from concurrent.futures import ThreadPoolExecutor
from aura_native.core.contracts import Command, Event
from aura_native.google.auth import GoogleAuthProvider, GoogleOAuthConfig
from aura_native.google.real_providers import GoogleCalendarProvider, GoogleTasksProvider
from aura_native.ui.models import LocalTasksModel, LocalRemindersModel, LocalNotesModel
from aura_native.diagnostics.service import DiagnosticsService
from aura_native.intents.router import NativeIntentRouter

class NativeDiagnosticsBridge(QObject):
    """Read-only, local diagnostics surface for the native QML view."""
    diagnosticsChanged = Signal()
    def __init__(self, parent=None, service=None):
        super().__init__(parent); self._service = service or DiagnosticsService(); self._data = {}
        self._set_safe_defaults()
    def _set_safe_defaults(self):
        self._data = {'cpu':0.0,'ram':0.0,'disk':0.0,'temp':0.0,'vram':0.0,
                      'cpuText':'Unavailable','ramText':'Unavailable','diskText':'Unavailable',
                      'tempText':'Unavailable','vramText':'Unavailable','downloadText':'Unavailable','uploadText':'Unavailable'}
    @Property(bool, notify=diagnosticsChanged)
    def diagReady(self): return bool(self._data.get('ready', False))
    @Property(float, notify=diagnosticsChanged)
    def diagCpuPercent(self): return float(self._data['cpu'])
    @Property(float, notify=diagnosticsChanged)
    def diagRamPercent(self): return float(self._data['ram'])
    @Property(float, notify=diagnosticsChanged)
    def diagDiskPercent(self): return float(self._data['disk'])
    @Property(float, notify=diagnosticsChanged)
    def diagTempPercent(self): return float(self._data['temp'])
    @Property(float, notify=diagnosticsChanged)
    def diagVramPercent(self): return float(self._data['vram'])
    @Property(str, notify=diagnosticsChanged)
    def diagCpuText(self): return self._data['cpuText']
    @Property(str, notify=diagnosticsChanged)
    def diagRamText(self): return self._data['ramText']
    @Property(str, notify=diagnosticsChanged)
    def diagDiskText(self): return self._data['diskText']
    @Property(str, notify=diagnosticsChanged)
    def diagTempText(self): return self._data['tempText']
    @Property(str, notify=diagnosticsChanged)
    def diagVramText(self): return self._data['vramText']
    @Property(str, notify=diagnosticsChanged)
    def diagDownloadText(self): return self._data['downloadText']
    @Property(str, notify=diagnosticsChanged)
    def diagUploadText(self): return self._data['uploadText']
    @Slot()
    def refreshDiagnostics(self):
        try:
            self._data.update(self._service.refresh())
        except Exception as exc:
            self._data['ready']=False
            self._data['cpuText']=self._data['ramText']=self._data['diskText']='ERROR'
            print(f'DIAG_REFRESH_ERROR type={type(exc).__name__}', flush=True)
        self.diagnosticsChanged.emit()

class NativeCoreBridge(QObject):
    localeChanged = Signal()

    @Property(str, notify=localeChanged)
    def locale(self):
        service = getattr(self._runtime, "locale_service", None)
        return service.locale if service is not None else "fr-FR"

    @Slot(str, result=bool)
    def setLocale(self, value):
        service = getattr(self._runtime, "locale_service", None)
        if service is None:
            return False
        before = service.locale
        accepted = service.set_locale(value)
        if accepted and before != service.locale:
            self.localeChanged.emit()
        return accepted

    connectedChanged = Signal()
    interactionReadyChanged = Signal()
    voiceStatusChanged = Signal()
    voiceAmplitudeChanged = Signal()
    availabilityChanged = Signal()
    memoriesChanged = Signal()
    memoryStatusChanged = Signal()
    messagesChanged = Signal()
    localCommandChanged = Signal()
    googleCalendarEventsChanged = Signal()
    googleTasksChanged = Signal()
    conversationStatusChanged = Signal()
    agentStateChanged = Signal()
    agentErrorChanged = Signal()
    providerAvailableChanged = Signal()
    agentStreamChanged = Signal()
    pendingActionChanged = Signal()
    providerConfigsChanged = Signal()
    activeProviderChanged = Signal()
    activeModelChanged = Signal()
    googleOAuthClientChanged = Signal()
    providerTestStarted = Signal(str)
    providerTestFinished = Signal(str, "QVariantMap")
    providerModelsRefreshStarted = Signal(str)
    providerModelsRefreshFinished = Signal(str, "QVariantList", "QVariantMap")
    providerModelSelectionChanged = Signal(str, str)
    intentRequested = Signal(str, "QVariantMap")
    voiceResponseFinal = Signal(str, str)
    voiceLocalActionTerminal = Signal(str, str)

    def __init__(self, runtime, parent=None, *, provider_test_timeout_seconds=14.0):
        super().__init__(parent)
        self._runtime = runtime
        self._ui_prepared_action_confirmer = getattr(runtime, "_ui_prepared_action_confirmer", None)
        self._closed = False
        self._intent_router = NativeIntentRouter()
        self._session = "native"
        self._availability = "not_migrated"
        self._memories = []
        self._memory_status = "ready"
        self._messages = []
        self._conversation_id = ""
        self._conversation_status = "ready"
        self._agent_state = "unavailable"
        self._agent_error = "provider_unavailable"
        self._agent_error_message = ""
        self._active_request_id = ""
        self._agent_provider = ""
        self._agent_model = ""
        self._provider_available = False
        self._agent_stream = ""
        self._voice_completed_ids = set()
        self._pending = None
        self._voice_action_by_id = {}
        self._reminder_notification_center = getattr(runtime, "reminder_notification_center", None)
        if self._reminder_notification_center is not None:
            self._reminder_notification_center.changed.connect(self.reminderNotificationChanged)
        self._prepared_repository = getattr(runtime, "prepared_action_repository", None)
        self._provider_settings = getattr(runtime, "provider_settings_service", None)
        self._oauth_client = getattr(runtime, "google_oauth_client_service", None)
        self._connection_tester = getattr(runtime, "provider_connection_tester", None)
        self._connection_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="aura-provider-test")
        self._model_catalog = getattr(runtime, "model_catalog_service", None)
        self._model_catalog_pending = set()
        self._provider_result_queue = queue.SimpleQueue()
        self._provider_result_timer = QTimer(self)
        self._provider_result_timer.setInterval(25)
        self._provider_result_timer.timeout.connect(self._drainProviderResultQueue)
        self._provider_result_timer.start()
        self._provider_test_timeout_seconds = max(0.05, float(provider_test_timeout_seconds))
        self._provider_test_generation = {}
        self._provider_test_pending = {}
        self._provider_test_deadlines = {}
        self._active_provider_test_futures = {}
        self._calendar_service = getattr(runtime, "calendar_service", None)
        self._tasks_service = getattr(runtime, "tasks_service", None)
        self._local_tasks_repository = getattr(runtime, "local_tasks_repository", None)
        self._local_tasks_service = getattr(runtime, "local_tasks_service", None)
        self.tasks_model = LocalTasksModel(self._local_tasks_repository.list() if self._local_tasks_repository else [], self)
        self._local_reminders_service = getattr(runtime, "local_reminders_service", None)
        self._local_reminders_repository = getattr(runtime, "local_reminders_repository", None)
        self.reminders_model = LocalRemindersModel(self._local_reminders_service.list() if self._local_reminders_service else [], self)
        self._local_notes_service = getattr(runtime, "local_notes_service", None)
        self._local_notes_repository = getattr(runtime, "local_notes_repository", None)
        self.notes_model = LocalNotesModel(self._local_notes_service.list() if self._local_notes_service else [], self)
        self._google_auth = getattr(runtime, "google_auth_provider", None)
        self._google_calendar_events = []
        self._google_tasks = []
        self._google_calendar_status = "not_connected"
        self._google_tasks_status = "not_connected"
        self._last_calendar_error_code = ""
        self._last_calendar_error_stage = ""
        self._calendar_request_id = 0
        self._tasks_request_id = 0
        self._read_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="aura-google-read")
        self._read_queue = queue.SimpleQueue()
        self._read_timer = QTimer(self); self._read_timer.setInterval(25); self._read_timer.timeout.connect(self._drain_read_queue); self._read_timer.start()
        self._pcc3_debug = os.environ.get("AURA_PCC3_DEBUG") == "1"
        self._bridge_thread_id = threading.get_ident()
        self._last_provider_worker_thread_id = None
        self._last_provider_drain_thread_id = None
        self._subscriptions = [
            runtime.bus.subscribe(self._on_command_result, name="command.result"),
            runtime.bus.subscribe(self._on_memory_list, name="memory.listed"),
            runtime.bus.subscribe(self._on_memory_list, name="memory.search_completed"),
            runtime.bus.subscribe(self._on_memory_created, name="memory.created"),
            runtime.bus.subscribe(self._on_memory_created, name="memory.updated"),
            runtime.bus.subscribe(self._on_memory_forgotten, name="memory.forgotten"),
            runtime.bus.subscribe(self._on_conversation_created, name="conversation.created"),
            runtime.bus.subscribe(self._on_message_created, name="conversation.message_created"),
            runtime.bus.subscribe(self._on_conversation_loaded, name="conversation.loaded"),
            runtime.bus.subscribe(self._on_conversation_cleared, name="conversation.cleared"),
            runtime.bus.subscribe(self._on_agent_state, name="agent.state_changed"),
            runtime.bus.subscribe(self._on_agent_state, name="agent.cancelled"),
            runtime.bus.subscribe(self._on_agent_state, name="agent.error"),
            runtime.bus.subscribe(self._on_agent_completed, name="agent.completed"),
            runtime.bus.subscribe(self._on_agent_delta, name="agent.delta"),
            runtime.bus.subscribe(self._on_pending_created, name="pending_action.created"),
            runtime.bus.subscribe(self._on_pending_state, name="pending_action.confirmed"),
            runtime.bus.subscribe(self._on_pending_state, name="pending_action.executed"),
            runtime.bus.subscribe(self._on_pending_state, name="pending_action.cancelled"),
            runtime.bus.subscribe(self._on_pending_state, name="pending_action.expired"),
            runtime.bus.subscribe(self._on_pending_error, name="pending_action.error"),
        ]
        self._restore_pending()

    def _restore_pending(self):
        if self._prepared_repository is not None:
            pending = self._prepared_repository.get_pending()
            if pending:
                action = pending[0]
                self._set_pending({"action_id": action.action_id, "tool_name": action.tool_name, "action_type": action.action_type, "state": action.state, "summary": action.summary, "error_code": action.error_code})

    def _set_pending(self, value):
        self._pending = value
        self.pendingActionChanged.emit()

    def _clear_pending(self):
        self._pending = None
        self.pendingActionChanged.emit()

    def _on_pending_created(self, event):
        if not self._closed: self._set_pending(event.payload)

    def _on_pending_state(self, event):
        if self._closed: return
        action_id = str(event.payload.get('action_id', ''))
        voice_id = self._voice_action_by_id.get(action_id, '')
        if voice_id and event.name in ('pending_action.executed', 'pending_action.cancelled', 'pending_action.expired'):
            self.voiceLocalActionTerminal.emit(voice_id, event.name.rsplit('.', 1)[-1])
            self._voice_action_by_id.pop(action_id, None)
        if str(event.payload.get('action_type','')).startswith(('local_notes.','local_tasks.','local_reminders.')) and event.name in ('pending_action.executed','pending_action.cancelled'):
            self._local_command_message='Action locale exécutée.' if event.name=='pending_action.executed' else 'Action locale annulée.'
            self.localCommandChanged.emit()
        if event.name == "pending_action.confirmed": self._set_pending(event.payload)
        else:
            if event.name == "pending_action.executed":
                print(f"PENDING_CONFIRM_RESULT success=true kind={str(event.payload.get('action_type', ''))}", flush=True)
                if str(event.payload.get('action_type', '')).startswith('local_tasks.') and self._local_tasks_repository:
                    self.tasks_model.replace_items(self._local_tasks_repository.list())
                elif str(event.payload.get('action_type', '')).startswith('local_reminders.') and self._local_reminders_repository:
                    self.reminders_model.replace_items(self._local_reminders_repository.list())
                elif str(event.payload.get('action_type', '')).startswith('local_notes.') and self._local_notes_repository:
                    self.notes_model.replace_items(self._local_notes_repository.list())
            self._clear_pending()

    def _on_pending_error(self, event):
        if not self._closed:
            action_id = str(event.payload.get('action_id', ''))
            voice_id = self._voice_action_by_id.get(action_id, '')
            if voice_id:
                self.voiceLocalActionTerminal.emit(voice_id, 'error')
                self._voice_action_by_id.pop(action_id, None)
            kind = str(event.payload.get("action_type", ""))
            reason = str(event.payload.get("error_code", "unknown"))
            print(f"PENDING_CONFIRM_RESULT success=false kind={kind}", flush=True)
            print(f"PENDING_CONFIRM_FAILURE reason={reason}", flush=True)
            if kind.startswith(('local_notes.','local_tasks.','local_reminders.')):
                self._local_command_message='Impossible d’exécuter cette action locale.'
                self.localCommandChanged.emit()
            self._set_pending(event.payload)

    @Property(bool, notify=connectedChanged)
    def connected(self):
        return self._runtime.state.value == "running" and not self._closed

    @Property(bool, notify=interactionReadyChanged)
    def interactionReady(self):
        return False

    @Property(str, notify=voiceStatusChanged)
    def voiceStatus(self):
        return "not_migrated"

    @Property(float, notify=voiceAmplitudeChanged)
    def voiceAmplitude(self):
        return 0.0

    @Property(str, notify=availabilityChanged)
    def availability(self):
        return self._availability

    @Property("QVariantList", notify=memoriesChanged)
    def memories(self):
        return list(self._memories)

    @Property(int, notify=memoriesChanged)
    def memoryCount(self):
        return len(self._memories)

    @Property(str, notify=memoryStatusChanged)
    def memoryStatus(self):
        return self._memory_status

    @Property(bool, constant=True)
    def memoryAvailable(self):
        return True

    @Property("QVariantList", notify=messagesChanged)
    def messages(self): return list(self._messages)

    @Property(int, notify=messagesChanged)
    def messageCount(self): return len(self._messages)

    @Property(str, notify=conversationStatusChanged)
    def conversationStatus(self): return self._conversation_status

    @Property(bool, constant=True)
    def conversationAvailable(self): return True

    @Property(str, notify=agentStateChanged)
    def agentState(self): return self._agent_state

    @Property(bool, constant=True)
    def agentAvailable(self): return True

    @Property(bool, notify=providerAvailableChanged)
    def providerAvailable(self): return self._provider_available

    @Property(str, notify=agentErrorChanged)
    def agentError(self): return self._agent_error
    @Property(str, notify=agentErrorChanged)
    def agentErrorMessage(self): return self._agent_error_message

    @Property(str, notify=agentStateChanged)
    def activeRequestId(self): return self._active_request_id
    @Property(str, notify=agentStateChanged)
    def agentProvider(self): return self._agent_provider
    @Property(str, notify=agentStateChanged)
    def agentModel(self): return self._agent_model

    @Property(bool, notify=agentStateChanged)
    def canCancel(self): return self._agent_state in ("queued", "thinking", "responding")

    @Property(str, notify=agentStreamChanged)
    def agentStream(self): return self._agent_stream

    @Property(bool, notify=pendingActionChanged)
    def hasPendingAction(self): return self._pending is not None
    @Property(str, notify=pendingActionChanged)
    def pendingActionId(self): return str((self._pending or {}).get("action_id", ""))
    @Property(str, notify=pendingActionChanged)
    def pendingActionSummary(self): return str((self._pending or {}).get("summary", ""))
    @Property(str, notify=pendingActionChanged)
    def pendingActionTool(self): return str((self._pending or {}).get("tool_name", ""))
    @Property(str, notify=pendingActionChanged)
    def pendingActionType(self): return str((self._pending or {}).get("action_type", ""))
    @Property(str, notify=pendingActionChanged)
    def pendingActionState(self): return str((self._pending or {}).get("state", ""))
    @Property(str, notify=pendingActionChanged)
    def pendingActionError(self): return str((self._pending or {}).get("error_code", ""))
    reminderNotificationChanged = Signal()
    @Property(bool, notify=reminderNotificationChanged)
    def reminderNotificationVisible(self): return bool(self._reminder_notification_center and self._reminder_notification_center.current)
    @Property(str, notify=reminderNotificationChanged)
    def reminderNotificationContent(self): return str((self._reminder_notification_center.current or {}).get("content", "")) if self._reminder_notification_center else ""
    @Property(str, notify=reminderNotificationChanged)
    def reminderNotificationTime(self): return str((self._reminder_notification_center.current or {}).get("trigger_at", "")) if self._reminder_notification_center else ""
    @Property(bool, notify=reminderNotificationChanged)
    def reminderNotificationMissed(self): return bool((self._reminder_notification_center.current or {}).get("is_missed", False)) if self._reminder_notification_center else False
    @Slot()
    def dismissReminderNotification(self):
        if self._reminder_notification_center: self._reminder_notification_center.dismiss()
    @Property("QVariantList", notify=providerConfigsChanged)
    def providerConfigs(self):
        if not self._provider_settings: return []
        return [{"provider_id":c.provider_id,"display_name":c.display_name,"configured":c.configured,"selected_model":c.selected_model,"base_url":c.base_url,"connection_status":c.connection_status} for c in self._provider_settings.list_provider_configs()]
    @Property(str, notify=activeProviderChanged)
    def activeProvider(self): return self._provider_settings.get_active_provider() if self._provider_settings else ''
    @Property(str, notify=activeModelChanged)
    def activeModel(self): return self._provider_settings.get_active_model() if self._provider_settings else ''
    # Safe native productivity surface used by AgendaView/TasksView. Reads are
    # empty until an explicit Google/local refresh is wired; never undefined.
    @Property(int, notify=messagesChanged)
    def googleTasksCount(self): return len(self._google_tasks)
    @Property(int, notify=messagesChanged)
    def taskCount(self): return self.tasks_model.rowCount()
    @Property("QVariantList", notify=googleTasksChanged)
    def googleTasks(self): return list(self._google_tasks)
    @Property("QVariantList", notify=googleCalendarEventsChanged)
    def googleCalendarEvents(self): return list(self._google_calendar_events)
    @Property(int, notify=messagesChanged)
    def googleCalendarCount(self): return len(self._google_calendar_events)
    @Property(bool, notify=messagesChanged)
    def googleSyncActive(self): return False
    @Property(str, notify=messagesChanged)
    def googleTasksStatus(self): return self._google_tasks_status
    @Property(str, notify=messagesChanged)
    def googleCalendarStatus(self): return self._google_calendar_status
    @Property(str, notify=messagesChanged)
    def googleWorkspaceStatus(self):
        if self._google_auth is None: return "not_connected"
        try: return "connected" if self._google_auth.get_state().authenticated else "not_connected"
        except Exception: return "not_connected"
    @Property(str, notify=messagesChanged)
    def lastGoogleCalendarErrorCode(self): return self._last_calendar_error_code
    @Property(str, notify=messagesChanged)
    def lastGoogleCalendarErrorStage(self): return self._last_calendar_error_stage
    @Property(bool, notify=messagesChanged)
    def googleConnecting(self): return False
    @Property(str, notify=messagesChanged)
    def googleConnectButtonLabel(self): return "CONNECTER GOOGLE"
    @Slot(result=bool)
    def startGoogleWorkspaceOAuth(self):
        if self._google_auth is None:
            return False
        self._google_calendar_status = "connecting"; self._google_tasks_status = "connecting"; self.messagesChanged.emit()
        try:
            state = self._google_auth.connect()
            if not self._rebind_google_providers():
                self._google_calendar_status = "error"; self._google_tasks_status = "error"; self.messagesChanged.emit(); return False
            self._google_calendar_status = "connected" if state.authenticated else "not_connected"
            self._google_tasks_status = self._google_calendar_status
            self.messagesChanged.emit()
            return bool(state.authenticated)
        except Exception:
            self._google_calendar_status = "error"; self._google_tasks_status = "error"; self.messagesChanged.emit(); return False
    @Property(str, notify=messagesChanged)
    def agendaMonthLabel(self): return ""
    @Slot()
    def refreshProductivity(self):
        self.refreshGoogleTasks()
        return None
    @Slot(str, str)
    def refreshGoogleCalendar(self, start="", end=""):
        print("B44_CALENDAR_BRIDGE_ENTER", flush=True)
        raw_start = str(start or "").strip()
        raw_end = str(end or "").strip()
        if not raw_start or not raw_end:
            print("B44_CALENDAR_REFRESH_DEFERRED reason=missing_range", flush=True)
            return None
        try:
            parsed_start = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            parsed_end = datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            print("B44_CALENDAR_REFRESH_DEFERRED reason=invalid_range", flush=True)
            return None
        if parsed_start.tzinfo is None or parsed_end.tzinfo is None or parsed_start >= parsed_end:
            print("B44_CALENDAR_REFRESH_DEFERRED reason=invalid_range", flush=True)
            return None
        if self._calendar_service is None:
            return None
        self._calendar_request_id += 1; request_id = self._calendar_request_id
        print(f"B44_CALENDAR_REQUEST_CREATED request_id={request_id} source=manual_calendar_refresh range_start={raw_start[:32]} range_end={raw_end[:32]}", flush=True)
        print(f"B44_CALENDAR_REFRESH_REQUESTED start={raw_start[:32]} end={raw_end[:32]}", flush=True)
        self._google_calendar_status = "loading"
        print("B44_CALENDAR_REQUEST_ACCEPTED", flush=True)
        self.messagesChanged.emit()
        provider = getattr(self._calendar_service, "provider", None)
        if provider is None or provider.__class__.__name__ == "FakeCalendarProvider":
            if self._google_calendar_status != "connected":
                self._google_calendar_status = "not_connected"
            self.messagesChanged.emit()
            return None
        self._read_executor.submit(self._read_calendar_worker, request_id, raw_start, raw_end)
        return None
    @Slot()
    def refreshGoogleTasks(self):
        if self._tasks_service is None:
            return None
        self._tasks_request_id += 1; request_id = self._tasks_request_id
        self._google_tasks_status = "loading"
        self.messagesChanged.emit()
        provider = getattr(self._tasks_service, "provider", None)
        if provider is None or provider.__class__.__name__ == "FakeTasksProvider":
            self._google_tasks_status = "not_connected"
            self.messagesChanged.emit()
            return None
        self._read_executor.submit(self._read_tasks_worker, request_id)
        return None

    @Slot(str, str, str, str, result=bool)
    def createGoogleEvent(self, title, start, end="", description=""):
        value = str(title or "").strip()
        raw_start, raw_end = str(start or "").strip(), str(end or "").strip()
        print(f"CALENDAR_UI_CREATE_ENTER title_present={str(bool(value)).lower()} datetime_present={str(bool(raw_start)).lower()}", flush=True)
        if self._closed or self._calendar_service is None or self.hasPendingAction or not value or not raw_start:
            return False
        try:
            start_dt = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=ZoneInfo("Europe/Paris"))
            end_dt = datetime.fromisoformat(raw_end.replace("Z", "+00:00")) if raw_end else start_dt + timedelta(minutes=60)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=start_dt.tzinfo)
            if end_dt <= start_dt:
                return False
            normalized_start = start_dt.isoformat(timespec="seconds")
            normalized_end = end_dt.isoformat(timespec="seconds")
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            return False
        action = self._calendar_service.prepare_create_event(
            title=value, start=normalized_start, end=normalized_end,
            timezone="Europe/Paris", description=str(description or "").strip(),
        )
        self._runtime.bus.publish(Event(
            name="pending_action.created",
            payload={"action_id": action.action_id, "tool_name": action.tool_name,
                     "action_type": action.action_type, "state": action.state,
                     "summary": action.summary, "error_code": action.error_code},
            session_id=self._session, source="qml",
        ))
        print("CALENDAR_UI_CREATE_PREPARED kind=calendar.create pending=true", flush=True)
        return True

    def _prepare_google_task_action(self, method, **payload):
        if self._closed or self._tasks_service is None or self.hasPendingAction:
            return False
        action = getattr(self._tasks_service, method)(**payload)
        self._runtime.bus.publish(Event(
            name="pending_action.created",
            payload={"action_id": action.action_id, "tool_name": action.tool_name,
                     "action_type": action.action_type, "state": action.state,
                     "summary": action.summary, "error_code": action.error_code},
            session_id=self._session, source="qml",
        ))
        return True

    @Slot(str, str, result=bool)
    def createGoogleTask(self, title, due=""):
        value = str(title or "").strip()
        return bool(value) and self._prepare_google_task_action("prepare_create_task", title=value, due=str(due or "").strip())

    @Slot(str, str, result=bool)
    def createReminder(self, content, trigger_at):
        print(f"LOCAL_REMINDER_CREATE_ENTER content_present={str(bool(str(content or '').strip())).lower()} trigger_present={str(bool(str(trigger_at or '').strip())).lower()}", flush=True)
        if self._closed or self._local_reminders_service is None:
            print("LOCAL_REMINDER_CREATE_RESULT success=false", flush=True); return False
        try: created = self._local_reminders_service.create(content, trigger_at)
        except ValueError:
            print("LOCAL_REMINDER_CREATE_RESULT success=false", flush=True); return False
        if not created:
            print("LOCAL_REMINDER_CREATE_RESULT success=false", flush=True); return False
        self.reminders_model.replace_items(self._local_reminders_repository.list())
        print(f"LOCAL_REMINDER_MODEL_REFRESH count={self.reminders_model.count}", flush=True)
        print("LOCAL_REMINDER_CREATE_RESULT success=true", flush=True)
        return True

    def _prepare_local_reminder_action(self, action):
        if self._closed or self._local_reminders_service is None or self.hasPendingAction or action is None:
            return False
        self._prepared_repository.create(action)
        self._runtime.bus.publish(Event(name='pending_action.created', payload={'action_id':action.action_id,'tool_name':action.tool_name,'action_type':action.action_type,'state':action.state,'summary':action.summary,'error_code':''}, session_id=self._session, source='qml'))
        return True

    @Slot(str, str, result=bool)
    def deleteReminder(self, reminder_id, content=''):
        action = self._local_reminders_service.prepare_delete(reminder_id, content) if self._local_reminders_service else None
        return self._prepare_local_reminder_action(action)

    @Slot(str, str, result=bool)
    def createNote(self, title, content):
        if self._closed or self._local_notes_service is None: return False
        try: created=self._local_notes_service.create(title, content)
        except ValueError: created=None
        if not created: print('LOCAL_NOTE_CREATE_RESULT success=false',flush=True); return False
        self.notes_model.replace_items(self._local_notes_repository.list()); print(f'LOCAL_NOTE_MODEL_REFRESH count={self.notes_model.count}',flush=True); print('LOCAL_NOTE_CREATE_RESULT success=true',flush=True); return True
    def _prepare_local_note_action(self, action):
        if self._closed or self._local_notes_service is None or self.hasPendingAction or action is None: return False
        self._prepared_repository.create(action); self._runtime.bus.publish(Event(name='pending_action.created',payload={'action_id':action.action_id,'tool_name':action.tool_name,'action_type':action.action_type,'state':action.state,'summary':action.summary,'error_code':''},session_id=self._session,source='qml')); return True
    @Slot(str, str, result=bool)
    def deleteNote(self, note_id, title=''):
        action=self._local_notes_service.prepare_delete(note_id,title) if self._local_notes_service else None
        return self._prepare_local_note_action(action)
    @Slot(str, str, str, result=bool)
    def updateNote(self, note_id, title, content):
        action=self._local_notes_service.prepare_update(note_id,title,content) if self._local_notes_service else None
        return self._prepare_local_note_action(action)

    @Slot(str, str, result=bool)
    def createTask(self, title, due=""):
        value = str(title or "").strip()
        raw_due = str(due or "").strip()
        print(f"LOCAL_TASK_CREATE_ENTER title_present={str(bool(value)).lower()} due_present={str(bool(raw_due)).lower()}", flush=True)
        if not value or self._local_tasks_service is None:
            print("LOCAL_TASK_CREATE_RESULT success=false", flush=True)
            return False
        try: result = self._local_tasks_service.create(value, raw_due)
        except ValueError:
            print("LOCAL_TASK_CREATE_RESULT success=false", flush=True); return False
        if not result:
            print("LOCAL_TASK_CREATE_RESULT success=false", flush=True); return False
        self.tasks_model.replace_items(self._local_tasks_repository.list())
        print("LOCAL_TASK_CREATE_RESULT success=true", flush=True)
        return True

    def _prepare_local_task_action(self, action):
        if self._closed or self._local_tasks_service is None or self.hasPendingAction or action is None: return False
        self._prepared_repository.create(action)
        self._runtime.bus.publish(Event(name='pending_action.created', payload={'action_id':action.action_id,'tool_name':action.tool_name,'action_type':action.action_type,'state':action.state,'summary':action.summary,'error_code':''}, session_id=self._session, source='qml'))
        return True

    @Slot(str, str, str, result=bool)
    def updateTask(self, task_id, title, due=""):
        return self._prepare_local_task_action(self._local_tasks_service.prepare_update(task_id, title, due) if self._local_tasks_service else None)

    @Slot(str, result=bool)
    def completeTask(self, task_id):
        title = next((x.get('title') for x in self._local_tasks_repository.list() if x.get('task_id') == str(task_id)), '') if self._local_tasks_repository else ''
        return self._prepare_local_task_action(self._local_tasks_service.prepare_complete(task_id, title) if self._local_tasks_service else None)

    @Slot(str, result=bool)
    def deleteTask(self, task_id):
        title = next((x.get('title') for x in self._local_tasks_repository.list() if x.get('task_id') == str(task_id)), '') if self._local_tasks_repository else ''
        return self._prepare_local_task_action(self._local_tasks_service.prepare_delete(task_id, title) if self._local_tasks_service else None)

    @Slot(str, str, str, bool, result=bool)
    def updateGoogleTask(self, task_id, title, due="", due_changed=False):
        identifier, value = str(task_id or "").strip(), str(title or "").strip()
        raw_due = str(due or "").strip()
        if not due_changed:
            payload = {"task_id": identifier, "title": value, "due_mode": "unchanged"}
        elif not raw_due:
            payload = {"task_id": identifier, "title": value, "due_mode": "clear"}
        else:
            try:
                parsed = datetime.fromisoformat(raw_due.replace("Z", "+00:00"))
                if parsed.tzinfo is None: raise ValueError("due must be timezone-aware")
                normalized = parsed.astimezone(ZoneInfo("UTC")).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            except (TypeError, ValueError):
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_due):
                    normalized = raw_due + "T00:00:00.000Z"
                else:
                    return False
            payload = {"task_id": identifier, "title": value, "due_mode": "value", "due": normalized}
        return bool(identifier and value) and self._prepare_google_task_action("prepare_update_task", **payload)

    @Slot(str, result=bool)
    def completeGoogleTask(self, task_id):
        identifier = str(task_id or "").strip()
        return bool(identifier) and self._prepare_google_task_action("prepare_complete_task", task_id=identifier)

    @Slot(str, str, result=bool)
    def deleteGoogleTask(self, task_id, task_title=""):
        identifier = str(task_id or "").strip()
        title = str(task_title or "").strip()
        payload = {"task_id": identifier}
        if title:
            payload["task_title"] = title
        return bool(identifier) and self._prepare_google_task_action("prepare_delete_task", **payload)

    def _read_calendar_worker(self, request_id, start, end):
        print(f"B44_CALENDAR_WORKER_START request_id={request_id}", flush=True)
        try:
            print("B44_CALENDAR_SERVICE_CALL", flush=True)
            events = self._calendar_service.list_events(start, end)
            print(f"B44_CALENDAR_PROVIDER_RESULT request_id={request_id} result_type={type(events).__name__} raw_count={len(events)}", flush=True)
            payload = []
            for e in events:
                raw = str(e.start or "")
                try:
                    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    local_key = parsed.astimezone(ZoneInfo("Europe/Paris")).date().isoformat() if parsed.tzinfo else raw[:10]
                except ValueError: local_key = raw[:10]
                payload.append({"id": e.event_id, "title": e.title, "start": raw, "end": e.end, "allDay": "T" not in raw, "timeLabel": (raw[11:16] if "T" in raw and len(raw) >= 16 else ""), "status": e.status, "dateKey": local_key})
            self._read_queue.put(("calendar", request_id, payload, None))
            print(f"B44_CALENDAR_NORMALIZED request_id={request_id} normalized_count={len(payload)}", flush=True)
        except ZoneInfoNotFoundError as exc:
            exc.code = "timezone_unavailable"
            print(f"B44_CALENDAR_READ_FAILED status=timezone_unavailable stage=timezone exception_type={type(exc).__name__}", flush=True)
            self._read_queue.put(("calendar", request_id, None, exc))
        except Exception as exc:
            print(f"B44_CALENDAR_READ_FAILED status={getattr(exc, 'code', 'error')} stage=provider exception_type={type(exc).__name__}", flush=True)
            self._read_queue.put(("calendar", request_id, None, exc))

    def _read_tasks_worker(self, request_id):
        try:
            tasks = self._tasks_service.list_tasks()
            payload = [{"id": t.task_id, "title": t.title, "due": t.due, "completed": t.status == "completed", "status": t.status} for t in tasks]
            self._read_queue.put(("tasks", request_id, payload, None))
        except Exception as exc: self._read_queue.put(("tasks", request_id, None, exc))

    def _drain_read_queue(self):
        while True:
            try: kind, request_id, payload, error = self._read_queue.get_nowait()
            except queue.Empty: return
            if kind == "calendar" and request_id == self._calendar_request_id:
                if error is None:
                    self._google_calendar_events = payload; self._google_calendar_status = "connected"; self.googleCalendarEventsChanged.emit()
                    print(f"B44_CALENDAR_PUBLISH request_id={request_id} published_count={len(payload)}", flush=True)
                    print(f"B44_CALENDAR_READ_SUCCESS request_id={request_id} source=manual_calendar_refresh count={len(payload)}", flush=True)
                else:
                    self._last_calendar_error_code = str(getattr(error, "code", "error"))
                    self._last_calendar_error_stage = "provider"
                    self._google_calendar_status = "not_connected" if self._last_calendar_error_code in ("google_auth_required", "google_auth_expired", "google_credentials_invalid") else "error"
                self.messagesChanged.emit()
            elif kind == "calendar":
                print(f"B44_CALENDAR_STALE_DROPPED request_id={request_id} latest_request_id={self._calendar_request_id}", flush=True)
            elif kind == "tasks" and request_id == self._tasks_request_id:
                if error is None: self._google_tasks = payload; self._google_tasks_status = "connected"; self.googleTasksChanged.emit()
                else: self._google_tasks_status = "not_connected" if getattr(error, "code", "") in ("google_auth_required", "google_auth_expired") else "error"
                self.messagesChanged.emit()
    @Slot()
    def agendaPreviousMonth(self): return None
    @Slot()
    def agendaNextMonth(self): return None
    @Slot()
    def agendaToday(self): return None
    @Slot(str, result=str)
    def getProviderSelectedModel(self, provider_id):
        if not self._provider_settings: return ""
        config = self._provider_settings.get_provider_config(str(provider_id))
        return str(getattr(config, "selected_model", "") or "") if config else ""
    @Slot(str, result="QVariantList")
    def getProviderModels(self, provider_id):
        if not self._model_catalog: return []
        return [descriptor.as_dict() for descriptor in self._model_catalog.get_models(str(provider_id))]
    @Slot(str)
    def refreshProviderModels(self, provider_id):
        provider_id = str(provider_id or "").strip().lower()
        if self._closed or not self._model_catalog or provider_id in self._model_catalog_pending: return False
        self._model_catalog_pending.add(provider_id); self.providerModelsRefreshStarted.emit(provider_id)
        future = self._connection_executor.submit(self._model_catalog.refresh_models, provider_id)
        future.add_done_callback(lambda done, pid=provider_id: self._model_catalog_done(pid, done))
        return True
    def _model_catalog_done(self, provider_id, future):
        try:
            models = [descriptor.as_dict() for descriptor in future.result()]
            payload = {"status": "success", "count": len(models), "last_refresh": self._model_catalog.get_last_refresh(provider_id)}
        except Exception as exc:
            models = self.getProviderModels(provider_id)
            payload = {"status": getattr(exc, "code", "unknown_error"), "count": len(models), "last_refresh": self._model_catalog.get_last_refresh(provider_id)}
        self._provider_result_queue.put(("model_catalog", provider_id, models, payload))
    @Slot(str, str)
    def selectProviderModel(self, provider_id, model_id):
        if not self._provider_settings: return False
        self._provider_settings.set_active_model(str(provider_id), str(model_id))
        self.providerModelSelectionChanged.emit(str(provider_id), str(model_id)); self.activeModelChanged.emit(); self.providerConfigsChanged.emit()
        return True
    @Property(bool, constant=True)
    def pcc3DebugEnabled(self): return self._pcc3_debug
    @Slot(str,str)
    def saveProviderSecret(self,provider_id,secret):
        if self._provider_settings: self._provider_settings.save_api_key(provider_id,secret); self.providerConfigsChanged.emit()
    @Slot(str)
    def removeProviderSecret(self,provider_id):
        if self._provider_settings: self._provider_settings.remove_api_key(provider_id); self.providerConfigsChanged.emit()
    @Slot(str)
    def setActiveProvider(self,provider_id):
        if self._provider_settings: self._provider_settings.set_active_provider(provider_id); self.activeProviderChanged.emit(); self.activeModelChanged.emit(); self.providerConfigsChanged.emit()
    @Slot(str,str)
    def setActiveModel(self,provider_id,model):
        if self._provider_settings: self._provider_settings.set_active_model(provider_id,model); self.activeModelChanged.emit(); self.providerConfigsChanged.emit()
    @Slot(str,str)
    def setProviderBaseUrl(self,provider_id,url):
        if self._provider_settings:
            try:
                self._provider_settings.set_provider_base_url(provider_id,url)
                self.providerConfigsChanged.emit()
            except Exception:
                return
    @Property("QVariantMap", notify=googleOAuthClientChanged)
    def googleOAuthClientStatus(self):
        return self._oauth_client.status() if self._oauth_client else {"configured": False, "source": "none", "filename": ""}
    @Slot(str, result=str)
    def importGoogleOAuthClient(self, path):
        if not self._oauth_client:
            return "unavailable"
        try:
            self._oauth_client.import_client(path, replace=bool(self._oauth_client.active_path.exists()))
            self.googleOAuthClientChanged.emit()
            return "ok"
        except Exception as exc:
            return getattr(exc, "code", "invalid_oauth_client")
    @Slot(str, result=str)
    def connectGoogle(self, path):
        """Agenda/Tasks connect action: import only when needed, then OAuth."""
        if not self.googleOAuthClientStatus.get("configured"):
            raw_path = str(path or "")
            if raw_path.startswith("file:///"): raw_path = raw_path[8:]
            result = self.importGoogleOAuthClient(raw_path)
            if result != "ok":
                return result
            if self._oauth_client:
                self._google_auth = GoogleAuthProvider(GoogleOAuthConfig(client_file=self._oauth_client.active_path), store=getattr(self._google_auth, "store", None))
        return "connected" if self.startGoogleWorkspaceOAuth() else "error"
    @Slot(str)
    def testProviderConnection(self, provider_id):
        if self._closed or not self._connection_tester or not self._provider_settings: return
        provider_id = str(provider_id or "").strip().lower()
        cfg=self._provider_settings.get_provider_config(provider_id)
        if not cfg: return
        if cfg.credential_required and not self._provider_settings.provider_configured(provider_id):
            self.providerTestFinished.emit(provider_id,{"provider_id":provider_id,"success":False,"status":"not_configured","message":"Configurez d'abord ce fournisseur."}); return
        request_id = self._provider_test_generation.get(provider_id, 0) + 1
        self._provider_test_generation[provider_id] = request_id
        self._provider_test_pending[provider_id] = request_id
        self._provider_test_deadlines[provider_id] = (request_id, time.monotonic() + self._provider_test_timeout_seconds)
        self._pcc3_trace("PCC3_REQUEST", provider_id, request_id=request_id)
        self.providerTestStarted.emit(provider_id)
        tester = self._resolve_provider_tester(provider_id)
        if tester is None:
            self._provider_result_queue.put((provider_id, request_id, self._provider_error_payload(provider_id, "provider_unavailable", "Fournisseur indisponible")))
            self._pcc3_trace("PCC3_QUEUE_ENQUEUE", provider_id, request_id=request_id, status="provider_unavailable")
            return
        try:
            self._pcc3_trace("PCC3_EXECUTOR_SUBMIT", provider_id, request_id=request_id)
            future = self._connection_executor.submit(
                self._run_provider_connection_test,
                tester,
                provider_id,
                request_id,
                {"selected_model":cfg.selected_model,"base_url":cfg.base_url},
            )
        except Exception:
            self._provider_result_queue.put((provider_id, request_id, self._provider_error_payload(provider_id)))
            self._pcc3_trace("PCC3_QUEUE_ENQUEUE", provider_id, request_id=request_id, status="unknown_error")
            return
        key = (provider_id, request_id)
        self._active_provider_test_futures[key] = future
        future.add_done_callback(lambda completed, p=provider_id, r=request_id: self._provider_future_done(p, r, completed))

    def _resolve_provider_tester(self, provider_id):
        registry = self._connection_tester
        if isinstance(registry, dict):
            return registry.get(provider_id)
        return registry if hasattr(registry, "test") else None

    @staticmethod
    def _provider_error_payload(provider_id, status="unknown_error", message="Échec de connexion"):
        return {
            "provider_id": provider_id,
            "success": False,
            "status": status,
            "message": message,
            "latency_ms": 0,
            "models_available_count": 0,
            "tested_model": "",
        }

    @classmethod
    def _provider_result_payload(cls, provider_id, result):
        return {
            "provider_id": str(getattr(result, "provider_id", provider_id) or provider_id),
            "success": bool(getattr(result, "success", False)),
            "status": str(getattr(result, "status", "unknown_error") or "unknown_error"),
            "message": str(getattr(result, "message", "Échec de connexion") or "Échec de connexion"),
            "latency_ms": int(getattr(result, "latency_ms", 0) or 0),
            "models_available_count": int(getattr(result, "models_available_count", 0) or 0),
            "tested_model": str(getattr(result, "tested_model", "") or ""),
        }

    def _run_provider_connection_test(self, tester, provider_id, request_id, config):
        self._last_provider_worker_thread_id = threading.get_ident()
        self._pcc3_trace("PCC3_WORKER_ENTER", provider_id, request_id=request_id)
        try:
            payload = self._provider_result_payload(provider_id, tester.test(provider_id, config))
        except Exception:
            payload = self._provider_error_payload(provider_id)
        self._pcc3_trace("PCC3_TESTER_RETURN", provider_id, request_id=request_id, status=payload["status"])
        return payload

    def _provider_future_done(self, provider_id, request_id, future):
        self._pcc3_trace("PCC3_FUTURE_CALLBACK", provider_id, request_id=request_id)
        try:
            payload = future.result()
        except Exception:
            payload = self._provider_error_payload(provider_id)
        self._provider_result_queue.put((provider_id, request_id, payload))
        self._pcc3_trace("PCC3_QUEUE_ENQUEUE", provider_id, request_id=request_id, status=payload["status"])

    @Slot()
    def _drainProviderResultQueue(self):
        self._last_provider_drain_thread_id = threading.get_ident()
        if QThread.currentThread() != self.thread():
            return
        while True:
            try:
                item = self._provider_result_queue.get_nowait()
            except queue.Empty:
                break
            if item[0] == "model_catalog":
                _, provider_id, models, metadata = item
                self._model_catalog_pending.discard(provider_id)
                if not self._closed: self.providerModelsRefreshFinished.emit(provider_id, models, metadata)
                continue
            provider_id, request_id, payload = item
            key = (provider_id, request_id)
            self._active_provider_test_futures.pop(key, None)
            self._pcc3_trace("PCC3_GUI_DRAIN", provider_id, request_id=request_id, status=payload["status"])
            if self._closed or self._provider_test_pending.get(provider_id) != request_id:
                self._pcc3_trace("PCC3_STALE_IGNORED", provider_id, request_id=request_id, status=payload["status"])
                continue
            self._provider_test_pending.pop(provider_id, None)
            self._provider_test_deadlines.pop(provider_id, None)
            self._emit_provider_test_finished(provider_id, request_id, payload)
        self._expire_provider_tests()

    def _expire_provider_tests(self):
        now = time.monotonic()
        expired = [
            (provider_id, request_id)
            for provider_id, (request_id, deadline) in tuple(self._provider_test_deadlines.items())
            if deadline <= now and self._provider_test_pending.get(provider_id) == request_id
        ]
        for provider_id, request_id in expired:
            self._provider_test_pending.pop(provider_id, None)
            self._provider_test_deadlines.pop(provider_id, None)
            self._emit_provider_test_finished(
                provider_id,
                request_id,
                self._provider_error_payload(provider_id, "timeout", "Le test de connexion a expiré"),
            )

    def _emit_provider_test_finished(self, provider_id, request_id, payload):
        self._pcc3_trace("PCC3_PUBLIC_FINISHED", provider_id, request_id=request_id, status=payload["status"])
        self.providerTestFinished.emit(provider_id, payload)

    def _pcc3_trace(self, marker, provider_id, *, request_id=None, status=None):
        if not self._pcc3_debug:
            return
        safe_provider = re.sub(r"[^a-z0-9_-]", "_", str(provider_id).lower())[:40]
        safe_status = re.sub(r"[^a-z0-9_-]", "_", str(status).lower())[:40] if status else ""
        parts = [marker, f"provider={safe_provider}"]
        if request_id is not None:
            parts.append(f"request_id={int(request_id)}")
        if safe_status:
            parts.append(f"status={safe_status}")
        parts.extend((f"current_thread_id={threading.get_ident()}", f"bridge_thread_id={self._bridge_thread_id}"))
        print(" ".join(parts), file=sys.stderr, flush=True)

    @Slot(str)
    def confirmPreparedAction(self, action_id):
        action_id = str(action_id or "").strip()
        pending = self._pending or {}
        kind = str(pending.get("action_type", ""))
        print(f"PREPARED_ACTION_UI_CONFIRM id_present={str(bool(action_id)).lower()} kind={kind}", flush=True)
        if self._closed or not pending or action_id != self.pendingActionId:
            print("PENDING_CONFIRM_REJECTED reason=no_pending_action", flush=True)
            return
        if self._ui_prepared_action_confirmer is None:
            return
        self._ui_prepared_action_confirmer.confirm(action_id, self._session)

    @Slot()
    def confirmPendingAction(self):
        if self.hasPendingAction: self.confirmPreparedAction(self.pendingActionId)

    @Slot(str)
    def cancelPreparedAction(self, action_id):
        action_id = str(action_id or "").strip()
        print(f"PREPARED_ACTION_UI_CANCEL id_present={str(bool(action_id)).lower()}", flush=True)
        if not self._closed and self.hasPendingAction and action_id == self.pendingActionId:
            self._runtime.bus.submit(Command(name="pending_action.cancel", payload={"action_id": action_id}, session_id=self._session, source="qml"))

    @Slot()
    def cancelPendingAction(self):
        if self.hasPendingAction: self.cancelPreparedAction(self.pendingActionId)

    def _set_memory_status(self, value):
        value = str(value)
        if value != self._memory_status:
            self._memory_status = value
            self.memoryStatusChanged.emit()

    @staticmethod
    def _plain_memory(value):
        if value is None:
            return None
        return {
            "memory_id": str(value.get("memory_id", "")),
            "content": str(value.get("content", "")),
            "memory_type": str(value.get("memory_type", "fact")),
            "scope": str(value.get("scope", "user")),
            "scope_id": str(value.get("scope_id", "default")),
            "importance": int(value.get("importance", 3)),
            "confidence": float(value.get("confidence", 1.0)),
            "source": str(value.get("source", "")),
            "is_sensitive": bool(value.get("is_sensitive", False)),
            "created_at": str(value.get("created_at", "")),
            "updated_at": str(value.get("updated_at", "")),
            "expires_at": value.get("expires_at"),
            "status": str(value.get("status", "active")),
        }

    def _on_command_result(self, event):
        if self._closed:
            return
        self._availability = str(event.payload.get("status", "not_migrated"))
        self.availabilityChanged.emit()
        # Reconcile persisted pending actions in case the creation event was
        # queued behind the command result while QML was already visible.
        if self._prepared_repository is not None and self._pending is None:
            pending = self._prepared_repository.get_pending()
            if pending:
                action = pending[0]
                self._set_pending({"action_id": action.action_id, "tool_name": action.tool_name, "action_type": action.action_type, "state": action.state, "summary": action.summary, "error_code": action.error_code})

    def _on_memory_list(self, event):
        if self._closed:
            return
        raw = event.payload.get("memories", ())
        self._memories = [self._plain_memory(item) for item in raw if item is not None]
        self._set_memory_status("ready")
        self.memoriesChanged.emit()

    def _on_memory_created(self, event):
        if self._closed:
            return
        record = self._plain_memory(event.payload.get("memory"))
        if record is None:
            return
        memory_id = record["memory_id"]
        replaced = False
        for index, item in enumerate(self._memories):
            if item.get("memory_id") == memory_id:
                self._memories[index] = record
                replaced = True
                break
        if not replaced:
            self._memories.insert(0, record)
        self._set_memory_status("saved")
        self.memoriesChanged.emit()

    def _on_memory_forgotten(self, event):
        if self._closed:
            return
        memory_id = str(event.payload.get("memory_id", ""))
        self._memories = [item for item in self._memories if item.get("memory_id") != memory_id]
        self._set_memory_status("forgotten")
        self.memoriesChanged.emit()

    def _set_conversation_status(self, value):
        value=str(value)
        if value != self._conversation_status:
            self._conversation_status=value; self.conversationStatusChanged.emit()

    @staticmethod
    def _plain_message(value):
        return {"message_id":str(value.get("message_id","")),"conversation_id":str(value.get("conversation_id","")),"role":str(value.get("role","user")),"content":str(value.get("content","")),"created_at":str(value.get("created_at","")),"sequence":int(value.get("sequence",0)),"status":str(value.get("status","active")),"source":str(value.get("source",""))}

    def _on_conversation_created(self,event):
        if self._closed:return
        value=event.payload.get("conversation") or {}; self._conversation_id=str(value.get("conversation_id",self._conversation_id)); self._set_conversation_status("ready")

    def _on_message_created(self,event):
        if self._closed:return
        message=self._plain_message(event.payload.get("message") or {}); self._conversation_id=message["conversation_id"] or self._conversation_id; self._messages.append(message); self._set_conversation_status("sent"); self.messagesChanged.emit()
        if message["role"] == "assistant" and self._agent_stream:
            self._agent_stream=""; self.agentStreamChanged.emit()

    def _on_conversation_loaded(self,event):
        if self._closed:return
        conversations=event.payload.get("conversations", ())
        if conversations:
            latest=conversations[0]
            self._conversation_id=str(latest.get("conversation_id", ""))
            self._runtime.bus.submit(Command(name="conversation.get",payload={"conversation_id":self._conversation_id},session_id=self._session,source="qml"))
            return
        record=event.payload.get("conversation") or {}; self._conversation_id=str(record.get("conversation_id",self._conversation_id)); self._messages=[self._plain_message(item) for item in event.payload.get("messages",())]; self._set_conversation_status("ready"); self.messagesChanged.emit()

    def _on_conversation_cleared(self,event):
        if self._closed:return
        if str(event.payload.get("conversation_id","")) == self._conversation_id:self._messages=[]; self.messagesChanged.emit()
        self._set_conversation_status("cleared")

    def _on_agent_state(self,event):
        if self._closed:return
        request=event.payload.get("request") or {}
        state=str(request.get("state",event.payload.get("state","unavailable")))
        error=str(request.get("error_code", ""))
        error_message=str(request.get("error_message", ""))
        request_id=str(request.get("request_id", ""))
        provider=str(request.get("provider", "")); model=str(request.get("model", ""))
        changed=state != self._agent_state or request_id != self._active_request_id or provider != self._agent_provider or model != self._agent_model
        self._agent_state=state; self._active_request_id=request_id
        self._agent_provider=provider; self._agent_model=model
        if error != self._agent_error or error_message != self._agent_error_message:
            self._agent_error=error; self._agent_error_message=error_message; self.agentErrorChanged.emit()
        available=bool(event.payload.get("provider_available",False))
        if available != self._provider_available: self._provider_available=available; self.providerAvailableChanged.emit()
        if changed:self.agentStateChanged.emit()
        if state == "completed":
            metadata = request.get("metadata") or {}
            voice_id = str(metadata.get("voice_request_id", ""))
            message = event.payload.get("message") or {}
            text = str(message.get("content", "")).strip()
            if voice_id and text and request_id not in self._voice_completed_ids:
                self._voice_completed_ids.add(request_id)
                if os.environ.get("AURA_PTT_DIAGNOSTICS") == "1":
                    print(f"VOICE_RESPONSE_FINAL_CORE voice_request_id={voice_id}", flush=True)
                    print(f"VOICE_RESPONSE_FINAL_SIGNAL voice_request_id={voice_id}", flush=True)
                self.voiceResponseFinal.emit(text, voice_id)

    def _on_agent_completed(self, event):
        if self._closed:
            return
        if os.environ.get("AURA_PTT_DIAGNOSTICS") == "1":
            print("VOICE_AGENT_COMPLETED_HANDLER_ENTER", flush=True)
        # The canonical completion payload is handled by the same state
        # mapper; this event is authoritative and arrives before the mirrored
        # agent.state_changed notification.
        self._on_agent_state(event)
        if state in ("cancelled","error","unavailable") and self._agent_stream:
            self._agent_stream=""; self.agentStreamChanged.emit()

    def _on_agent_delta(self,event):
        if self._closed:return
        # The service supplies the complete deterministic accumulator.  Keep a
        # fallback for older in-process producers while lots are migrated.
        if "accumulated" in event.payload:
            self._agent_stream=str(event.payload.get("accumulated") or "")
        else:
            self._agent_stream += str(event.payload.get("text", ""))
        self.agentStreamChanged.emit()

    @Property(str, notify=localCommandChanged)
    def localCommandMessage(self): return getattr(self,'_local_command_message','')

    def _dispatch_local_intent(self, intent):
        from aura_native.intents.local_product import LocalIntentProduct
        if intent.intent not in LocalIntentProduct.INTENTS: return False
        if self.hasPendingAction:
            self._set_conversation_status('local_pending_action_exists'); return True
        dispatcher = getattr(self._runtime,'local_intent_dispatcher',None)
        if dispatcher is None:
            self._set_conversation_status('local_unavailable'); return True
        result=dispatcher.dispatch(intent)
        self._local_command_message={
            'INVALID':'Commande incomplète : précisez le contenu et, pour un rappel, une date YYYY-MM-DDTHH:MM.',
            'NOT_FOUND':'Aucun élément local correspondant.',
            'AMBIGUOUS':'Plusieurs éléments correspondent. Précisez leur identifiant dans la vue locale.',
            'UNAVAILABLE':'Service local indisponible.',
            'FAILED':'La commande locale a échoué.',
            'PREPARED_ACTION_CREATED':'Confirmez ou annulez l’action ci-dessous.',
            'READ_ONLY_RESULT':f"{len(result.data.get('items',()))} élément(s) local(aux).",
        }.get(result.result_type,'')
        self.localCommandChanged.emit()
        print(f'LOCAL_INTENT_DISPATCH intent={intent.intent} result={result.result_type}',flush=True)
        self._set_conversation_status('local_'+result.result_type.lower())
        if result.result_type=='PREPARED_ACTION_CREATED':
            pending_data = dict(result.data)
            self._set_pending(pending_data)
            voice_id = str(getattr(intent, 'voice_request_id', '') or '')
            if voice_id:
                self._voice_action_by_id[str(pending_data.get('action_id', ''))] = voice_id
                pending_data['voice_request_id'] = voice_id
                self._set_pending(pending_data)
            self._runtime.bus.publish(Event(name='pending_action.created',payload=pending_data,session_id=self._session,source=intent.source))
        elif result.result_type=='READ_ONLY_RESULT':
            if result.route == 'memory':
                self._set_memory_status('ready')
            else:
                service=getattr(self._runtime,'local_'+result.route+'_service')
                getattr(self,{'notes':'notes_model','tasks':'tasks_model','reminders':'reminders_model'}[result.route]).replace_items(service.list())
            self.intentRequested.emit(intent.intent,dict(intent.slots))
        return True

    def _dispatch_productivity_read(self, intent):
        reads = {"MAIL_LIST", "MAIL_SEARCH", "MAIL_READ", "CALENDAR_LIST", "CALENDAR_FOR_DATE", "CALENDAR_SEARCH", "CONTACT_LIST", "CONTACT_SEARCH", "CONTACT_SHOW"}
        if intent.intent not in reads:
            return False
        try:
            if intent.intent.startswith("MAIL"):
                service = getattr(self._runtime, "mail_service", None)
                if service is None: raise RuntimeError("provider_unavailable")
                if intent.intent == "MAIL_LIST": rows = list(service.list_messages())
                elif intent.intent == "MAIL_SEARCH": rows = list(service.search(intent.slots.get("query", "")))
                else:
                    row = service.get_message(intent.slots.get("message_id", "")); rows = [] if row is None else [row]
                items = [{"subject":str(getattr(x,"subject","")),"sender":str(getattr(x,"sender","")),"date":str(getattr(x,"date","")),"snippet":str(getattr(x,"snippet",""))} for x in rows[:50]]
            elif intent.intent.startswith("CALENDAR"):
                service = getattr(self._runtime, "calendar_service", None)
                if service is None: raise RuntimeError("provider_unavailable")
                if intent.intent == "CALENDAR_LIST": rows=list(service.list_upcoming_events())
                elif intent.intent == "CALENDAR_SEARCH": rows=[x for x in service.list_upcoming_events() if str(intent.slots.get("query"," ")).casefold() in str(getattr(x,"title","")).casefold()]
                else:
                    day = datetime.now().date() + timedelta(days=1 if intent.slots.get("date")=="tomorrow" else 0); rows=list(service.get_events_for_date(day.isoformat()))
                items=[{"title":str(getattr(x,"title","")),"start":str(getattr(x,"start","")),"end":str(getattr(x,"end","")),"location":str(getattr(x,"location",""))} for x in rows[:50]]
            else:
                service=getattr(self._runtime,"contacts_service",None)
                if service is None: raise RuntimeError("provider_unavailable")
                if intent.intent == "CONTACT_LIST": rows=list(service.list_contacts())
                elif intent.intent == "CONTACT_SEARCH": rows=list(service.search_contacts(intent.slots.get("query","")))
                else: rows=[service.get_contact(intent.slots.get("contact_id",""))]
                items=[{"contact_id":str(getattr(x,"contact_id","")),"display_name":str(getattr(x,"display_name","")),"emails":list(getattr(x,"emails",())),"phones":list(getattr(x,"phones",()))} for x in rows[:50]]
            self._local_command_message=f"{len(items)} résultat(s)."; self.localCommandChanged.emit(); self.intentRequested.emit(intent.intent,{"items":items,**dict(intent.slots)}); self._set_conversation_status("intent_dispatched")
        except Exception as exc:
            self._local_command_message="Service indisponible." if "provider" in str(exc) else "Aucun résultat exploitable."; self.localCommandChanged.emit(); self._set_conversation_status("intent_unavailable")
        return True

    @Slot(str, result=bool)
    def sendMessage(self, text):
        if self._closed:
            return False
        value=str(text or "").strip()
        print("TEXT_SEND_BRIDGE_RECEIVED", flush=True)
        print(f"B43_CHAT_BRIDGE_ENTER length={len(value)}", flush=True)
        if not value:
            self._set_conversation_status("empty")
            return False
        intent = self._intent_router.parse(value, source="keyboard")
        if self._dispatch_local_intent(intent): return True
        if self._dispatch_productivity_read(intent): return True
        self._local_command_message=''; self.localCommandChanged.emit()
        if intent.intent in ("PC_MINIMIZE_WINDOW", "PC_MAXIMIZE_WINDOW", "PC_FOCUS_WINDOW"):
            product = getattr(self._runtime, "system_control_product", None)
            if product is None:
                self._set_conversation_status("intent_unavailable"); return False
            resolution, action = product.prepare(intent)
            if action is None:
                self._set_conversation_status("intent_" + str(resolution.status).lower())
                print(f"WINDOW_TARGET_RESOLUTION result={resolution.status} candidates={resolution.candidates}", flush=True)
                return False
            self._set_pending({"action_id":action.action_id,"tool_name":action.tool_name,"action_type":action.action_type,"state":action.state,"summary":action.summary,"error_code":""})
            self._runtime.bus.publish(Event(name="pending_action.created",payload={"action_id":action.action_id,"tool_name":action.tool_name,"action_type":action.action_type,"state":action.state,"summary":action.summary,"error_code":""},session_id=self._session,source="text_command"))
            print(f"TEXT_INTENT_DISPATCH result=PREPARED_ACTION_CREATED action_type={action.action_type}", flush=True)
            return True
        if intent.intent in ("PC_LIST_WINDOWS", "PC_LIST_PROCESSES", "PC_GET_FOREGROUND_WINDOW"):
            product = getattr(self._runtime, "system_control_product", None)
            if product is None:
                self._set_conversation_status("intent_unavailable"); return False
            result = product.read(intent)
            self._local_command_message = str(result.get("summary") or "Lecture système indisponible.")
            self.localCommandChanged.emit(); self.intentRequested.emit(intent.intent, dict(result))
            self._set_conversation_status("intent_dispatched")
            print(f"PC_READ_RESULT intent={intent.intent} status={result.get('status')} count={result.get('count',0)}", flush=True)
            return True
        if intent.deterministic:
            self.intentRequested.emit(intent.intent, dict(intent.slots))
            self._set_conversation_status("intent_dispatched")
            print(f"AURA_NATIVE_INTENT intent={intent.intent}", flush=True)
            return True
        self._set_conversation_status("sending")
        print("TEXT_SEND_COMMAND_CREATED", flush=True)
        self._runtime.bus.submit(
            Command(name="conversation.send", payload={"text": value, "conversation_id": self._conversation_id}, session_id=self._session, source="qml")
        )
        print("TEXT_SEND_COMMAND_ACCEPTED", flush=True)
        print("B43_CHAT_COMMAND_ACCEPTED", flush=True)
        return True

    @Slot(str, str, result=bool)
    def sendVoiceMessage(self, text, voice_request_id):
        if self._closed:
            return False
        value, ident = str(text or "").strip(), str(voice_request_id or "").strip()
        if not value or not ident:
            return False
        intent = self._intent_router.parse(value, source="voice")
        if self._dispatch_local_intent(intent): return True
        if self._dispatch_productivity_read(intent): return True
        if intent.intent in ("PC_MINIMIZE_WINDOW", "PC_MAXIMIZE_WINDOW", "PC_FOCUS_WINDOW"):
            product = getattr(self._runtime, "system_control_product", None)
            if product is None: return False
            resolution, action = product.prepare(intent)
            if action is None: return False
            self._set_pending({"action_id":action.action_id,"tool_name":action.tool_name,"action_type":action.action_type,"state":action.state,"summary":action.summary,"error_code":""})
            self._runtime.bus.publish(Event(name="pending_action.created",payload={"action_id":action.action_id,"tool_name":action.tool_name,"action_type":action.action_type,"state":action.state,"summary":action.summary,"error_code":""},session_id=self._session,source="voice"))
            return True
        if intent.intent in ("PC_LIST_WINDOWS", "PC_LIST_PROCESSES", "PC_GET_FOREGROUND_WINDOW"):
            product = getattr(self._runtime, "system_control_product", None)
            if product is None: return False
            result = product.read(intent)
            self._local_command_message = str(result.get("summary") or "Lecture système indisponible.")
            self.localCommandChanged.emit(); self.intentRequested.emit(intent.intent, dict(result)); return True
        if os.environ.get("AURA_PTT_DIAGNOSTICS") == "1":
            print(f"VOICE_REQUEST_CORE_RECEIVED voice_request_id={ident}", flush=True)
        self._set_conversation_status("sending")
        self._runtime.bus.submit(Command(name="conversation.send", payload={"text": value, "conversation_id": self._conversation_id, "metadata": {"voice_request_id": ident}}, session_id=self._session, source="voice"))
        if os.environ.get("AURA_PTT_DIAGNOSTICS") == "1":
            print(f"VOICE_REQUEST_COMMAND_CREATED voice_request_id={ident}", flush=True)
        print("B43_CHAT_COMMAND_ACCEPTED", flush=True)
        return True

    @Slot(str)
    def dispatchLocalTranscript(self, text):
        if not self._closed:
            self._dispatch_local_intent(self._intent_router.parse(text,source='voice'))

    @Slot(str, str)
    def dispatchLocalTranscriptWithRequest(self, text, voice_request_id):
        if not self._closed:
            from dataclasses import replace
            intent = self._intent_router.parse(text, source='voice')
            self._dispatch_local_intent(replace(intent, voice_request_id=str(voice_request_id or '')))

    def _rebind_google_providers(self):
        calendar_service = getattr(self._runtime, "calendar_service", None)
        tasks_service = getattr(self._runtime, "tasks_service", None)
        if self._google_auth is None or calendar_service is None or tasks_service is None:
            return False
        calendar = GoogleCalendarProvider(self._google_auth)
        tasks = GoogleTasksProvider(self._google_auth)
        calendar_service.set_provider(calendar); tasks_service.set_provider(tasks)
        self._runtime.google_calendar_provider = calendar; self._runtime.google_tasks_provider = tasks
        print("B44_GOOGLE_REBIND_DONE", flush=True)
        return True
    @Slot()
    def newConversation(self):
        if not self._closed:
            self._set_conversation_status("creating")
            self._runtime.bus.submit(Command(name="conversation.new",session_id=self._session,source="qml"))

    @Slot()
    def loadConversation(self):
        if not self._closed and self._conversation_id:
            self._set_conversation_status("loading")
            self._runtime.bus.submit(Command(name="conversation.get",payload={"conversation_id":self._conversation_id},session_id=self._session,source="qml"))

    @Slot(result=bool)
    def clearConversation(self):
        if self._closed or not self._conversation_id:return False
        self._runtime.bus.submit(Command(name="conversation.clear",payload={"conversation_id":self._conversation_id},session_id=self._session,source="qml")); return True

    @Slot(str, str, str, result=bool)
    def submitToAgent(self, text, conversation_id, user_message_id):
        value=str(text or "").strip()
        if self._closed or not value or not str(conversation_id or "").strip() or not str(user_message_id or "").strip(): return False
        self._runtime.bus.submit(Command(name="agent.submit",payload={"text":value,"conversation_id":str(conversation_id),"user_message_id":str(user_message_id)},session_id=self._session,source="qml")); return True

    @Slot(str, result=bool)
    def cancelAgent(self, request_id):
        value=str(request_id or "").strip()
        if self._closed or not value:return False
        self._runtime.bus.submit(Command(name="agent.cancel",payload={"request_id":value},session_id=self._session,source="qml")); return True

    @Slot()
    def refreshConversation(self):
        if self._closed:
            return
        self._set_conversation_status("loading")
        self._runtime.bus.submit(Command(name="conversation.list",payload={"limit":1},session_id=self._session,source="qml"))

    @Slot()
    def micStart(self):
        self._submit("voice.start")

    @Slot()
    def micStop(self):
        self._submit("voice.stop")

    @Slot()
    def stopSpeaking(self):
        self._submit("voice.stop_speaking")

    @Slot()
    def refreshMemories(self):
        if self._closed:
            return
        self._set_memory_status("loading")
        self._runtime.bus.submit(
            Command(name="memory.list", payload={"limit": 100}, session_id=self._session, source="qml")
        )

    @Slot(str)
    def searchMemories(self, query):
        if self._closed:
            return
        text = str(query or "").strip()
        self._set_memory_status("searching" if text else "loading")
        name = "memory.search" if text else "memory.list"
        payload = {"query": text, "limit": 100} if text else {"limit": 100}
        self._runtime.bus.submit(Command(name=name, payload=payload, session_id=self._session, source="qml"))

    @Slot(str, result=bool)
    def createMemory(self, content):
        if self._closed:
            return False
        text = str(content or "").strip()
        if not text:
            self._set_memory_status("empty")
            return False
        self._set_memory_status("saving")
        self._runtime.bus.submit(
            Command(
                name="memory.create",
                payload={
                    "content": text,
                    "memory_type": "note",
                    "scope": "user",
                    "scope_id": "default",
                    "source": "explicit_user",
                },
                session_id=self._session,
                source="qml",
            )
        )
        return True

    @Slot(str, result=bool)
    def forgetMemory(self, memory_id):
        if self._closed:
            return False
        value = str(memory_id or "").strip()
        if not value:
            return False
        self._set_memory_status("forgetting")
        self._runtime.bus.submit(
            Command(
                name="memory.forget",
                payload={"memory_id": value},
                session_id=self._session,
                source="qml",
            )
        )
        return True

    def _submit(self, name):
        if not self._closed:
            self._runtime.bus.submit(Command(name=name, session_id=self._session))

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._provider_result_timer.stop()
        self._provider_test_pending.clear()
        self._provider_test_deadlines.clear()
        self._connection_executor.shutdown(wait=False, cancel_futures=True)
        self._read_executor.shutdown(wait=False, cancel_futures=True)
        self._active_provider_test_futures.clear()
        self._model_catalog_pending.clear()
        for subscription in self._subscriptions:
            subscription.close()
        self._subscriptions = []
        self.connectedChanged.emit()
        self._runtime.bus.close()

class NativeUnavailableBridge(QObject):
    """Small inert facade for global QML references; it performs no I/O."""
    trackChanged = Signal()

    @Property(str, constant=True)
    def currentId(self):
        return ""

    @Slot()
    def refresh(self):
        pass
