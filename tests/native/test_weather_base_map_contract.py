import os
import unittest
from pathlib import Path
from PySide6.QtCore import QUrl, QObject
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from aura_native.weather.provider import FakeWeatherProvider
from aura_native.weather.service import WeatherService
from aura_native.weather.qt_bridge import NativeWeatherBridge
from aura_native.maps.service import MapsService

ROOT = Path(__file__).parents[2]


class WeatherBaseMapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QApplication.instance() or QApplication([])

    def test_shared_base_map_uses_natural_earth_geometry(self):
        service = WeatherService(FakeWeatherProvider())
        bridge = NativeWeatherBridge(service, map_service=MapsService(service, ROOT / 'app/assets/maps'))
        view = QQuickView(); view.rootContext().setContextProperty('weatherBridge', bridge)
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.setWidth(1280); view.setHeight(720)
        view.setSource(QUrl.fromLocalFile(str(ROOT / 'app/qml/views/WeatherView.qml')))
        try:
            self.assertEqual(view.status(), QQuickView.Ready)
            base = view.rootObject().findChild(QObject, 'weatherGeoBaseMap')
            self.assertIsNotNone(base)
            self.assertTrue(base.property('mapBaseReady'))
            self.assertGreater(base.property('landFeatureCount'), 100)
            self.assertGreater(base.property('coastlineFeatureCount'), 100)
            overlay = view.rootObject().findChild(QObject, 'weatherScalarOverlay')
            self.assertIsNotNone(overlay)
            self.assertTrue(overlay.property('visible'))
            self.assertLess(overlay.property('opacity'), 0.5)
            bridge.ensureLoaded()
            for _ in range(100):
                if bridge.locationName: break
                QTest.qWait(10)
            self.assertEqual(bridge.locationName, 'Nice')
            self.assertTrue(base.property('showMarker'))
            for width, height in ((1100,700),(1280,720),(1440,900),(1920,1080)):
                view.setWidth(width); view.setHeight(height); QTest.qWait(1)
                frame = base.parentItem()
                self.assertGreater(base.width(), 0)
                self.assertLessEqual(frame.x() + frame.width(), view.rootObject().width() + 1)
                self.assertLessEqual(frame.y() + frame.height(), view.rootObject().height() + 1)
            self.assertEqual(bridge.terrainJson, '{}')
            self.assertIsNotNone(view.rootObject().findChild(QObject, 'weatherGeographyUnavailable'))
        finally:
            view.setSource(QUrl())

    def test_missing_geometry_does_not_claim_ready(self):
        bridge = NativeWeatherBridge(WeatherService(FakeWeatherProvider()))
        view = QQuickView(); view.rootContext().setContextProperty('weatherBridge', bridge)
        view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.setWidth(1100); view.setHeight(700)
        view.setSource(QUrl.fromLocalFile(str(ROOT / 'app/qml/views/WeatherView.qml')))
        try:
            self.assertEqual(view.status(), QQuickView.Ready)
            base = view.rootObject().findChild(QObject, 'weatherGeoBaseMap')
            self.assertFalse(base.property('geometryReady'))
            self.assertTrue(view.rootObject().findChild(QObject, 'weatherGeographyUnavailable').property('visible'))
        finally:
            view.setSource(QUrl())

