"""Build the new runtime without importing the previous application."""

from pathlib import Path
import os
import importlib.util
from dataclasses import replace

from aura_native.config.paths import RuntimePaths
from aura_native.config.settings import Settings
from aura_native.config.locale_service import LocaleService
from aura_native.core.runtime import NativeRuntime
from aura_native.core.bus import LocalBus
from aura_native.memory.service import MemoryService
from aura_native.conversation.service import ConversationService
from aura_native.agent.service import AgentService
from aura_native.agent.runtime_provider import RuntimeProviderRouter
from aura_native.weather.provider import OpenMeteoProvider
from aura_native.weather.service import WeatherService
from aura_native.diagnostics.service import DiagnosticsService
from aura_native.tools.registry import ToolDefinition, ToolRegistry, register_google_offline_tools
from aura_native.tools.router import ToolRouter
from aura_native.tools.weather_tool import WeatherTool
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
from aura_native.storage.local_tasks_repository import LocalTasksRepository
from aura_native.tasks.local_tasks_service import LocalTasksService
from aura_native.storage.local_reminders_repository import LocalRemindersRepository
from aura_native.reminders.local_reminders_service import LocalRemindersService
from aura_native.storage.local_notes_repository import LocalNotesRepository
from aura_native.notes.local_notes_service import LocalNotesService
from aura_native.reminders.reminder_scheduler import ReminderScheduler, QtReminderSchedulerAdapter
from aura_native.google.providers import FakeCalendarProvider, FakeTasksProvider
from aura_native.google.auth import GoogleAuthProvider, GoogleOAuthConfig
from aura_native.google.oauth_client_config import GoogleOAuthClientConfigService
from aura_native.google.real_providers import GoogleCalendarProvider, GoogleTasksProvider
from aura_native.google.calendar_service import CalendarService
from aura_native.google.tasks_service import TasksService
from aura_native.google.pending_actions import PendingActionOrchestrator
from aura_native.providers.credentials import KeyringProviderCredentialStore, FakeProviderCredentialStore,ProviderConfig
from aura_native.providers.service import ProviderSettingsService
from aura_native.providers.repository import ProviderSettingsRepository
from aura_native.providers.connection import FakeProviderConnectionTester, build_connection_testers
from aura_native.providers.model_catalog import ModelCatalogService, FakeModelCatalogProvider, OllamaModelCatalogProvider, GeminiModelCatalogProvider
from aura_native.developer_fabric.adf import ADFService
from aura_native.google.day_summary import GoogleDaySummaryService
from aura_native.system_control.service import SystemControlService
from aura_native.system_control.product import SystemControlProductService


def compose_runtime(*, project_root: Path, state_dir: str | Path, settings: Settings | None = None, provider=None) -> NativeRuntime:
    # Qt reminder presentation is a runtime concern; keep module import safe
    # for the stdlib-only isolated core validator.
    from aura_native.reminders.notification_center import InternalReminderNotificationCenter
    from aura_native.reminders.notification_coordinator import NotificationCoordinator
    from aura_native.reminders.window_state import WindowStateAdapter
    from aura_native.reminders.windows_notifier import QtWindowsReminderNotifier
    from aura_native.mail.service import MailService, FakeMailBackend, PermissionRequiredMailBackend
    from aura_native.mail.gmail_adapter import GmailMailBackend, GMAIL_READ_SCOPE
    from aura_native.maps.service import MapsService
    paths = RuntimePaths.resolve(state_dir, project_root=project_root)
    memory = MemoryService(paths.data_dir / "aura_native.db")
    conversation = ConversationService(paths.data_dir / "aura_native.db")
    weather = WeatherService(OpenMeteoProvider())
    diagnostics = DiagnosticsService()
    registry = ToolRegistry()
    weather_tool = WeatherTool(weather)
    registry.register(ToolDefinition(weather_tool.name, "Get authoritative weather for an explicit city.", {"location":"string", "date":"ISO date optional"}, "weather", weather_tool))
    prepared=PreparedActionRepository(NativeDatabase(paths.data_dir / "aura_native.db"))
    system_control = SystemControlService()
    system_product = SystemControlProductService(system_control, prepared)
    local_tasks = LocalTasksRepository(NativeDatabase(paths.data_dir / "aura_native.db"))
    local_reminders = LocalRemindersRepository(NativeDatabase(paths.data_dir / "aura_native.db"))
    local_notes = LocalNotesRepository(NativeDatabase(paths.data_dir / "aura_native.db"))
    credential_store = FakeProviderCredentialStore() if os.environ.get("AURA_PCC_FAKE") == "1" else KeyringProviderCredentialStore()
    provider_settings=ProviderSettingsService(credential_store,(
        ProviderConfig('openai','OpenAI','api'),ProviderConfig('anthropic','Anthropic','api'),ProviderConfig('gemini','Google Gemini','api'),ProviderConfig('ollama','Ollama','local',credential_required=False),ProviderConfig('custom_openai','Custom OpenAI-compatible','custom',credential_required=False),
    ),ProviderSettingsRepository(NativeDatabase(paths.data_dir / "aura_native.db")))
    if os.environ.get("AURA_PCC_FAKE") == "1":
        # Deterministic visual-validation fixture. Secrets remain memory-only.
        provider_settings.save_api_key("openai", "fake-openai-secret")
        provider_settings.save_api_key("gemini", "fake-gemini-secret")
        provider_settings._configs["openai"] = replace(provider_settings._configs["openai"], selected_model="gpt-test-model")
        provider_settings._configs["gemini"] = replace(provider_settings._configs["gemini"], selected_model="gemini-test-model")
        if os.environ.get("AURA_PCC5_STALE_MODEL") == "1":
            provider_settings._configs["gemini"] = replace(provider_settings._configs["gemini"], selected_model="gemini-old-model")
        provider_settings._configs["ollama"] = replace(provider_settings._configs["ollama"], configured=True, selected_model="qwen3:8b", base_url="http://127.0.0.1:11434", connection_status="local")
        provider_settings.set_active("ollama", "qwen3:8b")
    runtime_provider_router = RuntimeProviderRouter(provider_settings, credential_store)
    calendar_provider, tasks_provider = FakeCalendarProvider(), FakeTasksProvider()
    # Developer override wins; otherwise resolve only files owned by this
    # runtime state directory. No external installation is discovered.
    oauth_root = paths.config_dir / "credentials"
    oauth_candidates = (oauth_root / "google_aura_desktop.json", oauth_root / "google_oauth_client.json", paths.config_dir / "google_aura_desktop.json")
    client_file = os.environ.get("AURA_GOOGLE_OAUTH_CLIENT_FILE", "").strip()
    if not client_file:
        client_file = next((str(candidate) for candidate in oauth_candidates if candidate.is_file()), "")
    if client_file:
        try:
            auth = GoogleAuthProvider(GoogleOAuthConfig(client_file=Path(client_file)))
            if auth.get_state().authenticated:
                calendar_provider, tasks_provider = GoogleCalendarProvider(auth), GoogleTasksProvider(auth)
        except Exception:
            # Offline and unconfigured startup must remain deterministic.
            pass
    calendar=CalendarService(calendar_provider,prepared); tasks=TasksService(tasks_provider,prepared)
    register_google_offline_tools(registry,calendar,tasks)
    local_service = LocalTasksService(local_tasks)
    runtime_bus = LocalBus()
    notification_center = InternalReminderNotificationCenter(runtime_bus)
    window_state = WindowStateAdapter()
    qt_runtime = importlib.util.find_spec("PySide6") is not None
    scheduler = QtReminderSchedulerAdapter(local_reminders, bus=None, notifier=None) if qt_runtime else ReminderScheduler(local_reminders, bus=None, notifier=None)
    local_reminders_service = LocalRemindersService(local_reminders, scheduler)
    local_notes_service = LocalNotesService(local_notes)
    from aura_native.contacts.repository import ContactsRepository
    from aura_native.contacts.service import ContactsService
    from aura_native.contacts.product import ContactsProductService
    contacts_service = ContactsService(ContactsRepository(paths.data_dir / 'contacts.sqlite'))
    contacts_product = ContactsProductService(contacts_service, prepared)
    pending=PendingActionOrchestrator(prepared,calendar,tasks,local_service,local_reminders_service,local_notes_service,system_product,memory,contacts_product)
    agent = AgentService(paths.data_dir / "aura_native.db", provider=provider, provider_router=None if provider is not None else runtime_provider_router, memory_repository=memory.repository, tool_router=ToolRouter(registry), tool_registry=registry, prepared_action_repository=prepared)
    developer_fabric_service = ADFService(project_root, paths.data_dir / 'adf_state')
    runtime = NativeRuntime(
        settings if settings is not None else Settings(),
        paths,
        runtime_bus,
        bus_binders=(memory.bind, conversation.bind, agent.bind, pending.bind),
        service_stoppers=(agent.stop, scheduler.stop, notification_center.close, developer_fabric_service.close),
        available_capabilities=("event_bus", "storage", "memory", "conversation", "agent", "weather", "tools"),
    )
    runtime.prepared_action_repository = prepared
    runtime._ui_prepared_action_confirmer = pending.create_ui_confirmation_port()
    runtime.system_control_service = system_control
    runtime.system_control_product = system_product
    runtime.calendar_service = calendar
    runtime.tasks_service = tasks
    runtime.weather_service = weather
    runtime.diagnostics_service = diagnostics
    runtime.local_tasks_repository = local_tasks
    runtime.local_tasks_service = local_service
    runtime.local_reminders_repository = local_reminders
    runtime.local_reminders_service = local_reminders_service
    runtime.local_notes_repository = local_notes
    runtime.local_notes_service = local_notes_service
    runtime.contacts_service = contacts_service
    from aura_native.intents.local_product import LocalIntentProduct
    from aura_native.intents.dispatcher import NativeActionDispatcher
    runtime.contacts_product = contacts_product
    runtime.local_intent_dispatcher = NativeActionDispatcher(local_product=LocalIntentProduct(prepared,local_notes_service,local_service,local_reminders_service,memory,contacts_product))
    scheduler.bus = runtime.bus
    scheduler.notifier = NotificationCoordinator(notification_center, window_state, QtWindowsReminderNotifier(project_root / 'app' / 'assets' / 'AURA_LOGO_SYMBOL_ARCTIC.svg')) if qt_runtime else None
    runtime.reminder_scheduler = scheduler
    runtime.reminder_notification_center = notification_center
    runtime.reminder_window_state = window_state
    runtime.reminder_notification_coordinator = scheduler.notifier
    runtime.google_auth_provider = auth if 'auth' in locals() else None
    runtime.google_calendar_provider = calendar_provider
    runtime.google_tasks_provider = tasks_provider
    runtime.provider_settings_service = provider_settings
    mail_backend = FakeMailBackend() if os.environ.get('AURA_PCC_FAKE') == '1' else PermissionRequiredMailBackend()
    if 'auth' in locals() and auth is not None:
        try:
            state = auth.get_state()
            if state.authenticated and GMAIL_READ_SCOPE in state.scopes:
                mail_backend = GmailMailBackend(auth)
        except Exception:
            mail_backend = PermissionRequiredMailBackend()
    runtime.mail_service = MailService(mail_backend)
    runtime.google_day_summary_service = GoogleDaySummaryService(calendar, tasks, runtime.mail_service)
    from aura_native.maps.routing import OSRMRoutingBackend, RoutingService
    runtime.maps_service = MapsService(weather, project_root / 'app' / 'assets' / 'maps', RoutingService(OSRMRoutingBackend()))
    runtime.locale_service = LocaleService(paths.config_dir)
    # Catalog creation is side-effect free; providers are queried only by an
    # explicit refresh request. Production startup never performs a fetch.
    if os.environ.get("AURA_PCC_FAKE") != "1":
        # Do not load the provider-settings database during boot. The catalog
        # provider uses the explicit environment host/default until refresh.
        ollama_cfg = provider_settings._configs.get("ollama")
        ollama_host = getattr(ollama_cfg, "base_url", "") or os.environ.get("AURA_OLLAMA_HOST", "http://127.0.0.1:11434")
        catalog_providers = {"ollama": OllamaModelCatalogProvider(ollama_host), "gemini": GeminiModelCatalogProvider(credential_store)}
        catalog_providers.update({pid: FakeModelCatalogProvider() for pid in ("openai", "anthropic", "custom_openai")})
    else:
        catalog_provider = FakeModelCatalogProvider()
        if os.environ.get("AURA_PCC5_LARGE_CATALOG") == "1": catalog_provider.catalogs["gemini"] = tuple(f"gemini-test-{index:03d}" for index in range(1, 61))
        catalog_providers = {pid: FakeModelCatalogProvider() for pid in ("openai", "anthropic", "gemini", "ollama", "custom_openai")}
        catalog_providers["gemini"] = catalog_provider
    if os.environ.get("AURA_PCC5_ERROR") == "1":
        catalog_providers["gemini"] = FakeModelCatalogProvider(error="network_error")
    runtime.model_catalog_service = ModelCatalogService(catalog_providers)
    runtime.runtime_provider_router = runtime_provider_router
    runtime.agent_service = agent
    runtime.memory_service = memory
    runtime.developer_fabric_service = developer_fabric_service
    runtime.provider_connection_tester = FakeProviderConnectionTester() if os.environ.get("AURA_PCC_FAKE") == "1" else build_connection_testers(credential_store)
    runtime.google_oauth_client_service = GoogleOAuthClientConfigService(user_root=oauth_root)
    return runtime
