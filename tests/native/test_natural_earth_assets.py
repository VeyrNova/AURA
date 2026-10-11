"""Offline integrity checks for the bundled Natural Earth map data."""
import hashlib
import json
import math
import unittest
from pathlib import Path

from aura_native.maps.service import MapsService

ROOT = Path(__file__).parents[2]
ASSETS = ROOT / 'app/assets/maps/natural_earth'
EXPECTED = {
    'world_50m_land.geojson': ('62677ae544e7aa8ab571e5020c41fc0ba13a8d35883b2cb8740dc2180da4aa3e', 1400),
    'world_50m_coastline.geojson': ('97e04fa2f5e732b56ea02178046a02c2d9b0ace52b9812cbbf2cd9df730d57b2', 1400),
    'europe_10m_land.geojson': ('a6670526829d395004934949bfbe3536e820e8563857013d6ae79488c47bb018', 1100),
    'europe_10m_coastline.geojson': ('4f9ff2798b972b31c3bc0a901638b6ceec63fb32cdf18b0711a7a3714b92355d', 500),
}


class NaturalEarthAssetTests(unittest.TestCase):
    def test_provenance_and_all_four_geojson_files(self):
        source = (ASSETS / 'SOURCE.md').read_text(encoding='utf-8')
        self.assertIn('Public Domain', source)
        self.assertIn('naturalearthdata.com', source)
        for filename, (expected_sha, minimum) in EXPECTED.items():
            raw = (ASSETS / filename).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_sha, filename)
            document = json.loads(raw)
            self.assertEqual(document['type'], 'FeatureCollection')
            self.assertGreater(len(document['features']), minimum)
            is_land = 'land' in filename
            for feature in document['features']:
                geometry = feature['geometry']
                self.assertEqual(geometry['type'], 'Polygon' if is_land else 'LineString')
                parts = geometry['coordinates'] if is_land else [geometry['coordinates']]
                for line in parts:
                    for longitude, latitude in line:
                        self.assertTrue(math.isfinite(longitude) and math.isfinite(latitude))
                        self.assertLessEqual(abs(longitude), 180)
                        self.assertLessEqual(abs(latitude), 90)

    def test_multi_resolution_cache_and_region(self):
        service = MapsService(geometry_root=ROOT / 'app/assets/maps')
        regional = service.local_geometry('regional')
        world = service.local_geometry('world')
        self.assertIs(regional, service.local_geometry('regional'))
        self.assertIs(world, service.local_geometry('world'))
        self.assertGreater(len(regional['land_polygons']), 1100)
        self.assertGreater(len(regional['coastlines']), 500)
        self.assertGreater(len(world['land_polygons']), 1400)
        for line in regional['land_polygons'] + regional['coastlines']:
            for longitude, latitude in line:
                self.assertTrue(-14 <= longitude <= 38 and 30 <= latitude <= 72)


if __name__ == '__main__': unittest.main()
