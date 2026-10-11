"""Offline road-routing parity tests; never contact OSRM."""
import os
import unittest
from unittest.mock import patch
from PySide6.QtGui import QDesktopServices
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, QUrl
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from aura_native.maps.routing import FakeRoutingBackend, OSRMRoutingBackend, RoutePlace, RoutingError, RoutingService
from aura_native.maps.service import MapsService
from aura_native.maps.qt_bridge import NativeMapsBridge
from aura_native.location import CurrentLocation, CurrentLocationService, FakeCurrentLocationProvider

ROOT = Path(__file__).parents[2]
PLACES = {'vidauban': (43.427, 6.431, 'Vidauban'), 'nice': (43.703, 7.266, 'Nice'), 'paris': (48.857, 2.352, 'Paris')}


class FakeGeocoder:
    def search_locations(self, query):
        row = PLACES.get(query.strip().lower())
        return [SimpleNamespace(name=row[2], latitude=row[0], longitude=row[1], country='France')] if row else []


def fixture(origin='vidauban', destination='nice'):
    a, b = PLACES[origin], PLACES[destination]
    return {'distance': 127000 if destination == 'nice' else 930000,
            'duration': 5460 if destination == 'nice' else 36000,
            'geometry': {'type': 'LineString', 'coordinates': [[a[1], a[0]], [(a[1]+b[1])/2, (a[0]+b[0])/2], [b[1], b[0]]]},
            'legs': [{'steps': [{'name': 'Route principale', 'maneuver': {'type': 'depart'}},
                                {'name': 'Centre-ville', 'maneuver': {'type': 'arrive'}}]}]}


class RoutingNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def wait_for(predicate):
        for _ in range(100):
            if predicate(): return
            QTest.qWait(10)
        raise AssertionError('asynchronous operation did not complete')

    def test_service_normalizes_metrics_geometry_and_instructions(self):
        backend = FakeRoutingBackend(fixture())
        service = RoutingService(backend)
        origin = RoutePlace('Vidauban', 43.427, 6.431)
        destination = RoutePlace('Nice', 43.703, 7.266)
        route = service.calculate(origin, destination)
        self.assertEqual(len(backend.calls), 1)
        self.assertEqual(route.distance_m, 127000)
        self.assertEqual(route.duration_s, 5460)
        self.assertEqual(route.geometry[0], (6.431, 43.427))
        self.assertIn('Départ', route.instructions[0])

    def test_input_and_backend_error_states(self):
        a = RoutePlace('Vidauban', 43.427, 6.431)
        b = RoutePlace('Nice', 43.703, 7.266)
        for origin, destination, code in ((None,b,'origin_missing'),(a,None,'destination_missing'),(a,a,'same_origin_destination')):
            with self.subTest(code=code), self.assertRaises(RoutingError) as caught:
                RoutingService(FakeRoutingBackend(fixture())).calculate(origin,destination)
            self.assertEqual(caught.exception.code, code)
        for code in ('no_route','provider_unavailable','network_error','rate_limited'):
            with self.subTest(code=code), self.assertRaises(RoutingError) as caught:
                RoutingService(FakeRoutingBackend(fixture(),error=code)).calculate(a,b)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(RoutingError) as caught:
            RoutingService(FakeRoutingBackend({'distance':5,'duration':5,'geometry':{'type':'LineString','coordinates':[]}})).calculate(a,b)
        self.assertEqual(caught.exception.code, 'invalid_result')
        with self.assertRaises(RoutingError) as caught:
            RoutingService(FakeRoutingBackend(fixture())).calculate(RoutePlace('Bad', 'oops', 6), b)
        self.assertEqual(caught.exception.code, 'invalid_location')

    def test_osrm_contract_and_invalid_provider_payload_are_offline(self):
        a = RoutePlace('Vidauban', 43.427, 6.431)
        b = RoutePlace('Nice', 43.703, 7.266)
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, *_): return b'{"code":"Ok","routes":[{"distance":127000,"duration":5460,"geometry":{"type":"LineString","coordinates":[[6.431,43.427],[7.266,43.703]]}}]}'
        with patch('aura_native.maps.routing.urlopen', return_value=Reply()) as urlopen:
            route = RoutingService(OSRMRoutingBackend()).calculate(a,b)
        self.assertEqual(route.distance_m, 127000)
        request = urlopen.call_args.args[0]
        self.assertIn('routing.openstreetmap.de/routed-car/route/v1/driving/6.431000,43.427000;7.266000,43.703000', request.full_url)
        self.assertIn('geometries=geojson', request.full_url)
        self.assertIn('steps=true', request.full_url)
        self.assertTrue(request.get_header('User-agent'))
        class InvalidReply(Reply):
            def read(self, *_): return b'[]'
        with patch('aura_native.maps.routing.urlopen', return_value=InvalidReply()):
            with self.assertRaises(RoutingError) as caught: OSRMRoutingBackend().route(a,b)
        self.assertEqual(caught.exception.code, 'invalid_result')

    def test_real_qml_bridge_fake_vidauban_nice_and_nice_paris(self):
        backend = FakeRoutingBackend(fixture())
        service = MapsService(FakeGeocoder(), ROOT/'app/assets/maps', RoutingService(backend))
        bridge = NativeMapsBridge(service)
        view = QQuickView(); view.setResizeMode(QQuickView.SizeRootObjectToView)
        view.rootContext().setContextProperty('mapsBridge', bridge)
        view.setWidth(1280); view.setHeight(720)
        view.setSource(QUrl.fromLocalFile(str(ROOT/'app/qml/views/MapsView.qml')))
        try:
            self.assertEqual(view.status(), QQuickView.Ready)
            root = view.rootObject()
            base = root.findChild(QObject, 'nativeMapsBaseMap')
            self.assertIsNotNone(root.findChild(QObject, 'nativeRoutePanel'))
            with patch('aura_native.maps.routing.urlopen', side_effect=AssertionError('real routing forbidden in fake test')):
              for origin, destination in (('vidauban','nice'),('nice','paris')):
                backend.response = fixture(origin,destination)
                bridge.searchOrigin(origin); self.wait_for(lambda: len(bridge.originCandidates)>0)
                bridge.selectOrigin(0)
                bridge.searchDestination(destination); self.wait_for(lambda: len(bridge.destinationCandidates)>0)
                bridge.selectDestination(0)
                bridge.calculateRoute(); self.wait_for(lambda: bridge.routingState != 'routing')
                self.assertTrue(bridge.routeReady)
                self.assertEqual(bridge.routePointCount, 3)
                self.assertTrue(base.property('routeReady'))
                self.assertEqual(base.property('routePointCount'), 3)
                self.assertTrue(root.findChild(QObject,'geoRouteLayer').property('visible'))
                self.assertTrue(root.findChild(QObject,'geoOriginMarker').property('visible'))
                self.assertTrue(root.findChild(QObject,'geoDestinationMarker').property('visible'))
                self.assertGreater(bridge.routeDistance, 0)
                self.assertGreater(bridge.routeDuration, 0)
                self.assertIn('km', root.findChild(QObject,'nativeRouteMetrics').property('text'))
                google = root.findChild(QObject, 'nativeRouteGoogleMaps')
                self.assertTrue(google.property('visible'))
                with patch.object(QDesktopServices, 'openUrl', return_value=True) as open_url:
                    self.assertTrue(bridge.openGoogleMaps())
                    self.assertIn('google.com/maps/dir/?', open_url.call_args.args[0].toString())
                self.assertGreater(bridge.routeSpanKm, 0)
                for marker in ('geoOriginMarker','geoDestinationMarker'):
                    item = root.findChild(QObject,marker)
                    self.assertGreaterEqual(item.x(), -1)
                    self.assertLessEqual(item.x()+item.width(), base.width()+1)
                bridge.clearRoute()
                self.assertFalse(bridge.routeReady)
            self.assertEqual(len(backend.calls), 2)
        finally:
            view.setSource(QUrl())

    def test_qml_bridge_current_location_fake_sets_origin_without_network(self):
        location = CurrentLocationService(FakeCurrentLocationProvider(CurrentLocation(43.427, 6.431)))
        service = MapsService(FakeGeocoder(), ROOT/'app/assets/maps', RoutingService(FakeRoutingBackend(fixture())))
        bridge = NativeMapsBridge(service, location_service=location)
        bridge.requestCurrentLocation()
        self.assertTrue(bridge.currentLocationReady)
        self.assertEqual(bridge.origin['label'], 'Ma position')
        self.assertAlmostEqual(bridge.origin['latitude'], 43.427)


if __name__ == '__main__': unittest.main()
