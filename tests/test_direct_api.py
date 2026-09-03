"""Unit tests for DirectApiTransport bypassing DataDome."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from tripadvisorintel.transports.direct_api import DirectApiTransport, CATEGORY_MAP
from tripadvisorintel.models import PlaceSummary, PlaceDetail, ReviewItem
from tripadvisorintel.client import TripAdvisorClient


class TestDirectApiTransport(unittest.TestCase):
    def setUp(self):
        self.transport = DirectApiTransport(api_key="test-key")

    @patch.object(DirectApiTransport, "_request_json")
    def test_search_places_parsing(self, mock_req):
        mock_req.return_value = {
            "data": [
                {
                    "result_type": "activities",
                    "result_object": {
                        "location_id": "5979069",
                        "name": "Monkey Island",
                        "rating": "3.4",
                        "num_reviews": "868",
                        "location_string": "Cat Ba, Vietnam",
                        "photo": {
                            "images": {
                                "thumbnail": {"url": "https://media-cdn.tripadvisor.com/thumb.jpg"}
                            }
                        },
                    },
                }
            ]
        }

        results = self.transport.search_places("Monkey Island", category="attractions")
        self.assertEqual(len(results), 1)
        p = results[0]
        self.assertEqual(p.place_id, "5979069")
        self.assertEqual(p.title, "Monkey Island")
        self.assertEqual(p.rating, 3.4)
        self.assertEqual(p.reviews, 868)
        self.assertEqual(p.thumbnail, "https://media-cdn.tripadvisor.com/thumb.jpg")
        mock_req.assert_called_once_with("typeahead", {"query": "Monkey Island", "category_type": "activities"})

    @patch.object(DirectApiTransport, "get_reviews")
    @patch.object(DirectApiTransport, "_request_json")
    def test_get_place_detail_parsing(self, mock_req, mock_reviews):
        mock_req.return_value = {
            "location_id": "5979069",
            "name": "Monkey Island Cat Ba",
            "subcategory_type_label": "attraction",
            "rating": "3.5",
            "num_reviews": "870",
            "ranking": "#8 of 60 things to do in Cat Ba",
            "ranking_position": "8",
            "ranking_denominator": "60",
            "address": "Lan Ha Bay, Cat Ba",
            "latitude": "20.72",
            "longitude": "107.07",
            "subratings": [
                {"name": "Cleanliness", "value": "3.0"},
                {"name": "Value", "value": "3.5"},
            ],
        }
        mock_reviews.return_value = ([], None)

        detail = self.transport.get_place_detail("5979069")
        self.assertEqual(detail.place_id, "5979069")
        self.assertEqual(detail.name, "Monkey Island Cat Ba")
        self.assertEqual(detail.rating, 3.5)
        self.assertEqual(detail.reviews, 870)
        self.assertEqual(detail.ranking_position, 8)
        self.assertEqual(detail.ranking_total, 60)
        self.assertEqual(len(detail.subratings), 2)
        self.assertEqual(detail.subratings[0].category, "Cleanliness")
        self.assertEqual(detail.subratings[0].score, 3.0)

    @patch.object(DirectApiTransport, "_request_json")
    def test_get_reviews_parsing(self, mock_req):
        mock_req.return_value = {
            "data": [
                {
                    "id": "1053183205",
                    "title": "Monkeys",
                    "text": "The monkeys are very aggressive and bite.",
                    "rating": "1.0",
                    "published_date": "2026-03-16T01:19:25-04:00",
                    "url": "https://www.tripadvisor.com/review1",
                    "lang": "en",
                    "helpful_votes": "3",
                    "user": {
                        "username": "traveler_dan",
                        "user_location": {"name": "Seattle, WA"},
                        "contributions": {"reviews": "14"},
                    },
                }
            ],
            "paging": {
                "next": "https://api.tripadvisor.com/api/internal/1.14/location/5979069/reviews?offset=20"
            },
        }

        reviews, next_token = self.transport.get_reviews("5979069", limit=20, offset=0)
        self.assertEqual(len(reviews), 1)
        r = reviews[0]
        self.assertEqual(r.review_id, "1053183205")
        self.assertEqual(r.title, "Monkeys")
        self.assertEqual(r.rating, 1.0)
        self.assertEqual(r.date, "2026-03-16")
        self.assertEqual(r.votes, 3)
        self.assertIsNotNone(r.author)
        self.assertEqual(r.author.username, "traveler_dan")
        self.assertEqual(r.author.hometown, "Seattle, WA")
        self.assertEqual(r.author.contributions, 14)
        self.assertIn("offset=20", next_token)

    def test_client_automatic_direct_api_fallback(self):
        failing_primary = MagicMock()
        failing_primary.search_places.side_effect = RuntimeError("403 Blocked by DataDome")

        fallback_direct = MagicMock()
        fallback_direct.search_places.return_value = [
            PlaceSummary(title="Recovered Place", place_id="123")
        ]

        client = TripAdvisorClient(
            transport=failing_primary,
            fallback_transport=fallback_direct,
        )

        res = client.search("test unique query direct api fallback", force_refresh=True)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].title, "Recovered Place")
        failing_primary.search_places.assert_called_once()
        fallback_direct.search_places.assert_called_once()


if __name__ == "__main__":
    unittest.main()
