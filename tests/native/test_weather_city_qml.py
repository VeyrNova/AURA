import unittest
from pathlib import Path

ROOT=Path(__file__).parents[2]

class WeatherCityQmlContractTests(unittest.TestCase):
    def test_weather_view_exposes_real_city_search_flow(self):
        source=(ROOT/'app/qml/views/WeatherView.qml').read_text(encoding='utf-8')
        self.assertIn('weatherBridge.searchLocations',source)
        self.assertIn('weatherBridge.cityResults',source)
        self.assertIn('weatherBridge.selectCity',source)
        self.assertNotIn('WebEngine',source)

if __name__=='__main__': unittest.main()
