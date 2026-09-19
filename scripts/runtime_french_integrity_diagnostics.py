"""Dependency-light diagnostics for AURA v0.7.0.13."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from ai.speech_quality import deterministic_french_fallback, find_voice_quality_issues
from ai.voice_brevity import voice_brevity_policy, voice_output_contract
from config.settings import settings
from tools.safe_http import HTTPResponse
from tools.weather import WeatherTool


class FakeHTTP:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def get_json(self, url, headers=None):
        payload = self.payloads.pop(0)
        return payload, HTTPResponse(url, 200, "application/json", json.dumps(payload).encode())


def main() -> int:
    print("=== AURA v0.7.0.13 - RUNTIME LATENCY & FRENCH INTEGRITY ===")
    print(f"Version                    : {settings.APP_VERSION}")
    print(f"XTTS idle residency       : {settings.RESOURCE_XTTS_IDLE_SECONDS:.0f}s")
    print(f"Voice prewarm delay       : {settings.VOICE_BRAIN_PREWARM_DELAY_MS}ms")
    print(f"Voice prewarm RAM ceiling : {settings.VOICE_BRAIN_PREWARM_MAX_RAM_PCT:.0f}%")
    print(f"Voice prewarm free RAM    : {settings.VOICE_BRAIN_PREWARM_MIN_AVAILABLE_RAM_GB:.1f} GiB")

    bad = "Je vais m'y assurer d'être plus précis. Vous pourriez me aider avec ça."
    fixed = deterministic_french_fallback(bad)
    print("\nFrench integrity")
    print(f"  Avant : {bad}")
    print(f"  Après : {fixed}")
    print(f"  Risques restants : {len(find_voice_quality_issues(fixed))}")

    fake = FakeHTTP([
        {"results": [{"name": "Vidauban", "admin1": "Région PACA", "country": "France", "latitude": 43.43, "longitude": 6.43}]},
        {"current": {"temperature_2m": 33.1, "apparent_temperature": 33.2, "relative_humidity_2m": 38, "precipitation": 0.0, "weather_code": 0, "wind_speed_10m": 12.0}},
    ])
    result = WeatherTool(fake).execute("Vidauban")
    print("\nWeather dual rendering")
    print(f"  UI chars    : {len(result.response)}")
    print(f"  Voice chars : {len(result.speech_response)}")
    print(f"  Voice       : {result.speech_response}")

    contract = voice_output_contract(voice_brevity_policy("Bonjour Aura"))
    source = (Path(__file__).resolve().parents[1] / "core" / "aura_core.py").read_text(encoding="utf-8")
    checks = {
        "version": settings.APP_VERSION == "0.7.0.13",
        "xtts_5min": settings.RESOURCE_XTTS_IDLE_SECONDS >= 300,
        "prewarm_window": settings.VOICE_BRAIN_PREWARM_MAX_RAM_PCT >= 85,
        "french_fixed": "m'assurer" in fixed and "m'aider" in fixed and not find_voice_quality_issues(fixed),
        "weather_shorter": bool(result.speech_response) and len(result.speech_response) < len(result.response),
        "weather_under_220": len(result.speech_response) < 220,
        "voice_contract": "Français naturel obligatoire" in contract,
        "dynamic_banner": "{settings.APP_VERSION}" in source,
    }
    print("\nChecks")
    for name, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = all(checks.values())
    print("\n[PASS] Runtime/French hotfix prêt." if passed else "\n[FAIL] Vérifier les points ci-dessus.")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
