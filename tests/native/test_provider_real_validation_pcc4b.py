from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from aura_native.agent.pcc4_debug import pcc4_trace
from aura_native.agent.provider import ProviderChunk
from aura_native.bootstrap import composition
from aura_native.core.contracts import Command
from aura_native.providers.credentials import FakeProviderCredentialStore
from aura_native.storage.conversation_repository import ConversationRepository
from aura_native.storage.database import NativeDatabase


ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = ROOT / "tests/native/_evidence/pcc4_real_conversation_validation.py"
PROMPT_SENTINEL = "PCC4B_PRIVATE_PROMPT_SENTINEL"
SECRET_SENTINEL = "PCC4B_PRIVATE_SECRET_SENTINEL"


def load_harness():
    spec = importlib.util.spec_from_file_location("pcc4b_real_harness", HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrackingCredentialStore(FakeProviderCredentialStore):
    def __init__(self):
        super().__init__()
        self.secret_reads = []

    def get_secret(self, provider_id):
        self.secret_reads.append(provider_id)
        raise AssertionError("composition must not read a real provider secret")


class FixedStreamingProvider:
    name = "ollama"
    model = "qwen3:8b"
    available = True
    supports_tools = False

    def generate_stream(self, messages, *, cancel_event=None):
        yield ProviderChunk("safe ", self.name, self.model, False)
        yield ProviderChunk("answer", self.name, self.model, True)


class Pcc4bRealValidationPreparationTests(unittest.TestCase):
    def test_debug_trace_is_opt_in_and_content_free(self):
        output = io.StringIO()
        pcc4_trace(
            "PCC4_PROVIDER_RESOLVED",
            provider="gemini",
            model="gemini-test-model",
            request_id="request-1",
            environment={"AURA_PCC4_DEBUG": "1"},
            stream=output,
        )
        trace = output.getvalue()
        self.assertIn("PCC4_PROVIDER_RESOLVED", trace)
        self.assertIn("provider=gemini", trace)
        self.assertIn("model=gemini-test-model", trace)
        self.assertNotIn(PROMPT_SENTINEL, trace)
        self.assertNotIn(SECRET_SENTINEL, trace)
        detailed = io.StringIO()
        pcc4_trace("PCC4_ERROR", provider="gemini", model="gemini-test-model", request_id="request-1", error_code="provider_unavailable", http_status=503, stage="http_response", environment={"AURA_PCC4_DEBUG": "1"}, stream=detailed)
        self.assertIn("http_status=503", detailed.getvalue())
        self.assertIn("stage=http_response", detailed.getvalue())
        disabled = io.StringIO()
        pcc4_trace("PCC4_ERROR", error_code="network_error", environment={}, stream=disabled)
        self.assertEqual(disabled.getvalue(), "")

    def test_agent_debug_trace_has_metadata_without_prompt_or_answer(self):
        with tempfile.TemporaryDirectory(prefix="aura-pcc4b-debug-") as folder:
            stderr = io.StringIO()
            with patch.dict(os.environ, {"AURA_PCC4_DEBUG": "1"}, clear=False), contextlib.redirect_stderr(stderr):
                runtime = composition.compose_runtime(
                    project_root=ROOT,
                    state_dir=Path(folder),
                    provider=FixedStreamingProvider(),
                )
                runtime.start()
                repository = ConversationRepository(NativeDatabase(runtime.paths.data_dir / "aura_native.db"))
                conversation = repository.create("native")
                message = repository.add_message(conversation.conversation_id, "native", "user", PROMPT_SENTINEL, "test")
                terminal = []
                runtime.bus.subscribe(terminal.append, name="agent.completed")
                runtime.bus.submit(Command(
                    name="agent.submit",
                    payload={"text": message.content, "conversation_id": conversation.conversation_id, "user_message_id": message.message_id},
                    session_id="native",
                    source="test",
                ))
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not terminal:
                    runtime.bus.drain()
                    time.sleep(0.005)
                runtime.stop()
                runtime.agent_service._executor.shutdown(wait=True, cancel_futures=True)
            trace = stderr.getvalue()
            self.assertTrue(terminal)
            for event in ("PCC4_PROVIDER_RESOLVED", "PCC4_REQUEST_CREATED", "PCC4_STREAM_STARTED", "PCC4_FIRST_DELTA", "PCC4_COMPLETED"):
                self.assertIn(event, trace)
            self.assertIn("provider=ollama", trace)
            self.assertIn("model=qwen3:8b", trace)
            self.assertNotIn(PROMPT_SENTINEL, trace)
            self.assertNotIn("safe answer", trace)
            self.assertNotIn(SECRET_SENTINEL, trace)

    def test_production_composition_shares_one_settings_store_and_router_without_secret_read(self):
        store = TrackingCredentialStore()
        with tempfile.TemporaryDirectory(prefix="aura-pcc4b-") as folder, patch.object(
            composition, "KeyringProviderCredentialStore", return_value=store
        ), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AURA_PCC_FAKE", None)
            runtime = composition.compose_runtime(project_root=ROOT, state_dir=Path(folder) / "AURA-NATIVE")
            self.assertIs(runtime.provider_settings_service.store, store)
            self.assertIs(runtime.runtime_provider_router.credential_store, store)
            self.assertIs(runtime.agent_service.provider_router, runtime.runtime_provider_router)
            self.assertIs(runtime.runtime_provider_router.settings_service, runtime.provider_settings_service)
            self.assertEqual(store.secret_reads, [])
            runtime.stop()

    def test_harness_requires_explicit_provider_network_guard_and_state_dir(self):
        harness = load_harness()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            harness.parse_args(["--ollama", "--state-dir", "profile"])
        ollama = harness.parse_args(["--ollama", "--confirm-real-network", "--state-dir", "profile"])
        gemini = harness.parse_args(["--gemini", "--confirm-real-network", "--state-dir", "profile", "--cancel-after-first-delta"])
        self.assertTrue(ollama.ollama)
        self.assertTrue(gemini.gemini and gemini.cancel_after_first_delta)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            harness.parse_args(["--ollama", "--gemini", "--confirm-real-network", "--state-dir", "profile"])

    def test_harness_has_fixed_prompts_and_no_secret_arguments(self):
        harness = load_harness()
        source = HARNESS_PATH.read_text(encoding="utf-8")
        self.assertEqual(harness.PROMPTS["ollama"], "Réponds uniquement : AURA OLLAMA OK")
        self.assertEqual(harness.PROMPTS["gemini"], "Réponds uniquement : AURA GEMINI OK")
        for forbidden in ("--api-key", "--secret", "--token", "--prompt"):
            self.assertNotIn(forbidden, source)
        self.assertIn("external_paid_api_possible", source)
        self.assertNotIn("message.content)", source)
        self.assertNotIn("result.ok", source)
        self.assertIn("find_by_user_message", source)

    def test_all_public_conversation_errors_are_normalized(self):
        from aura_native.agent.service import AgentService

        expected = {
            "provider_not_configured", "model_not_selected", "authentication_failed",
            "permission_denied", "rate_limited", "network_error", "timeout",
            "provider_unavailable", "invalid_response", "cancelled", "unknown_error",
        }
        for code in expected:
            with self.subTest(code=code):
                self.assertTrue(AgentService._public_failure_message(code))


if __name__ == "__main__":
    unittest.main()
