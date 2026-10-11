import contextlib
from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import unittest

from aura_native.__main__ import main
from aura_native.bootstrap.composition import compose_runtime
from aura_native.config.settings import Settings
from aura_native.core.contracts import Command, CommandResult, Event, RuntimeState


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "tests/native/_evidence/unused-profile"


class BootstrapTests(unittest.TestCase):
    def runtime(self):
        return compose_runtime(project_root=ROOT, state_dir=STATE)

    def call_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = main(list(args), project_root=ROOT)
        return rc, json.loads(output.getvalue())

    def test_lifecycle(self):
        runtime = self.runtime()
        self.assertEqual(runtime.state, RuntimeState.CREATED)
        runtime.start()
        self.assertEqual(runtime.state, RuntimeState.RUNNING)
        runtime.stop()
        self.assertEqual(runtime.state, RuntimeState.STOPPED)
        self.assertEqual([state.value for state in runtime.transitions], ["created", "running", "stopped"])

    def test_repeated_start_and_stop_are_idempotent(self):
        runtime = self.runtime()
        for _ in range(3):
            runtime.start()
            runtime.start()
            self.assertEqual(runtime.state, RuntimeState.RUNNING)
            runtime.stop()
            runtime.stop()
            self.assertEqual(runtime.state, RuntimeState.STOPPED)

    def test_stop_before_start(self):
        runtime = self.runtime()
        runtime.stop()
        self.assertEqual(runtime.state, RuntimeState.STOPPED)

    def test_instances_do_not_share_state(self):
        first, second = self.runtime(), self.runtime()
        first.start()
        self.assertEqual(second.state, RuntimeState.CREATED)

    def test_available_native_capabilities_are_explicit(self):
        caps = self.runtime().capabilities
        self.assertEqual(
            [c.name for c in caps if c.state.value == "available"],
            ["foundation", "event_bus", "storage", "memory", "conversation", "agent", "weather", "tools"],
        )
        self.assertTrue(
            all(c.state.value == "not_migrated" for c in caps if c.name not in {"foundation", "event_bus", "storage", "memory", "conversation", "agent", "weather", "tools"})
        )
        self.assertTrue(all(c.reason for c in caps))
        self.assertEqual(len({c.name for c in caps}), len(caps))

    def test_settings_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            Settings().profile = "other"

    def test_invalid_settings_are_rejected(self):
        for kwargs in ({"profile": "legacy"}, {"schema_version": 2}, {"schema_version": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Settings(**kwargs)

    def test_settings_object_is_injected(self):
        settings = Settings()
        runtime = compose_runtime(project_root=ROOT, state_dir=STATE, settings=settings)
        self.assertIs(runtime.settings, settings)

    def test_contracts_have_version_and_correlation_fields(self):
        command = Command("cmd-1", "example")
        result = CommandResult(command.command_id, False, "not_implemented")
        event = Event("event-1", "example")
        self.assertEqual(result.command_id, command.command_id)
        self.assertEqual((command.schema_version, result.schema_version, event.schema_version), (1, 1, 1))

    def test_contract_payload_defaults_are_not_shared(self):
        first, second = Command("1", "example"), Command("2", "example")
        with self.assertRaises(TypeError):
            first.payload["value"] = 1
        self.assertEqual(second.payload, {})

    def test_selfcheck_reports_honest_scope(self):
        rc, body = self.call_cli("--self-check", "--state-dir", str(STATE))
        self.assertEqual(rc, 0)
        self.assertTrue(body["ok"])
        self.assertFalse(body["application_ready"])
        self.assertEqual(body["scope"], "minimal_foundation_only")
        self.assertEqual(body["lifecycle"], ["created", "running", "stopped"])
        self.assertTrue(any(m["name"] == "aura_native.core.runtime" for m in body["modules"]))

    def test_selfcheck_rejects_unsafe_state_path(self):
        rc, body = self.call_cli("--self-check", "--state-dir", str(ROOT / "app"))
        self.assertEqual(rc, 2)
        self.assertEqual(body["error"], "invalid_configuration")

    def test_missing_cli_arguments_fail(self):
        for args in ([], ["--self-check"], ["--state-dir", str(STATE)]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main(args, project_root=ROOT)
                self.assertEqual(raised.exception.code, 2)

    def test_unknown_cli_argument_fails(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--self-check", "--state-dir", str(STATE), "--launch-core"], project_root=ROOT)
        self.assertEqual(raised.exception.code, 2)

