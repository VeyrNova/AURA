import unittest
from pathlib import Path

from tools.maps import MapsTool, extract_maps_request
from tools.internet_manager import InternetToolManager

ROOT = Path(__file__).resolve().parents[1]


class FastToolHudV07015612Tests(unittest.TestCase):
    def test_version_and_fast_mode_defaults_present(self):
        s = (ROOT / 'config' / 'settings.py').read_text(encoding='utf-8')
        self.assertIn('0.7.0.15.6.12', s)
        self.assertIn('FAST_TEXT_TEST_MODE', s)
        self.assertIn('_env_bool("FAST_TEXT_TEST_MODE", True)', s)
        self.assertIn('WEATHER_HUD_POPUP_ENABLED', s)
        self.assertIn('MAPS_HUD_POPUP_ENABLED', s)

    def test_audio_runtime_is_independent_from_legacy_fast_text_mode(self):
        s = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
        cfg = (ROOT / 'config' / 'settings.py').read_text(encoding='utf-8')
        self.assertIn('settings.AUDIO_RUNTIME_PAUSED', s)
        self.assertIn('XTTSBackgroundPrewarmWorker', s)
        self.assertIn('Audio runtime enabled: XTTS background prewarm deferred until UI ready', s)
        self.assertIn('AUDIO_RUNTIME_ENABLED', cfg)

    def test_weather_popup_and_structured_payload(self):
        ui = (ROOT / 'ui' / 'tool_hud_popups.py').read_text(encoding='utf-8')
        weather = (ROOT / 'tools' / 'weather.py').read_text(encoding='utf-8')
        self.assertIn('class WeatherHudPopup', ui)
        self.assertIn('QUALITÉ DE L’AIR', ui)
        self.assertIn('surface_pressure,visibility,dew_point_2m', weather)
        self.assertIn('european_aqi,pm2_5,pm10', weather)
        self.assertIn('data=data', weather)

    def test_maps_request_and_google_urls(self):
        req = extract_maps_request('itinéraire de Vidauban à Toulon')
        self.assertEqual(req['action'], 'directions')
        self.assertEqual(req['origin'], 'Vidauban')
        self.assertEqual(req['destination'], 'Toulon')
        url = MapsTool.directions_url('Toulon', origin='Vidauban')
        self.assertIn('google.com/maps/dir/', url)
        self.assertIn('api=1', url)
        self.assertIn('origin=Vidauban', url)
        self.assertIn('destination=Toulon', url)

    def test_internet_manager_routes_maps_before_llm(self):
        manager = InternetToolManager()
        plan = manager.plan('montre-moi Toulon sur la carte')
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, 'maps')
        self.assertEqual(plan.action, 'MAPS_LOCATE')

    def test_maps_popup_is_dedicated(self):
        ui = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
        popup = (ROOT / 'ui' / 'tool_hud_popups.py').read_text(encoding='utf-8')
        self.assertIn('_show_maps_popup', ui)
        self.assertIn('_show_weather_popup', ui)
        self.assertIn('class MapsHudPopup', popup)
        self.assertIn('OUVRIR DANS GOOGLE MAPS', popup)


if __name__ == '__main__':
    unittest.main()
