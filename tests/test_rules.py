"""Unit tests for reasoning rules and metrics."""

import unittest
from tripadvisorintel.models import (
    PlaceDetail,
    Subrating,
    ReviewItem,
    ReviewDistribution,
    PriceRange,
)
from tripadvisorintel.reasoning.rules import (
    audit_value_discrepancy,
    scan_red_flags,
    calculate_rank_percentile,
    evaluate_persona_fits,
    generate_walk_in_brief,
)


class TestRules(unittest.TestCase):
    def test_value_discrepancy_luxury_surcharge(self):
        # Overall 4.8, Value 3.9 -> gap = 0.9 (Luxury Surcharge)
        place = PlaceDetail(
            place_id="1",
            name="Luxury Resort",
            rating=4.8,
            subratings=[
                Subrating(category="Cleanliness", score=4.9),
                Subrating(category="Value", score=3.9),
            ],
        )
        score, msg = audit_value_discrepancy(place)
        self.assertEqual(score, 0.9)
        self.assertIn("Luxury/Brand Surcharge", msg)

    def test_value_discrepancy_exceptional_value(self):
        # Overall 4.2, Value 4.8 -> gap = -0.6 (High Value)
        place = PlaceDetail(
            place_id="2",
            name="Bargain Lodge",
            rating=4.2,
            subratings=[
                Subrating(category="Value", score=4.8),
            ],
        )
        score, msg = audit_value_discrepancy(place)
        self.assertEqual(score, -0.6)
        self.assertIn("Exceptional Value", msg)

    def test_scan_red_flags(self):
        place = PlaceDetail(
            place_id="3",
            name="Problem Hotel",
            rating=3.8,
            reviews_list=[
                ReviewItem(
                    title="Horrible stay",
                    snippet="We found bed bugs in the bed and heard heavy construction noise from 6am.",
                    rating=1.0,
                ),
                ReviewItem(
                    title="Deposit rip off",
                    snippet="They kept deposit and accused us of breaking things. Total scam.",
                    rating=1.0,
                ),
            ],
            review_distribution=ReviewDistribution(
                star_5=50, star_4=20, star_3=10, star_2=10, star_1=10  # 20% negative!
            ),
        )
        flags = scan_red_flags(place)
        categories = {f.category for f in flags}
        self.assertIn("cleanliness", categories)
        self.assertIn("noise", categories)
        self.assertIn("scam_and_billing", categories)
        self.assertIn("reputation_drift", categories)

    def test_rank_percentile(self):
        place = PlaceDetail(
            place_id="4",
            name="Top Hotel",
            ranking_position=5,
            ranking_total=500,
        )
        pct, summary = calculate_rank_percentile(place)
        self.assertEqual(pct, 1.0)
        self.assertIn("Top 1.0%", summary)
        self.assertIn("Elite Tier", summary)

    def test_persona_fits(self):
        place = PlaceDetail(
            place_id="5",
            name="Central Nomad Oasis",
            rating=4.7,
            subratings=[
                Subrating(category="Location", score=4.9),
                Subrating(category="Cleanliness", score=4.8),
                Subrating(category="Service", score=4.8),
                Subrating(category="Value", score=4.6),
                Subrating(category="Sleep Quality", score=4.8),
            ],
            walk_score=95,
        )
        fits = evaluate_persona_fits(place)
        self.assertIn("solo_nomad", fits)
        self.assertIn("couples", fits)
        self.assertIn("family", fits)
        self.assertGreaterEqual(fits["solo_nomad"].score, 8.0)

    def test_adversarial_red_flags(self):
        """Verify capture of food poisoning, bait & switch, Wi-Fi outage, AC failure, and bribery."""
        place = PlaceDetail(
            place_id="6",
            name="Adversarial Trap Hotel",
            rating=4.5,
            reviews_list=[
                ReviewItem(
                    title="Ruined trip",
                    snippet="We got violent food poisoning from the buffet and aircon was broken blowing hot air.",
                    rating=1.0,
                ),
                ReviewItem(
                    title="Deceptive",
                    snippet="Total bait and switch! This was not the room pictured. Photos are fake.",
                    rating=1.0,
                ),
                ReviewItem(
                    title="Impossible to work",
                    snippet="The unusable Wi-Fi kept dropping every 2 minutes. No internet in rooms.",
                    rating=2.0,
                ),
                ReviewItem(
                    title="Suspicious",
                    snippet="Staff offered free drinks for a 5-star review at the front desk.",
                    rating=3.0,
                ),
            ],
        )
        flags = scan_red_flags(place)
        cat_map = {f.category: f for f in flags}
        self.assertIn("food_and_hygiene", cat_map)
        self.assertIn("infrastructure_failure", cat_map)
        self.assertIn("bait_and_switch", cat_map)
        self.assertIn("wifi_and_connectivity", cat_map)
        self.assertIn("review_manipulation", cat_map)

        # Test that persona penalties trigger properly
        fits = evaluate_persona_fits(place, red_flags=flags)
        # Nomad score should be penalized for wifi & infrastructure
        self.assertLessEqual(fits["solo_nomad"].score, 6.0)
        self.assertTrue(any("Work Disruption" in c for c in fits["solo_nomad"].cons))
        # Family score should be penalized for food poisoning
        self.assertTrue(any("Culinary Warning" in c for c in fits["family"].cons))


if __name__ == "__main__":
    unittest.main()
