"""Live End-to-End integration tests against real TripAdvisor endpoints."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tripadvisorintel.client import TripAdvisorClient
from tripadvisorintel.config import serpapi_api_key


class TestLiveE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api_key = serpapi_api_key()
        if not cls.api_key:
            raise unittest.SkipTest("SERPAPI_API_KEY not found; skipping live E2E tests.")
        cls.client = TripAdvisorClient()

    def test_live_search_and_ranking_integrity(self):
        """Verify that live search returns valid places with real TripAdvisor IDs."""
        places = self.client.search("Hoi An", category="hotels", limit=3, force_refresh=True)
        self.assertGreaterEqual(len(places), 1)
        first = places[0]
        self.assertTrue(first.place_id.isdigit(), f"Expected numeric place_id, got {first.place_id}")
        self.assertGreater(first.rating, 3.0)
        self.assertGreater(first.reviews, 100)

    def test_live_place_details_contract(self):
        """Verify that live place details match real page fields."""
        # Using a stable famous property: Hotel Royal Hoi An Danang (7182682)
        detail = self.client.get_place("7182682", force_refresh=True)
        self.assertEqual(detail.place_id, "7182682")
        self.assertIn("Hoi An", detail.name)
        self.assertIsNotNone(detail.ranking)
        self.assertIsNotNone(detail.ranking_position)
        self.assertGreater(detail.ranking_total, 100)
        self.assertGreaterEqual(len(detail.subratings), 4)

        # Check subratings presence
        cat_names = [sr.category.lower() for sr in detail.subratings]
        self.assertTrue(any("cleanliness" in c for c in cat_names))
        self.assertTrue(any("value" in c for c in cat_names))

        # Check review list
        self.assertGreaterEqual(len(detail.reviews_list), 5)
        self.assertIsNotNone(detail.reviews_list[0].snippet)

    def test_live_reasoning_dossier_generation(self):
        """Verify that live reasoning produces valid walk-in brief and persona scores."""
        dossier = self.client.analyze("7182682", force_refresh=True)
        self.assertEqual(dossier.place_id, "7182682")
        self.assertIsNotNone(dossier.walk_in_brief)
        self.assertIn("solo_nomad", dossier.persona_fits)
        self.assertGreaterEqual(dossier.persona_fits["solo_nomad"].score, 7.0)
        self.assertGreater(dossier.source_coverage.get("confidence", 0.0), 0.7)
        self.assertIsNotNone(dossier.authenticity_score)
        self.assertGreaterEqual(dossier.authenticity_score, 7.0)

    def test_live_url_resolution(self):
        """Verify that passing a full TripAdvisor web URL directly resolves and parses correctly."""
        url = "https://www.tripadvisor.com/Hotel_Review-g298082-d7182682-Reviews-Hotel_Royal_Hoi_An_MGallery-Hoi_An_Quang_Nam_Province.html"
        detail = self.client.get_place(url)
        self.assertEqual(detail.place_id, "7182682")
        self.assertIn("Hotel Royal", detail.name)

    def test_live_restaurant_dossier(self):
        """Verify live analysis for a restaurant (Mango Rooms Hoi An - 1121828)."""
        dossier = self.client.analyze("1121828", category="restaurants")
        self.assertEqual(dossier.place_id, "1121828")
        self.assertIn("Mango", dossier.name)
        self.assertGreater(dossier.rating, 4.0)
        self.assertIsNotNone(dossier.authenticity_score)

    def test_live_reviews_pagination_and_storage(self):
        """Verify live paginated review fetching and SQLite caching on real property."""
        reviews = self.client.get_reviews("7182682", max_reviews=20)
        self.assertGreaterEqual(len(reviews), 5)
        first = reviews[0]
        self.assertIsNotNone(first.snippet)
        self.assertGreater(first.rating, 0.0)

        # Verify SQLite cache
        cached = self.client.cache.get_reviews("7182682", limit=20)
        self.assertGreaterEqual(len(cached), len(reviews))


if __name__ == "__main__":
    unittest.main()
