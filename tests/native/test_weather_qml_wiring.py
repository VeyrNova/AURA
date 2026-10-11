import unittest
from aura_native.weather.provider import FakeWeatherProvider, WeatherProviderError
from aura_native.weather.service import WeatherService
from aura_native.weather.qt_bridge import NativeWeatherBridge
from PySide6.QtCore import QCoreApplication

class WeatherQmlWiringTests(unittest.TestCase):
    def test_fake_provider_reaches_bridge_signal(self):
        app=QCoreApplication.instance() or QCoreApplication([])
        fake=FakeWeatherProvider(); bridge=NativeWeatherBridge(WeatherService(fake),default_location='Nice')
        changes=[]; bridge.weatherChanged.connect(lambda:changes.append(bridge.temperature))
        bridge.refresh()
        for _ in range(200):
            app.processEvents()
            if not bridge.loading: break
            import time; time.sleep(.005)
        self.assertFalse(bridge.loading)
        self.assertEqual(bridge.locationName,'Nice')
        self.assertEqual(bridge.temperature,20.0)
        self.assertTrue(any(v==20.0 for v in changes))
        self.assertEqual([x[0] for x in fake.calls],['geocode','forecast'])
    def test_error_is_safe(self):
        app=QCoreApplication.instance() or QCoreApplication([])
        fake=FakeWeatherProvider(failure=WeatherProviderError('weather_timeout','private detail'))
        bridge=NativeWeatherBridge(WeatherService(fake)); bridge.refresh()
        for _ in range(200):
            app.processEvents()
            if not bridge.loading: break
            import time; time.sleep(.005)
        self.assertEqual(bridge.error,'weather_timeout')

    def test_city_search_results_and_selection(self):
        app=QCoreApplication.instance() or QCoreApplication([])
        fake=FakeWeatherProvider(geocode_payload={'results':[
            {'name':'Nice','country':'France','latitude':43.7,'longitude':7.25,'timezone':'Europe/Paris'},
            {'name':'Paris','country':'France','latitude':48.85,'longitude':2.35,'timezone':'Europe/Paris'}]})
        bridge=NativeWeatherBridge(WeatherService(fake))
        bridge.searchLocations('France')
        for _ in range(200):
            app.processEvents()
            if not bridge.citySearchLoading: break
            import time; time.sleep(.005)
        self.assertEqual([x['name'] for x in bridge.cityResults],['Nice','Paris'])
        bridge.selectCity(bridge.cityResults[1])
        for _ in range(200):
            app.processEvents()
            if not bridge.loading: break
            import time; time.sleep(.005)
        self.assertEqual(bridge.locationName,'Paris')
        self.assertEqual(bridge.temperature,20.0)

if __name__=='__main__': unittest.main()
