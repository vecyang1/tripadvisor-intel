"""Unit tests for SQLite caching in tripadvisorintel."""

import tempfile
import unittest
from pathlib import Path
from tripadvisorintel.cache import CacheDB


class TestCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cache.db"
        self.cache = CacheDB(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_search_cache(self):
        query = "Hoi An boutique"
        cat = "hotels"
        payload = [{"title": "Hotel A", "place_id": "123"}]

        # Miss
        self.assertIsNone(self.cache.get_search(query, cat))

        # Set and Hit
        self.cache.set_search(query, cat, payload)
        hit = self.cache.get_search(query, cat)
        self.assertIsNotNone(hit)
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["title"], "Hotel A")

    def test_place_cache(self):
        place_id = "98765"
        payload = {"name": "Seaside Villa", "place_id": place_id, "rating": 4.9}

        # Miss
        self.assertIsNone(self.cache.get_place(place_id))

        # Set and Hit
        self.cache.set_place(place_id, payload)
        hit = self.cache.get_place(place_id)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["name"], "Seaside Villa")

    def test_report_cache(self):
        place_id = "98765"
        persona = "solo_nomad"
        payload = {"place_id": place_id, "walk_in_brief": "Great spot for laptop work."}

        self.assertIsNone(self.cache.get_report(place_id, persona))
        self.cache.set_report(place_id, persona, payload)
        hit = self.cache.get_report(place_id, persona)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["walk_in_brief"], "Great spot for laptop work.")

    def test_cache_stats_and_clear(self):
        self.cache.set_search("q1", "hotels", [{"place_id": "1"}])
        self.cache.set_place("1", {"name": "P1"})
        stats = self.cache.stats()
        self.assertEqual(stats["searches_count"], 1)
        self.assertEqual(stats["places_count"], 1)

        self.cache.clear()
        stats_cleared = self.cache.stats()
        self.assertEqual(stats_cleared["searches_count"], 0)
        self.assertEqual(stats_cleared["places_count"], 0)


if __name__ == "__main__":
    unittest.main()
