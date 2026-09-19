from __future__ import annotations

from regression_compat import assert_version_at_least
import queue
import threading
import time
import unittest
from types import SimpleNamespace

from config.settings import settings
from tools.internet_manager import InternetToolManager
from tools.search_intent import (
    extract_explicit_search_query,
    is_explicit_search_request,
    is_visual_request,
    requested_result_count,
)
from tools.web_search import BraveSearchTool
from ui.response_presentation import for_llm_reply, for_tool_result, for_user_request
from voice.realtime_pipeline import run_realtime_audio_pipeline


class V070152SearchAndVisualTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_recherche_moi_routes_as_explicit_search(self):
        text = "Aura, recherche-moi 5 destinations intéressantes à visiter autour de Nice avec les avantages de chacune."
        self.assertTrue(is_explicit_search_request(text))
        self.assertTrue(is_visual_request(text))
        self.assertEqual(requested_result_count(text, default=4), 5)
        query = extract_explicit_search_query(text)
        self.assertIsNotNone(query)
        self.assertTrue(query.startswith("5 destinations"))

    def test_spaced_cherche_moi_is_supported(self):
        self.assertEqual(extract_explicit_search_query("cherche moi 3 hôtels à Nice"), "3 hôtels à Nice")

    def test_internet_planner_preserves_requested_count(self):
        manager = InternetToolManager()
        plan = manager.plan("Aura, recherche-moi 5 destinations autour de Nice")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")
        self.assertEqual(plan.args["count"], 5)

    def test_visual_handoff_is_intent_driven_not_length_driven(self):
        request = "recherche-moi 5 destinations autour de Nice"
        self.assertTrue(for_user_request(request).visual)
        # Reproduces the 308-char reply that failed to open the panel in the log.
        decision = for_llm_reply("x" * 308, request)
        self.assertTrue(decision.visual)

    def test_failed_explicit_web_search_still_opens_diagnostic_panel(self):
        plan = SimpleNamespace(args={"query": "5 destinations autour de Nice"})
        result = SimpleNamespace(ok=False, category="web_search", response="provider missing", source="provider_not_configured")
        decision = for_tool_result(result, plan)
        self.assertTrue(decision.visual)
        self.assertIn("INDISPONIBLE", decision.title)


class _FakeHTTPClient:
    def get_json(self, url, headers=None):
        results = [
            {"title": f"Destination {i}", "url": f"https://example{i}..test/place", "description": f"Description {i}"}
            for i in range(1, 6)
        ]
        return {"web": {"results": results}}, SimpleNamespace()


class V070152CompleteSearchTests(unittest.TestCase):
    def test_search_tracks_completeness_contract(self):
        tool = BraveSearchTool(_FakeHTTPClient(), "test-key")
        result = tool.execute("destinations autour de Nice", count=5)
        self.assertTrue(result.ok)
        self.assertEqual(result.item_count, 5)
        self.assertEqual(result.expected_items, 5)
        self.assertTrue(result.complete)
        self.assertEqual(len(result.sources), 5)


class _Prepared:
    def __init__(self, index: int):
        self.index = index
        self.synthesis_seconds = 0.04
        self.prepared_at = time.perf_counter()


class _FakeRealtimeSession:
    def __init__(self):
        self.lock = threading.Lock()
        self.synth_starts = {}
        self.synth_ends = {}
        self.play_starts = {}
        self.play_ends = {}

    def synthesize(self, text: str, *, index: int):
        with self.lock:
            self.synth_starts[index] = time.perf_counter()
        time.sleep(0.04)
        prepared = _Prepared(index)
        with self.lock:
            self.synth_ends[index] = time.perf_counter()
        return prepared

    def play(self, prepared):
        idx = prepared.index
        with self.lock:
            self.play_starts[idx] = time.perf_counter()
        time.sleep(0.12)
        with self.lock:
            self.play_ends[idx] = time.perf_counter()
        return 0.12


class V070152RealtimePipelineTests(unittest.TestCase):
    def test_synthesis_n_plus_one_overlaps_playback_n(self):
        sentences = queue.Queue()
        now = time.perf_counter()
        sentences.put(("Phrase une.", now))
        sentences.put(("Phrase deux.", now))
        sentences.put(None)
        session = _FakeRealtimeSession()
        played = run_realtime_audio_pipeline(
            sentences,
            session,
            threading.Event(),
            audio_queue_size=2,
        )
        self.assertEqual(played, 2)
        # This is the defining property missing from v0.7.0.15.1.
        self.assertLess(session.synth_starts[1], session.play_ends[0])
        self.assertLess(session.play_starts[0], session.synth_ends[1])


if __name__ == "__main__":
    unittest.main()
