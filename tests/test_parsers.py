"""Unit tests for parsers in tripadvisorintel."""

import unittest
from tripadvisorintel.parsers import (
    parse_ranking_string,
    parse_review_distribution,
    parse_search_results,
    parse_place_details,
)


class TestParsers(unittest.TestCase):
    def test_parse_ranking_string(self):
        # 1. Standard hotel ranking
        pos, total, cat, loc = parse_ranking_string("#45 of 466 hotels in Hoi An")
        self.assertEqual(pos, 45)
        self.assertEqual(total, 466)
        self.assertEqual(cat.lower(), "hotels")
        self.assertEqual(loc, "Hoi An")

        # 2. Large numbers with commas
        pos, total, cat, loc = parse_ranking_string("#1 of 2,104 restaurants in Tokyo")
        self.assertEqual(pos, 1)
        self.assertEqual(total, 2104)
        self.assertEqual(cat.lower(), "restaurants")
        self.assertEqual(loc, "Tokyo")

        # 3. Bare of (#45 of 466)
        pos, total, cat, loc = parse_ranking_string("#45 of 466")
        self.assertEqual(pos, 45)
        self.assertEqual(total, 466)

        # 4. Regional: Vietnamese (#1 trong số 466 khách sạn tại Hội An)
        pos, total, cat, loc = parse_ranking_string("#1 trong số 466 khách sạn tại Hội An")
        self.assertEqual(pos, 1)
        self.assertEqual(total, 466)
        self.assertIn("khách sạn", cat)
        self.assertIn("Hội An", loc)

        # 5. Regional: French (#12 sur 150 restaurants à Paris)
        pos, total, cat, loc = parse_ranking_string("#12 sur 150 restaurants à Paris")
        self.assertEqual(pos, 12)
        self.assertEqual(total, 150)

        # 6. Regional: Chinese
        pos, total, cat, loc = parse_ranking_string("466家酒店中排名第45")
        self.assertEqual(pos, 45)
        self.assertEqual(total, 466)

        # 7. Invalid or empty
        pos, total, cat, loc = parse_ranking_string(None)
        self.assertIsNone(pos)
        self.assertIsNone(total)

    def test_extract_place_id(self):
        from tripadvisorintel.parsers import extract_place_id
        # Pure numeric
        self.assertEqual(extract_place_id("7182682"), "7182682")
        # 'd' prefix
        self.assertEqual(extract_place_id("d7182682"), "7182682")
        # Full TripAdvisor hotel URL
        url1 = "https://www.tripadvisor.com/Hotel_Review-g298082-d7182682-Reviews-Hotel_Royal_Hoi_An.html"
        self.assertEqual(extract_place_id(url1), "7182682")
        # Restaurant URL
        url2 = "https://www.tripadvisor.com/Restaurant_Review-g298082-d1121828-Reviews-Mango_Rooms-Hoi_An.html"
        self.assertEqual(extract_place_id(url2), "1121828")
        # Query parameter
        url3 = "https://www.tripadvisor.com/place_info?place_id=4507121&ref=tripadvisor"
        self.assertEqual(extract_place_id(url3), "4507121")
        # Search query string should return None
        self.assertIsNone(extract_place_id("Mango Rooms Hoi An Vietnam"))

    def test_safe_parsers(self):
        from tripadvisorintel.parsers import safe_float, safe_int
        self.assertEqual(safe_float("bubble_45"), 4.5)
        self.assertEqual(safe_float("bubble_50"), 5.0)
        self.assertEqual(safe_float("4.5 of 5 stars"), 4.5)
        self.assertEqual(safe_float("4,8"), 4.8)
        self.assertEqual(safe_int("1,250"), 1250)
        self.assertIsNone(safe_float(None))
        self.assertIsNone(safe_int(None))

    def test_audit_review_authenticity(self):
        from tripadvisorintel.parsers import audit_review_authenticity
        from tripadvisorintel.models import PlaceDetail, ReviewItem, ReviewAuthor, ReviewDistribution, Subrating

        # Authentic place
        auth_place = PlaceDetail(
            place_id="1",
            name="Authentic Hotel",
            rating=4.8,
            subratings=[Subrating(category="Cleanliness", score=4.8)],
            review_distribution=ReviewDistribution(star_5=80, star_4=15, star_3=3, star_2=1, star_1=1),
            reviews_list=[
                ReviewItem(snippet="Great", rating=5.0, author=ReviewAuthor(contributions=30)),
                ReviewItem(snippet="Lovely", rating=5.0, author=ReviewAuthor(contributions=15)),
                ReviewItem(snippet="Nice", rating=5.0, author=ReviewAuthor(contributions=45)),
            ]
        )
        score, verdict = audit_review_authenticity(auth_place)
        self.assertGreaterEqual(score, 9.0)
        self.assertIn("High Organic Authenticity", verdict)

        # Astroturfed place: 100% 5★ reviews from 0-1 contribution accounts + polarized distribution
        fake_place = PlaceDetail(
            place_id="2",
            name="Suspicious Hotel",
            rating=4.9,
            subratings=[Subrating(category="Cleanliness", score=3.5)],
            review_distribution=ReviewDistribution(star_5=85, star_4=1, star_3=0, star_2=0, star_1=14),
            reviews_list=[
                ReviewItem(snippet="Best hotel ever", rating=5.0, author=ReviewAuthor(contributions=1)),
                ReviewItem(snippet="Incredible", rating=5.0, author=ReviewAuthor(contributions=1)),
                ReviewItem(snippet="Amazing", rating=5.0, author=ReviewAuthor(contributions=0)),
            ]
        )
        score_fake, verdict_fake = audit_review_authenticity(fake_place)
        self.assertLess(score_fake, 6.5)
        self.assertIn("Authenticity Risk", verdict_fake)

    def test_parse_review_distribution_list(self):
        raw = [
            {"rating": "Excellent", "count": 100},
            {"rating": "Very Good", "count": 50},
            {"rating": "Average", "count": 20},
            {"rating": "Poor", "count": 5},
            {"rating": "Terrible", "count": 2},
        ]
        dist = parse_review_distribution(raw)
        self.assertIsNotNone(dist)
        self.assertEqual(dist.star_5, 100)
        self.assertEqual(dist.star_4, 50)
        self.assertEqual(dist.star_3, 20)
        self.assertEqual(dist.star_2, 5)
        self.assertEqual(dist.star_1, 2)
        self.assertEqual(dist.total, 177)

    def test_parse_review_distribution_dict(self):
        raw = {"5": 500, "4": 100, "3": 30, "2": 10, "1": 5}
        dist = parse_review_distribution(raw)
        self.assertIsNotNone(dist)
        self.assertEqual(dist.star_5, 500)
        self.assertEqual(dist.star_1, 5)

    def test_parse_search_results(self):
        payload = {
            "places": [
                {
                    "position": 1,
                    "title": "Old Town Homestay",
                    "place_id": "88888",
                    "rating": 4.9,
                    "reviews": 350,
                    "location": "Hoi An",
                    "highlighted_review": {
                        "text": "Best host in Vietnam",
                        "highlighted_texts": ["Best host"],
                        "mention_count": 15,
                    },
                }
            ]
        }
        results = parse_search_results(payload)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.title, "Old Town Homestay")
        self.assertEqual(r.place_id, "88888")
        self.assertEqual(r.rating, 4.9)
        self.assertEqual(r.reviews, 350)
        self.assertEqual(r.highlighted_review.mention_count, 15)

    def test_parse_place_details(self):
        payload = {
            "place_result": {
                "name": "Grand Palace Da Nang",
                "type": "HOTEL",
                "rating": 4.6,
                "reviews": 1250,
                "ranking": "#5 of 320 hotels in Da Nang",
                "price_range": {"low": 75.0, "high": 150.0, "currency": "USD"},
                "subratings": [
                    {"category": "Location", "score": 4.8},
                    {"category": "Cleanliness", "score": 4.9},
                    {"category": "Service", "score": 4.7},
                    {"category": "Value", "score": 4.3},
                ],
                "walk_score": 92,
                "reviews_list": [
                    {
                        "title": "Wonderful pool",
                        "snippet": "The infinity pool has great sunset views.",
                        "rating": 5.0,
                        "date": "2026-08-01",
                        "author": {"username": "Sunshine77", "contributions": 23},
                    }
                ],
            }
        }
        pd = parse_place_details(payload, place_id="555")
        self.assertEqual(pd.name, "Grand Palace Da Nang")
        self.assertEqual(pd.place_id, "555")
        self.assertEqual(pd.ranking_position, 5)
        self.assertEqual(pd.ranking_total, 320)
        self.assertEqual(pd.walk_score, 92)
        self.assertEqual(len(pd.subratings), 4)
        self.assertEqual(len(pd.reviews_list), 1)
        self.assertEqual(pd.reviews_list[0].author.username, "Sunshine77")


if __name__ == "__main__":
    unittest.main()
