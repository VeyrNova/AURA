import tempfile
import unittest
from pathlib import Path

from voice.voice_audition import VoiceAuditionStore, VoiceRating


class VoiceAuditionTests(unittest.TestCase):
    def test_rating_is_bounded(self):
        rating = VoiceRating("Test", naturality=9, warmth=-2, sensuality=3, preference=5).normalized()
        self.assertEqual(rating.naturality, 5)
        self.assertEqual(rating.warmth, 0)
        self.assertEqual(rating.sensuality, 3)
        self.assertEqual(rating.preference, 5)

    def test_score_weights_preference(self):
        a = VoiceRating("A", naturality=5, warmth=5, sensuality=5, preference=1)
        b = VoiceRating("B", naturality=4, warmth=4, sensuality=4, preference=5)
        self.assertGreater(b.score, a.score)

    def test_store_round_trip_and_csv_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = VoiceAuditionStore(base / "ratings.json")
            store.save_rating(VoiceRating("Claribel Dervla", 5, 4, 4, 5, True, "Très bien"))
            loaded = store.load()
            self.assertIn("Claribel Dervla", loaded)
            self.assertTrue(loaded["Claribel Dervla"].favorite)
            csv_path = store.export_csv(base / "ranking.csv")
            self.assertTrue(csv_path.is_file())
            content = csv_path.read_text(encoding="utf-8-sig")
            self.assertIn("Claribel Dervla", content)


if __name__ == "__main__":
    unittest.main()
