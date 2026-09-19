import unittest
from pathlib import Path
from ai.local_first_voice import social_reply

ROOT=Path(__file__).resolve().parents[1]

class TestWeatherWorkspace367(unittest.TestCase):
    def test_workspace_exists(self):
        text=(ROOT/'ui'/'weather_workspace.py').read_text(encoding='utf-8')
        self.assertIn('class WeatherWorkspaceDialog',text)
        self.assertIn('COUCHES',text)
        self.assertIn('RECHERCHER',text)
        self.assertIn('LIRE LE RÉSUMÉ',text)
    def test_application_nav_hook(self):
        text=(ROOT/'ui'/'main_window.py').read_text(encoding='utf-8')
        self.assertIn('_nav_buttons[1].clicked.connect(self._open_applications_dialog)',text)
        self.assertIn('WeatherWorkspaceDialog',text)
    def test_weather_payload_is_rich(self):
        text=(ROOT/'tools'/'weather.py').read_text(encoding='utf-8')
        self.assertIn('daily_forecast',text)
        self.assertIn('hourly_forecast',text)
        self.assertIn('forecast_days": "8"',text)
    def test_map_has_weather_focus_layer(self):
        text=(ROOT/'ui'/'map_widget.py').read_text(encoding='utf-8')
        self.assertIn('set_weather_layer',text)
        self.assertIn('_draw_weather_focus',text)
    def test_social_ready_avoids_ambiguous_pronunciation(self):
        text=(ROOT/'ai'/'local_first_voice.py').read_text(encoding='utf-8')
        self.assertNotIn('Je suis opérationnelle.', text)
        self.assertIn('Je suis là', social_reply('Bonjour Aura'))
        self.assertNotIn('Je suis prête.',text)

if __name__=='__main__': unittest.main()
