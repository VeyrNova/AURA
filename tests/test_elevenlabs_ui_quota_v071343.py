import unittest

from config.settings import settings
from regression_compat import assert_version_at_least


class ElevenLabsUIQuotaTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.4.3")

    def test_key_setup_is_not_gated_by_selected_engine(self):
        source = (settings.BASE_DIR / "ui" / "voice_settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn("self.eleven_key_edit.setEnabled(True)", source)
        self.assertIn("self.eleven_key_paste.setEnabled(True)", source)
        self.assertIn("self.eleven_import_jarvis.setEnabled(True)", source)
        self.assertIn("can_query = has_saved_key or entered_valid", source)
        self.assertNotIn("self.eleven_key_edit.setEnabled(eleven)", source)

    def test_refresh_is_key_aware(self):
        source = (settings.BASE_DIR / "ui" / "voice_settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn("self.eleven_refresh_button.setEnabled(can_query)", source)
        self.assertIn("valid_elevenlabs_api_key(entered)", source)

    def test_quota_panel_shows_remaining_usage(self):
        source = (settings.BASE_DIR / "ui" / "voice_settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn('form.addRow("Quota ElevenLabs", self.eleven_quota_label)', source)
        self.assertIn('remaining = max(0, limit - used)', source)
        self.assertIn('crédits restants', source)


if __name__ == "__main__":
    unittest.main()
