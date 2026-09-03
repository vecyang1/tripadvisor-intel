"""Unit tests for review pagination, parsing, and SQLite caching."""

import tempfile
import unittest
from pathlib import Path
from tripadvisorintel.models import ReviewItem, ReviewAuthor
from tripadvisorintel.parsers import parse_review_item, parse_reviews_response
from tripadvisorintel.cache import CacheDB
from tripadvisorintel.transports.mock import MockTransport
from tripadvisorintel.client import TripAdvisorClient


class TestReviews(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_revs.db"
        self.cache = CacheDB(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_review_item(self):
        raw = {
            "review_id": "1001",
            "title": "Unforgettable stay",
            "snippet": "The breakfast by the river was divine.",
            "rating": 5,
            "date": "2026-08-10",
            "link": "https://tripadvisor.com/review/1001",
            "trip_info": {"type": "COUPLES"},
            "votes": 3,
            "author": {
                "username": "TravelerJane",
                "contributions": 42,
                "hometown": "Melbourne, Australia",
            },
        }
        item = parse_review_item(raw)
        self.assertEqual(item.review_id, "1001")
        self.assertEqual(item.title, "Unforgettable stay")
        self.assertEqual(item.rating, 5.0)
        self.assertEqual(item.trip_type, "COUPLES")
        self.assertEqual(item.votes, 3)
        self.assertIsNotNone(item.author)
        self.assertEqual(item.author.username, "TravelerJane")
        self.assertEqual(item.author.contributions, 42)

    def test_parse_reviews_response(self):
        payload = {
            "reviews": [
                {"review_id": "r1", "title": "Good", "snippet": "Very nice", "rating": 4},
                {"review_id": "r2", "title": "Great", "snippet": "Awesome stay", "rating": 5},
            ],
            "serpapi_pagination": {
                "next": "https://serpapi.com/search.json?engine=tripadvisor_reviews&offset=20"
            },
        }
        items, next_url = parse_reviews_response(payload)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].review_id, "r1")
        self.assertIn("offset=20", next_url)

    def test_cache_reviews_crud(self):
        items = [
            {"review_id": "101", "rating": 5.0, "title": "T1", "snippet": "S1", "date": "2026-08-01"},
            {"review_id": "102", "rating": 4.0, "title": "T2", "snippet": "S2", "date": "2026-08-02"},
        ]
        inserted = self.cache.save_reviews("place_A", items)
        self.assertEqual(inserted, 2)
        self.assertEqual(self.cache.count_reviews("place_A"), 2)

        # Retrieve
        fetched = self.cache.get_reviews("place_A")
        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]["review_id"], "102")  # Ordered by date DESC

        # Re-saving same items should be idempotent
        self.cache.save_reviews("place_A", items)
        self.assertEqual(self.cache.count_reviews("place_A"), 2)

    def test_client_paginated_reviews_and_caching(self):
        transport = MockTransport()
        client = TripAdvisorClient(transport=transport, cache_instance=self.cache, enable_llm=False)

        # Request 40 reviews (MockTransport generates up to 100)
        revs = client.get_reviews(place_id="12345", max_reviews=40, page_size=20)
        self.assertGreaterEqual(len(revs), 2)
        self.assertEqual(self.cache.count_reviews("12345"), len(revs))

        # Second call should serve from SQLite cache with zero transport calls
        revs_cached = client.get_reviews(place_id="12345", max_reviews=len(revs))
        self.assertEqual(len(revs_cached), len(revs))


if __name__ == "__main__":
    unittest.main()
