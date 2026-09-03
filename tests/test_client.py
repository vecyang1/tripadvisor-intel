"""Unit tests for TripAdvisorClient using MockTransport."""

import tempfile
import unittest
from pathlib import Path
from tripadvisorintel.client import TripAdvisorClient
from tripadvisorintel.transports.mock import MockTransport
from tripadvisorintel.cache import CacheDB


class TestClient(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache = CacheDB(db_path=Path(self.temp_dir.name) / "test_client.db")
        self.transport = MockTransport()
        self.client = TripAdvisorClient(transport=self.transport, cache_instance=self.cache, enable_llm=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_client_search(self):
        results = self.client.search("Hoi An", category="hotels")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].place_id, "12345")

        # Cache check: verify next call hits cache without transport change
        self.transport.search_results = []
        cached_results = self.client.search("Hoi An", category="hotels")
        self.assertEqual(len(cached_results), 2)
        self.assertEqual(cached_results[0].place_id, "12345")

    def test_client_get_place(self):
        detail = self.client.get_place("12345")
        self.assertEqual(detail.name, "Mock Royal Heritage Hotel")
        self.assertEqual(detail.ranking_position, 3)

        # Test cache hit
        cached_detail = self.client.get_place("12345")
        self.assertEqual(cached_detail.name, "Mock Royal Heritage Hotel")

    def test_client_analyze_dossier(self):
        dossier = self.client.analyze("12345")
        self.assertEqual(dossier.place_id, "12345")
        self.assertEqual(dossier.name, "Mock Royal Heritage Hotel")
        self.assertIsNotNone(dossier.walk_in_brief)
        self.assertIn("solo_nomad", dossier.persona_fits)
        self.assertIn("couples", dossier.persona_fits)
        self.assertIn("family", dossier.persona_fits)

    def test_client_analyze_dossier_with_red_flags(self):
        # Create a mock place with severe red flags
        from tripadvisorintel.models import PlaceDetail, ReviewItem, ReviewDistribution, Subrating
        bad_place = PlaceDetail(
            place_id="999",
            name="Bedbug Motel",
            rating=2.5,
            subratings=[
                Subrating(category="Cleanliness", score=1.8),
                Subrating(category="Value", score=2.0),
            ],
            reviews_list=[
                ReviewItem(title="Nightmare", snippet="Bed bugs everywhere and loud club downstairs. Total scam.", rating=1.0)
            ],
            review_distribution=ReviewDistribution(star_5=5, star_4=5, star_3=10, star_2=30, star_1=50)
        )
        self.transport.place_detail = bad_place

        dossier = self.client.analyze("999", persona="family")
        self.assertGreater(len(dossier.red_flags), 0)
        categories = {rf.category for rf in dossier.red_flags}
        self.assertIn("cleanliness", categories)
        self.assertIn("reputation_drift", categories)
        # Verify family fit was heavily penalized
        self.assertLess(dossier.persona_fits["family"].score, 5.0)
        self.assertIn("Caution", dossier.persona_fits["family"].recommendation)

    def test_client_get_place_by_url(self):
        # Pass a full TripAdvisor URL
        url = "https://www.tripadvisor.com/Hotel_Review-g298082-d12345-Reviews-Mock_Royal_Hotel.html"
        detail = self.client.get_place(url)
        self.assertEqual(detail.place_id, "12345")
        self.assertEqual(detail.name, "Mock Royal Heritage Hotel")

    def test_client_reviews_pagination(self):
        # Default page 1: 2 reviews
        p1 = self.client.get_place("12345", reviews_pages=1)
        self.assertEqual(len(p1.reviews_list), 2)

        # Multi-page: page 2 appends coffee review
        p2 = self.client.get_place("12345", reviews_pages=2, force_refresh=True)
        self.assertEqual(len(p2.reviews_list), 3)
        self.assertIn("Good coffee", p2.reviews_list[-1].title)


if __name__ == "__main__":
    unittest.main()

