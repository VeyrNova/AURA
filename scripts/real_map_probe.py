from config.settings import settings
from tools.maps import MapsTool
from tools.safe_http import SafeHTTPClient


def main():
    client = SafeHTTPClient(timeout=settings.WEB_HTTP_TIMEOUT, max_bytes=settings.WEB_MAX_RESPONSE_BYTES, max_redirects=settings.WEB_MAX_REDIRECTS)
    result = MapsTool(client).directions("Toulon", origin="Vidauban", travelmode="driving")
    print(f"AURA_REAL_MAP_VERSION={settings.APP_VERSION}")
    print(f"AURA_REAL_MAP_OK={result.ok}")
    print(f"AURA_REAL_MAP_ROUTE_PROVIDER={result.data.get('route_provider', 'fallback')}")
    print(f"AURA_REAL_MAP_POINTS={len(result.data.get('route_points') or [])}")
    print(f"AURA_REAL_MAP_DISTANCE_KM={result.data.get('distance_km', 'n/a')}")
    print(f"AURA_REAL_MAP_DURATION_MIN={result.data.get('duration_min', 'n/a')}")
    if result.data.get('route_warning'):
        print(f"AURA_REAL_MAP_WARNING={result.data['route_warning']}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
