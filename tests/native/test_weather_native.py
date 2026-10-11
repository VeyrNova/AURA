import tempfile
import time
import unittest
from pathlib import Path

from aura_native.agent.provider import FakeProvider
from aura_native.agent.service import AgentService
from aura_native.core.bus import LocalBus
from aura_native.core.contracts import Command
from aura_native.storage.conversation_repository import ConversationRepository
from aura_native.storage.database import NativeDatabase
from aura_native.tools.registry import ToolDefinition, ToolRegistry
from aura_native.tools.router import ToolRouter
from aura_native.tools.weather_tool import WeatherTool
from aura_native.weather.provider import FakeWeatherProvider, WeatherProviderError
from aura_native.weather.service import WeatherService, condition_for


class WeatherNativeTests(unittest.TestCase):
    def setUp(self):
        self.provider=FakeWeatherProvider(); self.service=WeatherService(self.provider); self.tool=WeatherTool(self.service)

    def test_geocode_current_daily_and_units(self):
        report=self.service.get_forecast("Nice", 2)
        self.assertEqual(report.location.label, "Nice, France"); self.assertEqual(report.current.condition, "partly_cloudy")
        self.assertEqual(report.daily[1].condition, "rain"); self.assertEqual(report.as_payload()["units"]["temperature"], "celsius")

    def test_location_not_found_timeout_network_and_invalid_response(self):
        invalid={"current":{"temperature_2m":"bad"},"daily":{}}
        for provider, code in ((FakeWeatherProvider(geocode_payload={}), "weather_location_not_found"), (FakeWeatherProvider(failure=WeatherProviderError("weather_timeout", "x")), "weather_timeout"), (FakeWeatherProvider(failure=WeatherProviderError("weather_network_error", "x")), "weather_network_error"), (FakeWeatherProvider(forecast_payload=invalid), "weather_invalid_response")):
            with self.assertRaises(WeatherProviderError) as caught: WeatherService(provider).get_forecast("Nice")
            self.assertEqual(caught.exception.code, code)

    def test_cache_and_code_mapping(self):
        self.service.get_forecast("Nice"); self.service.get_forecast("Nice")
        self.assertEqual([row[0] for row in self.provider.calls].count("forecast"), 1)
        self.assertEqual(condition_for(95), "thunderstorm"); self.assertEqual(condition_for(999), "unknown")

    def test_registry_tool_validation_and_structured_result(self):
        registry=ToolRegistry(); registry.register(ToolDefinition(self.tool.name,"weather",{},"weather",self.tool))
        self.assertFalse(registry.execute(self.tool.name,{})["ok"])
        result=registry.execute(self.tool.name,{"location":"Nice","date":"2026-09-29"})
        self.assertTrue(result["ok"]); self.assertEqual(result["data"]["selected_day"]["date"], "2026-09-29")

    def test_router_routes_weather_and_ignores_non_weather(self):
        registry=ToolRegistry(); registry.register(ToolDefinition(self.tool.name,"weather",{},"weather",self.tool)); router=ToolRouter(registry)
        self.assertIsNone(router.route("Donne-moi une idée de film"))
        routed=router.route("Quel temps fera-t-il demain à Nice ?")
        self.assertEqual(routed["name"], "weather.get_forecast"); self.assertEqual(routed["payload"]["location"], "Nice")
        self.assertTrue(router.execute_for("Faut-il prendre un parapluie demain à Lyon ?")["ok"])


class AgentWeatherIntegrationTests(unittest.TestCase):
    def test_tool_result_is_injected_before_provider_message(self):
        with tempfile.TemporaryDirectory(prefix="aura-weather-agent-") as directory:
            database=NativeDatabase(Path(directory)/"aura.db"); conversation=ConversationRepository(database)
            provider=FakeProvider("Réponse basée sur la météo")
            weather=WeatherTool(WeatherService(FakeWeatherProvider()))
            registry=ToolRegistry(); registry.register(ToolDefinition(weather.name,"weather",{},"weather",weather))
            service=AgentService(Path(directory)/"aura.db",provider=provider,tool_router=ToolRouter(registry)); bus=LocalBus(); service.bind(bus)
            convo=conversation.create("native"); message=conversation.add_message(convo.conversation_id,"native","user","Quel temps fera-t-il demain à Nice ?","test")
            completed=[]; bus.subscribe(completed.append,name="agent.completed")
            bus.submit(Command(name="agent.submit",payload={"text":message.content,"conversation_id":convo.conversation_id,"user_message_id":message.message_id},session_id="native",source="test")); bus.drain()
            for _ in range(50):
                bus.drain()
                if provider.calls and completed: break
                time.sleep(.01)
            messages=provider.calls[-1]
            self.assertIn("<tool_result>", messages[-2]["content"]); self.assertIn('"source": "open-meteo"', messages[-2]["content"])
            self.assertEqual(messages[-1]["content"], message.content)
            service.stop()
