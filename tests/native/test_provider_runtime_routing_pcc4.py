from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from aura_native.agent.provider import GeminiRuntimeProvider, ProviderChunk, ProviderFailure, ProviderResponse
from aura_native.agent.runtime_provider import ProviderRoutingError, RuntimeProviderRouter
from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import Command
from aura_native.providers.credentials import FakeProviderCredentialStore, ProviderConfig
from aura_native.providers.repository import ProviderSettingsRepository
from aura_native.providers.service import ProviderSettingsService
from aura_native.storage.conversation_repository import ConversationRepository
from aura_native.storage.database import NativeDatabase

ROOT = Path(__file__).resolve().parents[2]
SECRET = "PCC4_SECRET_SENTINEL_DO_NOT_LEAK"


class FakeRuntimeProvider:
    supports_tools = False

    def __init__(self, provider_id, model, *, failure=None, entered=None, release=None, delay=0.0):
        self.name = provider_id
        self.model = model
        self.failure = failure
        self.entered = entered
        self.release = release
        self.delay = delay
        self.calls = []

    @property
    def available(self):
        return True

    def generate(self, messages):
        self.calls.append(tuple(messages))
        if self.failure:
            raise ProviderFailure(self.failure, "private sentinel " + SECRET)
        return ProviderResponse("A B", self.name, self.model)

    def generate_stream(self, messages, *, cancel_event=None):
        self.calls.append(tuple(messages))
        if self.failure:
            raise ProviderFailure(self.failure, "private sentinel " + SECRET)
        if self.entered:
            self.entered.set()
        for index, text in enumerate(("A", "B")):
            if self.release and index == 1:
                self.release.wait(2)
            if self.delay:
                time.sleep(self.delay)
            if cancel_event is not None and cancel_event.is_set():
                return
            yield ProviderChunk(text, self.name, self.model, index == 1)


class ProviderRuntimeRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aura-pcc4-")
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "settings.db"
        self.store = FakeProviderCredentialStore()
        self.configs = (
            ProviderConfig("openai", "OpenAI", "api"),
            ProviderConfig("anthropic", "Anthropic", "api"),
            ProviderConfig("gemini", "Google Gemini", "api"),
            ProviderConfig("ollama", "Ollama", "local", credential_required=False),
            ProviderConfig("custom_openai", "Custom", "custom", credential_required=False),
        )
        self.settings = ProviderSettingsService(self.store, self.configs, ProviderSettingsRepository(NativeDatabase(self.db_path)))
        self.router = RuntimeProviderRouter(
            self.settings,
            self.store,
            environment={},
            adapters={
                "ollama": lambda selection: FakeRuntimeProvider("ollama", selection.model),
                "gemini": lambda selection: FakeRuntimeProvider("gemini", selection.model),
            },
        )

    def test_active_ollama_resolves_selected_model(self):
        self.settings.set_active("ollama", "qwen3:8b")
        resolved = self.router.resolve_active_provider()
        self.assertEqual((resolved.provider_id, resolved.model), ("ollama", "qwen3:8b"))
        self.assertIsInstance(resolved.adapter, FakeRuntimeProvider)
        self.assertTrue(resolved.is_local)

    def test_active_gemini_resolves_configured_model(self):
        self.store.set_secret("gemini", SECRET)
        self.settings.set_active("gemini", "gemini-test-model")
        resolved = self.router.resolve_active_provider()
        self.assertEqual((resolved.provider_id, resolved.model), ("gemini", "gemini-test-model"))
        self.assertFalse(resolved.is_local)

    def test_no_provider_is_an_explicit_error(self):
        with self.assertRaises(ProviderRoutingError) as caught:
            self.router.resolve_active_provider()
        self.assertEqual(caught.exception.code, "provider_not_selected")

    def test_gemini_without_credential_is_refused(self):
        self.settings.set_active("gemini", "gemini-test-model")
        with self.assertRaises(ProviderRoutingError) as caught:
            self.router.resolve_active_provider()
        self.assertEqual(caught.exception.code, "provider_not_configured")

    def test_gemini_without_model_is_refused_before_adapter_creation(self):
        self.store.set_secret("gemini", SECRET)
        self.settings.set_active("gemini", "")
        with self.assertRaises(ProviderRoutingError) as caught:
            self.router.resolve_active_provider()
        self.assertEqual(caught.exception.code, "model_not_selected")
        self.assertIn("Gemini", caught.exception.message)

    def test_ollama_without_model_is_refused(self):
        self.settings.set_active("ollama", "")
        with self.assertRaises(ProviderRoutingError) as caught:
            self.router.resolve_active_provider()
        self.assertEqual(caught.exception.code, "model_not_selected")

    def test_unknown_provider_is_invalid_configuration(self):
        self.settings._configs["not-a-provider"] = ProviderConfig("not-a-provider", "Unknown", "api")
        self.settings.set_active("not-a-provider")
        with self.assertRaises(ProviderRoutingError) as caught:
            self.router.resolve_active_provider()
        self.assertEqual(caught.exception.code, "invalid_configuration")

    def test_dev_environment_overrides_are_temporary(self):
        self.settings.set_active("ollama", "persisted-model")
        router = RuntimeProviderRouter(self.settings, self.store, environment={
            "AURA_PROVIDER": "ollama",
            "AURA_MODEL": "dev-model",
            "AURA_OLLAMA_HOST": "http://127.0.0.1:11434",
        }, adapters={"ollama": lambda selection: FakeRuntimeProvider("ollama", selection.model)})
        resolved = router.resolve_active_provider()
        self.assertEqual(resolved.model, "dev-model")
        self.assertEqual(self.settings.get_provider_config("ollama").selected_model, "persisted-model")
        self.assertEqual(self.settings.get_active_model(), "persisted-model")

    def make_composed_runtime(self, adapters, *, provider=None):
        env_patch = patch.dict(os.environ, {"AURA_PCC_FAKE": "1"}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        runtime = compose_runtime(project_root=ROOT, state_dir=Path(self.temp.name) / "runtime", provider=provider)
        runtime.runtime_provider_router.adapters.update(adapters)
        runtime.start()
        def stop_fake_runtime():
            runtime.stop()
            # These tests inject only finite fake streams. Wait for their
            # completion callbacks before TemporaryDirectory removes SQLite.
            runtime.agent_service._executor.shutdown(wait=True, cancel_futures=True)
        self.addCleanup(stop_fake_runtime)
        return runtime

    @staticmethod
    def create_user_message(runtime, text):
        repository = ConversationRepository(NativeDatabase(runtime.paths.data_dir / "aura_native.db"))
        conversation = repository.create("native")
        message = repository.add_message(conversation.conversation_id, "native", "user", text, "test")
        return conversation, message

    def run_agent_until(self, runtime, events, *, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            runtime.bus.drain()
            if any(event.name in ("agent.error", "agent.completed") or event.payload.get("request", {}).get("state") in ("error", "completed", "cancelled", "unavailable") for event in events):
                return
            time.sleep(.005)
        self.fail("agent request did not finish before timeout")

    def submit(self, runtime, message, conversation, events):
        runtime.bus.subscribe(events.append, name="agent.state_changed")
        runtime.bus.subscribe(events.append, name="agent.error")
        runtime.bus.subscribe(events.append, name="agent.completed")
        runtime.bus.submit(Command(name="agent.submit", payload={
            "text": message.content,
            "conversation_id": conversation.conversation_id,
            "user_message_id": message.message_id,
        }, session_id="native", source="test"))
        runtime.bus.drain()

    def test_production_composition_shares_settings_router_and_agent(self):
        runtime = self.make_composed_runtime({})
        self.assertIs(runtime.agent_service.provider_router, runtime.runtime_provider_router)
        self.assertIs(runtime.runtime_provider_router.settings_service, runtime.provider_settings_service)
        self.assertIs(runtime.agent_service.provider_router.settings_service, runtime.provider_settings_service)

    def test_hot_switch_keeps_request_snapshot_and_routes_next_request(self):
        entered = threading.Event(); release = threading.Event()
        created = {}
        def ollama(selection):
            created["ollama"] = FakeRuntimeProvider("ollama", selection.model, entered=entered, release=release)
            return created["ollama"]
        def gemini(selection):
            self.assertEqual(selection.model, "gemini-test-model")
            created["gemini"] = FakeRuntimeProvider("gemini", selection.model)
            return created["gemini"]
        runtime = self.make_composed_runtime({"ollama": ollama, "gemini": gemini})
        runtime.provider_settings_service.set_active("ollama", "qwen3:8b")
        first_conversation, first_message = self.create_user_message(runtime, "first")
        first_events = []
        self.submit(runtime, first_message, first_conversation, first_events)
        self.assertTrue(entered.wait(1))
        runtime.provider_settings_service.set_active("gemini", "gemini-test-model")
        second_conversation, second_message = self.create_user_message(runtime, "second")
        second_events = []
        self.submit(runtime, second_message, second_conversation, second_events)
        release.set()
        self.run_agent_until(runtime, second_events)
        self.run_agent_until(runtime, first_events)
        requests = runtime.agent_service.repository
        first = requests.find_by_user_message("native", first_message.message_id)
        second = requests.find_by_user_message("native", second_message.message_id)
        self.assertEqual((first.provider, first.model), ("ollama", "qwen3:8b"))
        self.assertEqual((second.provider, second.model), ("gemini", "gemini-test-model"))
        self.assertEqual(len(created["ollama"].calls), 1)
        self.assertEqual(len(created["gemini"].calls), 1)

    def test_gemini_failure_never_falls_back_to_ollama(self):
        providers = {}
        def make(provider_id, selection, failure=None):
            providers[provider_id] = FakeRuntimeProvider(provider_id, selection.model, failure=failure)
            return providers[provider_id]
        runtime = self.make_composed_runtime({
            "gemini": lambda selection: make("gemini", selection, "network_error"),
            "ollama": lambda selection: make("ollama", selection),
        })
        runtime.provider_settings_service.set_active("gemini", "gemini-test-model")
        conversation, message = self.create_user_message(runtime, "will fail")
        events = []; self.submit(runtime, message, conversation, events)
        self.run_agent_until(runtime, events)
        request = runtime.agent_service.repository.find_by_user_message("native", message.message_id)
        self.assertEqual(request.error_code, "network_error")
        self.assertEqual(request.provider, "gemini")
        self.assertNotIn("ollama", providers)

    def test_ollama_and_gemini_fake_streams_share_agent_contract(self):
        created={}
        def adapter(provider_id, selection):
            created[provider_id]=FakeRuntimeProvider(provider_id,selection.model)
            return created[provider_id]
        runtime=self.make_composed_runtime({"ollama":lambda selection:adapter("ollama",selection),"gemini":lambda selection:adapter("gemini",selection)})
        for provider_id,model in (("ollama","qwen3:8b"),("gemini","gemini-test-model")):
            runtime.provider_settings_service.set_active(provider_id,model)
            conversation,message=self.create_user_message(runtime,"stream " + provider_id)
            deltas=[];completed=[]
            runtime.bus.subscribe(deltas.append,name="agent.delta");runtime.bus.subscribe(completed.append,name="agent.completed")
            events=[];self.submit(runtime,message,conversation,events);self.run_agent_until(runtime,events)
            self.assertEqual("".join(item.payload["text"] for item in deltas if item.payload["request_id"]==runtime.agent_service.repository.find_by_user_message("native",message.message_id).request_id),"AB")
            self.assertEqual(completed[-1].payload["message"]["content"],"AB")

    def test_ollama_failure_never_falls_back_to_gemini(self):
        providers = {}
        def make(provider_id, selection, failure=None):
            providers[provider_id] = FakeRuntimeProvider(provider_id, selection.model, failure=failure)
            return providers[provider_id]
        runtime = self.make_composed_runtime({
            "ollama": lambda selection: make("ollama", selection, "network_error"),
            "gemini": lambda selection: make("gemini", selection),
        })
        runtime.provider_settings_service.set_active("ollama", "qwen3:8b")
        conversation, message = self.create_user_message(runtime, "will fail")
        events = []; self.submit(runtime, message, conversation, events)
        self.run_agent_until(runtime, events)
        request = runtime.agent_service.repository.find_by_user_message("native", message.message_id)
        self.assertEqual(request.error_code, "network_error")
        self.assertEqual(request.provider, "ollama")
        self.assertNotIn("gemini", providers)

    def test_cancelled_gemini_stream_has_no_late_delta_or_assistant(self):
        entered = threading.Event(); release = threading.Event()
        runtime = self.make_composed_runtime({"gemini": lambda selection: FakeRuntimeProvider("gemini", selection.model, entered=entered, release=release)})
        runtime.provider_settings_service.set_active("gemini", "gemini-test-model")
        conversation, message = self.create_user_message(runtime, "cancel me")
        deltas = []; states = []
        runtime.bus.subscribe(deltas.append, name="agent.delta")
        runtime.bus.subscribe(states.append, name="agent.request_created")
        self.submit(runtime, message, conversation, [])
        self.assertTrue(entered.wait(1))
        request = runtime.agent_service.repository.find_by_user_message("native", message.message_id)
        runtime.bus.submit(Command(name="agent.cancel", payload={"request_id": request.request_id}, session_id="native", source="test")); runtime.bus.drain()
        release.set(); time.sleep(.05); runtime.bus.drain()
        stored = ConversationRepository(NativeDatabase(runtime.paths.data_dir / "aura_native.db")).messages(conversation.conversation_id, "native")
        self.assertEqual([item.role for item in stored], ["user"])
        self.assertEqual(len(deltas), 0)
        self.assertEqual(runtime.agent_service.repository.get(request.request_id, "native").state.value, "cancelled")

    def test_no_provider_returns_clear_error_without_assistant_message(self):
        runtime = self.make_composed_runtime({})
        class NoActiveProviderSettings:
            def get_active_provider(self): return ""
            def get_provider_config(self,_provider_id): return None
        runtime.runtime_provider_router.settings_service=NoActiveProviderSettings()
        conversation, message = self.create_user_message(runtime, "hello")
        runtime.bus.submit(Command(name="agent.submit", payload={"text":message.content,"conversation_id":conversation.conversation_id,"user_message_id":message.message_id},session_id="native",source="test"))
        runtime.bus.drain()
        stored = ConversationRepository(NativeDatabase(runtime.paths.data_dir / "aura_native.db")).messages(conversation.conversation_id,"native")
        request = runtime.agent_service.repository.find_by_user_message("native",message.message_id)
        self.assertEqual(request.error_code,"provider_not_selected")
        self.assertEqual(request.state.value,"unavailable")
        self.assertEqual(request.error_message,"Aucun fournisseur d’IA n’est sélectionné.")
        self.assertEqual([item.role for item in stored],["user"])

    def test_secret_sentinel_never_enters_events_or_sqlite(self):
        runtime = self.make_composed_runtime({"gemini": lambda selection: FakeRuntimeProvider("gemini", selection.model, failure="network_error")})
        store = runtime.runtime_provider_router.credential_store
        store.set_secret("gemini", SECRET)
        runtime.provider_settings_service.set_active("gemini", "gemini-test-model")
        events = []
        runtime.bus.subscribe(events.append)
        conversation, message = self.create_user_message(runtime, "safe prompt")
        agent_events = []; self.submit(runtime, message, conversation, agent_events); self.run_agent_until(runtime, agent_events)
        db = runtime.paths.data_dir / "aura_native.db"
        raw = db.read_bytes()
        self.assertNotIn(SECRET.encode(), raw)
        self.assertNotIn(SECRET, repr(events))
        self.assertNotIn(SECRET, repr(agent_events))
        self.assertNotIn(SECRET, repr(runtime.agent_service.conversations.messages(conversation.conversation_id,"native")))

    def test_provider_settings_restore_selected_provider_and_model(self):
        env_patch = patch.dict(os.environ, {"AURA_PCC_FAKE":"1"}, clear=False); env_patch.start(); self.addCleanup(env_patch.stop)
        state = Path(self.temp.name) / "persisted"
        first = compose_runtime(project_root=ROOT, state_dir=state); first.provider_settings_service.set_active("ollama","qwen3:8b"); first.stop()
        second = compose_runtime(project_root=ROOT, state_dir=state)
        self.assertEqual(second.provider_settings_service.get_active_provider(),"ollama")
        self.assertEqual(second.provider_settings_service.get_provider_config("ollama").selected_model,"qwen3:8b")

    def test_ollama_host_setting_is_persisted_and_used_by_router(self):
        self.settings.set_active("ollama","qwen3:8b")
        self.settings.set_provider_base_url("ollama","http://127.0.0.1:11434/")
        self.assertEqual(self.router.selection().host,"http://127.0.0.1:11434")
        restored=ProviderSettingsService(self.store,self.configs,ProviderSettingsRepository(NativeDatabase(self.db_path)))
        self.assertEqual(restored.get_provider_config("ollama").base_url,"http://127.0.0.1:11434")

    def test_gemini_rest_stream_normalizes_sse_and_redacts_sentinel(self):
        class Response:
            def __iter__(self):
                return iter((
                    b'data: {"candidates":[{"content":{"parts":[{"text":"A"}]}}]}\n',
                    b'data: {"candidates":[{"content":{"parts":[{"text":"B PCC4_SECRET_SENTINEL_DO_NOT_LEAK"}]},"finishReason":"STOP"}]}\n',
                ))
            def __enter__(self): return self
            def __exit__(self,*_): return False
        requests=[]
        provider=GeminiRuntimeProvider(model="gemini-test-model",api_key=SECRET,opener=lambda req,**kwargs:(requests.append((req,kwargs)) or Response()))
        chunks=list(provider.generate_stream(({"role":"system","content":"safe system"},{"role":"user","content":"hello"})))
        self.assertEqual([chunk.text for chunk in chunks],["A","B [redacted]",""])
        self.assertTrue(chunks[-1].done)
        self.assertIn("streamGenerateContent",requests[0][0].full_url)
        self.assertNotIn("key=",requests[0][0].full_url)
        self.assertEqual(requests[0][0].get_header("X-goog-api-key"), SECRET)
        self.assertNotIn(SECRET.encode(),requests[0][0].data)

    def test_gemini_auth_error_is_normalized_without_response_body(self):
        from urllib.error import HTTPError
        def fail(*_args,**_kwargs):
            raise HTTPError("https://generativelanguage.googleapis.com/",401,"unauthorized",{},None)
        provider=GeminiRuntimeProvider(model="gemini-test-model",api_key=SECRET,opener=fail)
        with self.assertRaises(ProviderFailure) as caught:
            list(provider.generate_stream(({"role":"user","content":"hello"},)))
        self.assertEqual(caught.exception.code,"authentication_failed")
        self.assertNotIn(SECRET,str(caught.exception))


if __name__ == "__main__":
    unittest.main()
