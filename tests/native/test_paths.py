import os
from pathlib import Path
import unittest
import tempfile
import sys
from unittest.mock import patch

from aura_native.config.paths import PathConfigurationError, RuntimePaths


ROOT = Path(__file__).resolve().parents[2]
if sys.flags.no_site:
    _PROFILE_TMP = None
    PROFILE = ROOT / "tests" / "native" / "_lot1-strict-profile"
else:
    _PROFILE_TMP = tempfile.TemporaryDirectory(prefix="aura-paths-", dir=ROOT)
    PROFILE = Path(_PROFILE_TMP.name) / "profile"
PROFILE_RELATIVE = PROFILE.relative_to(ROOT).as_posix()


class PathTests(unittest.TestCase):
    def resolve(self, path=PROFILE):
        return RuntimePaths.resolve(path, project_root=ROOT)

    def test_explicit_absolute_path(self):
        paths = self.resolve()
        self.assertEqual(paths.state_dir, PROFILE)
        self.assertEqual(paths.resources_dir, ROOT / "app")
        for name in ("config_dir", "data_dir", "cache_dir", "logs_dir", "models_dir"):
            self.assertTrue(getattr(paths, name).is_relative_to(PROFILE))

    def test_relative_path_is_project_relative(self):
        paths = self.resolve(PROFILE_RELATIVE)
        self.assertEqual(paths.state_dir, PROFILE)

    def test_cwd_does_not_control_resolution(self):
        with patch("os.getcwd", return_value=str(ROOT / "tools")):
            self.assertEqual(self.resolve(PROFILE_RELATIVE).state_dir, PROFILE)

    def test_spaces_and_unicode(self):
        path = PROFILE / "Profil été 漢字"
        self.assertEqual(self.resolve(path).state_dir, path)

    def test_normalizes_parent_segments(self):
        self.assertEqual(self.resolve(PROFILE / "child" / ".." / "data-root").state_dir, PROFILE / "data-root")

    def test_requires_explicit_path(self):
        for value in ("", "   ", None, 123):
            with self.subTest(value=value), self.assertRaises(PathConfigurationError):
                self.resolve(value)

    def test_rejects_environment_placeholders(self):
        for value in ("~/state", "%LOCALAPPDATA%/state", "$HOME/state"):
            with self.subTest(value=value), self.assertRaises(PathConfigurationError):
                self.resolve(value)

    @unittest.skipUnless(os.name == "nt", "Windows-specific path semantics")
    def test_rejects_ambiguous_windows_paths(self):
        for value in ("C:relative", "\\relative"):
            with self.subTest(value=value), self.assertRaises(PathConfigurationError):
                self.resolve(value)

    def test_rejects_root_and_project_ancestors(self):
        for path in (ROOT, ROOT.parent, Path(ROOT.anchor)):
            with self.subTest(path=path), self.assertRaises(PathConfigurationError):
                self.resolve(path)

    def test_protects_application_and_interpreter_directories(self):
        for name in ("src", "app", "tools", "docs", ".venv", ".runtime"):
            with self.subTest(name=name), self.assertRaises(PathConfigurationError):
                self.resolve(ROOT / name / "state")

    def test_rejects_a_file_as_state(self):
        with self.assertRaises(PathConfigurationError):
            self.resolve(ROOT / "pyproject.toml")

    def test_resolution_failure_has_no_fallback(self):
        with patch.object(Path, "resolve", side_effect=PermissionError("test denial")):
            with self.assertRaisesRegex(PathConfigurationError, "no fallback"):
                self.resolve()

    def test_rejects_redirected_state_child(self):
        original = Path.resolve

        def simulated_junction(path, *args, **kwargs):
            if path == PROFILE / "data":
                return ROOT / "app"
            return original(path, *args, **kwargs)

        with patch.object(Path, "resolve", simulated_junction):
            with self.assertRaisesRegex(PathConfigurationError, "outside state_dir"):
                self.resolve()

    def test_rejects_state_redirected_to_source(self):
        original = Path.resolve

        def simulated_junction(path, *args, **kwargs):
            if path == PROFILE:
                return ROOT / "src"
            return original(path, *args, **kwargs)

        with patch.object(Path, "resolve", simulated_junction):
            with self.assertRaisesRegex(PathConfigurationError, "protected"):
                self.resolve()

    def test_legacy_environment_does_not_change_paths(self):
        expected = self.resolve()
        fake = str(PROFILE / "unread-legacy-location")
        with patch.dict(os.environ, {k: fake for k in (
            "AURA_ROOT", "AURA_UI_ROOT", "LOCALAPPDATA", "APPDATA", "PYTHONPATH", "PYTHONHOME"
        )}):
            self.assertEqual(self.resolve(), expected)

    def test_resolution_creates_nothing(self):
        self.assertFalse(PROFILE.exists())
        self.resolve()
        self.assertFalse(PROFILE.exists())

