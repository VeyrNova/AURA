import json
import unittest
from unittest.mock import patch

from consciousness.self_model import CapabilityState, SelfModel
from grounding.manager import GroundedIntelligence
from security.permissions import Permission
from security.policy_engine import SecurityPolicyEngine
from tools.internet_manager import InternetToolManager
from tools.safe_http import SafeHTTPClient, SafeHTTPError, HTTPResponse
from tools.weather import WeatherTool
from tools.web_fetch import WebFetchTool
from tools.web_search import BraveSearchTool


class FakeHTTP:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.urls = []

    def get_json(self, url, headers=None):
        self.urls.append(url)
        payload = self.payloads.pop(0)
        return payload, HTTPResponse(url, 200, "application/json", json.dumps(payload).encode())

    def get(self, url, headers=None, allowed_types=()):
        self.urls.append(url)
        return HTTPResponse(url, 200, "text/html", b"<html><head><title>Test Page</title></head><body><h1>Hello</h1><p>Useful text.</p><script>ignore me</script></body></html>")


class InternetToolsV070Tests(unittest.TestCase):
    def test_weather_planner_requires_explicit_place_but_matches_weather(self):
        manager = InternetToolManager()
        plan = manager.plan("Quelle météo demain à Toulon ?")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "weather")
        self.assertEqual(plan.action, "WEB_WEATHER")
        self.assertEqual(plan.args["location"].lower(), "toulon")
        self.assertTrue(plan.args["tomorrow"])

    def test_weather_planner_does_not_hijack_cooking_temperature(self):
        manager = InternetToolManager()
        self.assertIsNone(manager.plan("Quelle température pour cuire un poulet ?"))

    def test_weather_planner_extracts_city_from_question_form(self):
        manager = InternetToolManager()
        plan = manager.plan("Quelle météo fait-il à Toulon ?")
        self.assertEqual(plan.args["location"].lower(), "toulon")

    def test_weather_planner_accepts_short_city_form(self):
        manager = InternetToolManager()
        plan = manager.plan("météo Toulon")
        self.assertEqual(plan.name, "weather")
        self.assertEqual(plan.args["location"].lower(), "toulon")

    def test_url_planner_prefers_explicit_fetch(self):
        manager = InternetToolManager()
        plan = manager.plan("Lis https://example.com/article")
        self.assertEqual(plan.name, "web_fetch")
        self.assertEqual(plan.args["url"], "https://example.com/article")

    def test_search_planner(self):
        manager = InternetToolManager()
        plan = manager.plan("cherche sur internet nouveautés Python")
        self.assertEqual(plan.name, "web_search")
        self.assertIn("nouveautés", plan.args["query"])

    def test_weather_formats_source_backed_current_conditions(self):
        fake = FakeHTTP([
            {"results": [{"name": "Toulon", "admin1": "Provence-Alpes-Côte d'Azur", "country": "France", "latitude": 43.12, "longitude": 5.93}]},
            {"current": {"temperature_2m": 25.2, "apparent_temperature": 26.1, "relative_humidity_2m": 55, "precipitation": 0.0, "weather_code": 1, "wind_speed_10m": 12.2}},
        ])
        result = WeatherTool(fake).execute("Toulon")
        self.assertTrue(result.ok)
        self.assertIn("25.2 °C", result.response)
        self.assertIn("Open-Meteo", result.response)
        self.assertEqual(result.source, "open-meteo")

    def test_weather_formats_tomorrow(self):
        fake = FakeHTTP([
            {"results": [{"name": "Toulon", "country": "France", "latitude": 43.12, "longitude": 5.93}]},
            {"daily": {"time": ["2026-08-08", "2026-08-09"], "weather_code": [1, 61], "temperature_2m_max": [30, 28], "temperature_2m_min": [21, 20], "precipitation_probability_max": [10, 70]}},
        ])
        result = WeatherTool(fake).execute("Toulon", tomorrow=True)
        self.assertTrue(result.ok)
        self.assertIn("Demain", result.response)
        self.assertIn("70%", result.response)

    def test_web_fetch_strips_scripts(self):
        result = WebFetchTool(FakeHTTP([])).execute("https://example.com")
        self.assertTrue(result.ok)
        self.assertIn("Useful text", result.response)
        self.assertNotIn("ignore me", result.response)

    def test_brave_without_key_fails_explicitly(self):
        result = BraveSearchTool(FakeHTTP([]), "").execute("AURA")
        self.assertFalse(result.ok)
        self.assertIn("clé Brave Search", result.response)

    def test_brave_results_are_source_labelled(self):
        fake = FakeHTTP([{"web": {"results": [{"title": "Official result", "url": "https://example.com/a", "description": "A useful result"}]}}])
        result = BraveSearchTool(fake, "secret").execute("test", count=1)
        self.assertTrue(result.ok)
        self.assertIn("example.com", result.response)
        self.assertEqual(result.sources[0].host, "example.com")

    def test_security_grants_read_only_web_actions(self):
        policy = SecurityPolicyEngine(db=None)
        for action in ("WEB_WEATHER", "WEB_FETCH", "WEB_SEARCH"):
            self.assertTrue(policy.authorize(action).allowed)
        self.assertIn(Permission.WEB_READ, policy.granted_permissions)
        self.assertNotIn(Permission.EXTERNAL_NETWORK, policy.granted_permissions)
        self.assertFalse(policy.authorize("SEND_EMAIL", user_confirmed=True).allowed)
        # Network permission does not make process/system actions available.
        self.assertFalse(policy.authorize("RUN_PROGRAM").allowed)

    def test_grounding_blocks_unsupported_live_categories_even_with_internet_capability(self):
        model = SelfModel(CapabilityState(internet=True))
        d = GroundedIntelligence().evaluate("Quel est le score du match ce soir ?", model)
        self.assertTrue(d.handled)
        self.assertEqual(d.category, "sports")

    def test_safe_http_rejects_localhost_literal(self):
        client = SafeHTTPClient()
        with self.assertRaises(SafeHTTPError):
            client.get("http://127.0.0.1/")

    def test_safe_http_rejects_hostname_resolving_private(self):
        client = SafeHTTPClient()
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("192.168.1.10", 80))]):
            with self.assertRaises(SafeHTTPError):
                client.get("http://example.test/")

    def test_safe_http_rejects_unsafe_scheme_userinfo_and_port(self):
        client = SafeHTTPClient()
        for url in ("file:///etc/passwd", "https://user:pass@example.com/", "https://example.com:8443/"):
            with self.subTest(url=url):
                with self.assertRaises(SafeHTTPError):
                    client.get(url)


if __name__ == "__main__":
    unittest.main()
