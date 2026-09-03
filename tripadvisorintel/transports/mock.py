"""Mock transport for unit tests and offline evaluation."""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
from .base import BaseTransport
from ..models import (
    PlaceSummary,
    PlaceDetail,
    Subrating,
    PriceRange,
    ReviewDistribution,
    ReviewItem,
    ReviewAuthor,
)


class MockTransport(BaseTransport):
    def __init__(self, search_results: Optional[List[PlaceSummary]] = None, place_detail: Optional[PlaceDetail] = None):
        self.search_results = search_results or [
            PlaceSummary(
                position=1,
                title="Mock Royal Heritage Hotel",
                place_id="12345",
                place_type="ACCOMMODATION",
                rating=4.8,
                reviews=1500,
                location="Hoi An, Vietnam",
            ),
            PlaceSummary(
                position=2,
                title="Mock Riverside Resort",
                place_id="67890",
                place_type="ACCOMMODATION",
                rating=4.2,
                reviews=800,
                location="Hoi An, Vietnam",
            ),
        ]
        self.place_detail = place_detail or PlaceDetail(
            place_id="12345",
            name="Mock Royal Heritage Hotel",
            place_type="ACCOMMODATION",
            rating=4.8,
            reviews=1500,
            ranking="#3 of 450 hotels in Hoi An",
            ranking_position=3,
            ranking_total=450,
            ranking_category="hotels",
            ranking_location="Hoi An",
            price_range=PriceRange(low=85.0, high=160.0, currency="USD"),
            subratings=[
                Subrating(category="Location", score=4.9),
                Subrating(category="Cleanliness", score=4.8),
                Subrating(category="Service", score=4.9),
                Subrating(category="Value", score=4.1),
            ],
            review_distribution=ReviewDistribution(
                star_5=1200, star_4=220, star_3=50, star_2=20, star_1=10
            ),
            reviews_list=[
                ReviewItem(
                    title="Exceptional stay near the old town",
                    snippet="Loved the pool and breakfast. Great quiet work desk in room. Aircon cold and quiet.",
                    rating=5.0,
                    date="2026-08-15",
                    author=ReviewAuthor(username="TravelerNomad", hometown="London, UK", contributions=45),
                ),
                ReviewItem(
                    title="A bit pricey for laundry",
                    snippet="Hotel is lovely but laundry prices are 5x street rates. Noise from pool in evening.",
                    rating=3.0,
                    date="2026-08-10",
                    author=ReviewAuthor(username="BudgetScout", hometown="Sydney, Australia", contributions=12),
                ),
            ],
        )

    def search_places(
        self,
        query: str,
        category: str = "all",
        domain: str = "www.tripadvisor.com",
        limit: int = 30,
    ) -> List[PlaceSummary]:
        return self.search_results[:limit]

    def get_place_detail(
        self,
        place_id: str,
        domain: str = "www.tripadvisor.com",
        reviews_pages: int = 1,
    ) -> PlaceDetail:
        res = self.place_detail.model_copy(deep=True)
        if reviews_pages > 1:
            res.reviews_list.append(
                ReviewItem(
                    title="Page 2 Review - Good coffee",
                    snippet="Breakfast buffet had great Vietnamese iced coffee.",
                    rating=4.5,
                    date="2026-08-05",
                    author=ReviewAuthor(username="CoffeeLover", contributions=18),
                )
            )
        return res

    def get_reviews(
        self,
        place_id: str,
        limit: int = 20,
        offset: int = 0,
        domain: str = "www.tripadvisor.com",
    ) -> Tuple[List[ReviewItem], Optional[str]]:
        total_available = 100
        if offset >= total_available:
            return [], None

        batch_count = min(limit, total_available - offset)
        page: List[ReviewItem] = []
        for idx in range(offset, offset + batch_count):
            if idx < len(self.place_detail.reviews_list):
                item = self.place_detail.reviews_list[idx].model_copy(deep=True)
                if not item.review_id:
                    item.review_id = f"rev_{idx}"
                page.append(item)
            else:
                page.append(
                    ReviewItem(
                        review_id=f"rev_{idx}",
                        title=f"Simulated Review {idx}",
                        snippet=f"Snippet content for review {idx}",
                        rating=4.0,
                        date="2026-07-01",
                        author=ReviewAuthor(username=f"user_{idx}", contributions=idx),
                    )
                )
        has_next = (offset + batch_count) < total_available
        next_token = f"offset_{offset + batch_count}" if has_next else None
        return page, next_token
