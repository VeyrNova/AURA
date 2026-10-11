import os
import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QUrl, QObject
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from aura_native.maps.service import MapsService
from aura_native.maps.qt_bridge import NativeMapsBridge
from aura_native.weather.provider import FakeWeatherProvider
from aura_native.weather.service import WeatherService

ROOT = Path(__file__).parents[2]


class MapsVisualContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QApplication.instance() or QApplication([])

    def test_real_maps_view_loads_natural_earth_and_nice_marker(self):
        weather = WeatherService(FakeWeatherProvider())
        service = MapsService(weather, ROOT / 'app/assets/maps')
        bridge = NativeMapsBridge(service)
        view = QQuickView()
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.rootContext().setContextProperty('mapsBridge', bridge)
        view.setWidth(1100); view.setHeight(700)
        view.setSource(QUrl.fromLocalFile(str(ROOT / 'app/qml/views/MapsView.qml')))
        try:
            self.assertEqual(view.status(), QQuickView.Ready)
            root = view.rootObject()
            base = root.findChild(QObject, 'nativeMapsBaseMap')
            self.assertIsNotNone(base)
            self.assertEqual(bool(base.property('mapBaseReady')), bool(bridge.mapBaseReady))
            self.assertTrue(bridge.mapBaseReady)
            self.assertGreater(base.property('landFeatureCount'), 100)
            self.assertGreater(base.property('coastlineFeatureCount'), 100)
            bridge.search('Nice')
            for _ in range(20):
                if bridge.places: break
                QTest.qWait(10)
            self.assertEqual(bridge.places[0]['name'], 'Nice')
            bridge.select(0); self.assertEqual(bridge.selectedPlace['name'], 'Nice')
            self.assertTrue(base.property('showMarker'))
            self.assertAlmostEqual(base.property('markerLatitude'), 43.7, delta=1)
            for width, height in ((1100,700),(1280,720),(1440,900),(1920,1080)):
                view.setWidth(width); view.setHeight(height); QTest.qWait(1)
                self.assertGreater(base.width(), 0)
                self.assertLessEqual(base.x() + base.width(), root.width() + 1)
                self.assertLessEqual(base.y() + base.height(), root.height() + 1)
        finally:
            view.setSource(QUrl())

    def test_bundled_geojson_is_used_by_actual_map_component(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests/native/_evidence') as folder:
            root = Path(folder)
            land = {'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[6,42],[9,42],[9,45],[6,45],[6,42]]]}}]}
            coast = {'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'LineString','coordinates':[[6,42],[9,42],[9,45]]}}]}
            (root/'land.geojson').write_text(json.dumps(land), encoding='utf-8')
            (root/'coastline.geojson').write_text(json.dumps(coast), encoding='utf-8')
            bridge = NativeMapsBridge(MapsService(WeatherService(FakeWeatherProvider()), root))
            view = QQuickView(); view.setResizeMode(QQuickView.SizeRootObjectToView)
            view.rootContext().setContextProperty('mapsBridge', bridge)
            view.setWidth(1100); view.setHeight(700)
            view.setSource(QUrl.fromLocalFile(str(ROOT / 'app/qml/views/MapsView.qml')))
            try:
                self.assertEqual(view.status(), QQuickView.Ready)
                base = view.rootObject().findChild(QObject, 'nativeMapsBaseMap')
                self.assertTrue(base.property('mapBaseReady'))
                self.assertEqual(base.property('geometryCount'), 2)
            finally:
                view.setSource(QUrl())

    def test_missing_asset_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests/native/_evidence') as folder:
            bridge = NativeMapsBridge(MapsService(WeatherService(FakeWeatherProvider()), Path(folder)))
            self.assertFalse(bridge.mapBaseReady)
            self.assertEqual(bridge.geometry['land_polygons'], [])

