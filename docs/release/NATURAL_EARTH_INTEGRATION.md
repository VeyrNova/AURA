# Natural Earth local vector integration

Acquired 2026-10-03 from Natural Earth's AWS hosting after confirming the
themes and versions on its official site. Natural Earth licenses the data as
Public Domain. Exact URLs, versions, ZIP SHA-256 values, output counts, bounds
and output hashes are in `app/assets/maps/natural_earth/SOURCE.md`.

The build-only `tools/prepare_map_assets.py` converts four SHP archives with
Python standard library code. Global 1:50m land/coastline and clipped regional
1:10m land/coastline are bundled as local GeoJSON. The 10m region covers
longitude -14..38, latitude 30..72. Douglas–Peucker tolerance is 0.005° at
10m and 0.02° at 50m. No shapefile parser or download is needed at runtime.

`MapsService` parses each resolution once per service instance and caches the
result. `GeoBaseMap.qml` draws land and coast with one Mercator projection and
uses the same projection for the marker. Maps and Weather select regional 10m
for Europe/Mediterranean close views and global 50m for wider or out-of-region
views; they never draw both resolutions together. Weather's old terrain
fallback canvas and emboss code were removed. The scalar weather overlay sits
above the shared map with opacity below 0.5; missing or corrupt map data show
an explicit unavailable state.

Observed on this Windows host after simplification: regional parse 43.3 ms,
global parse 37.7 ms, regional cache hit 0.002 ms. One offscreen capture run
reported Maps QML load 216 ms / grab 29 ms and Weather QML load 1069 ms / grab
127 ms. These are approximate local observations, not a startup SLA or a
visible-window frame-time measurement.

The offscreen Nice captures in `tests/native/_evidence` show the Mediterranean
coast and city marker in Maps and Weather. They are local evidence only:
**LIVE_WINDOWS=NOT_AVAILABLE** because the available Computer Use surface
reported `apps=[]`. A visible Windows review is still required for map labels,
coast detail, readability and interactions. The offscreen font renderer showed
square glyphs, so typography cannot be accepted from those captures.

Offline tests cover asset hashes and geometry, missing assets, both real QML
views, Nice marker, overlay separation and viewport bounds at 1100×700,
1280×720, 1440×900 and 1920×1080. Network was used only for the four archive
downloads. Runtime operation and tests used no network, OAuth, Gmail or Google
write. No BAT, default launch mode, WebEngine or Git state was changed.

Final fresh headless run: 487 tests discovered, 237 executed and 237 passed;
0 failures, 0 failed imports, 0 timeouts, completed. ADF 35/35. Native QML
self-check passed. Bytecode count 0.
