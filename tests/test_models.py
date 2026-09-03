"""Unit tests for models in tripadvisorintel."""

import unittest
from tripadvisorintel.models import (
    PlaceSummary,
    PlaceDetail,
    ReviewDistribution,
    Subrating,
    PriceRange,
    ReviewItem,
    HighlightedReview,
)


class TestModels(unittest.TestCase):
    def test_place_summary(self):
        p = PlaceSummary(
            position=1,
            title="Luxury Resort",
            place_id="99999",
            rating=4.5,
            reviews=320,
            location="Da Nang, Vietnam",
            highlighted_review=HighlightedReview(
                text="Great beachfront view.",
                highlighted_texts=["beachfront view"],
                mention_count=42,
            ),
        )
        self.assertEqual(p.position, 1)
        self.assertEqual(p.title, "Luxury Resort")
        self.assertEqual(p.reviews, 320)
        self.assertIsNotNone(p.highlighted_review)
        self.assertEqual(p.highlighted_review.mention_count, 42)

    def test_review_distribution_negative_ratio(self):
        dist = ReviewDistribution(
            star_5=80, star_4=10, star_3=5, star_2=3, star_1=2
        )
        self.assertEqual(dist.total, 100)
        self.assertAlmostEqual(dist.negative_ratio, 0.05)

        empty_dist = ReviewDistribution()
        self.assertEqual(empty_dist.total, 0)
        self.assertEqual(empty_dist.negative_ratio, 0.0)

    def test_place_detail_defaults(self):
        pd = PlaceDetail(
            place_id="111",
            name="City Boutique Hotel",
        )
        self.assertEqual(pd.place_id, "111")
        self.assertEqual(pd.name, "City Boutique Hotel")
        self.assertEqual(pd.rating, 0.0)
        self.assertEqual(pd.reviews, 0)
        self.assertEqual(len(pd.subratings), 0)
        self.assertEqual(len(pd.amenities), 0)


if __name__ == "__main__":
    unittest.main()
