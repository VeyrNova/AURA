# Natural Earth vector source

Natural Earth map data is **Public Domain** under its [official terms](https://www.naturalearthdata.com/about/terms-of-use/). Acquired 2026-10-03 from Natural Earth's AWS hosting, identified by the [official 1:50m](https://www.naturalearthdata.com/downloads/50m-physical-vectors/) and [1:10m](https://www.naturalearthdata.com/downloads/10m-physical-vectors/) pages. The website's direct archive links were malformed at acquisition; the Natural Earth AWS-hosted archive URLs below returned the four matching themes. No third-party mirror was used.

| Theme | Scale | Version announced | Official archive URL | Download bytes | Download SHA-256 |
|---|---|---|---|---:|---|
| Land | 1:50m | 4.0.0 | https://naturalearth.s3.amazonaws.com/50m_physical/ne_50m_land.zip | 457183 | `0b8e670cf80dce9cbebe2a193bc44ba5602758c22e1fa603980553646d7ff162` |
| Coastline | 1:50m | 4.0.0 | https://naturalearth.s3.amazonaws.com/50m_physical/ne_50m_coastline.zip | 455936 | `640f805509b822f57f4840a2e18d9ff2412cf1cf6976124701c2789436166fde` |
| Land | 1:10m | 5.1.1 | https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_land.zip | 3269070 | `e547d749445eaa0964aba76738090ec88f5e63c4585122170f98c67a7ea922dc` |
| Coastline | 1:10m | 4.1.0 | https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_coastline.zip | 3069451 | `bfa04cdbcbef07ef90dfca1dabb48062eca29900a113df0f389303e255484017` |

The four ZIP files are retained locally in `tests/native/_evidence/natural_earth_source` for acquisition evidence, outside the distributable map assets. `tools/prepare_map_assets.py` converts the SHP geometry to GeoJSON with Python's standard library. The 1:10m data are clipped to longitude -14..38 and latitude 30..72 (Europe and Mediterranean); the 1:50m data remain global. Build-time Douglas–Peucker simplification uses a 0.005° tolerance at 1:10m (about 0.5 km latitude) and 0.02° at 1:50m (about 2.2 km latitude); no runtime simplification occurs. The runtime reads only GeoJSON and needs no converter or network.

| Output | Features | Rings/lines | Coordinates | Bounding box [W,S,E,N] | SHA-256 |
|---|---:|---:|---:|---|---|
| `world_50m_land.geojson` | 1422 | 1422 | 35432 | [-180,-89.9989,180,83.5996] | `62677ae544e7aa8ab571e5020c41fc0ba13a8d35883b2cb8740dc2180da4aa3e` |
| `world_50m_coastline.geojson` | 1429 | 1429 | 35185 | [-180,-85.1922,180,83.5996] | `97e04fa2f5e732b56ea02178046a02c2d9b0ace52b9812cbbf2cd9df730d57b2` |
| `europe_10m_land.geojson` | 1142 | 1142 | 34038 | [-14,30,38,71.1804] | `a6670526829d395004934949bfbe3536e820e8563857013d6ae79488c47bb018` |
| `europe_10m_coastline.geojson` | 512 | 512 | 29890 | [-14,30,38,71.1804] | `4f9ff2798b972b31c3bc0a901638b6ceec63fb32cdf18b0711a7a3714b92355d` |

All four files are valid GeoJSON FeatureCollections with finite, valid WGS84 coordinates. The geometry is for display, not navigation or surveying.
