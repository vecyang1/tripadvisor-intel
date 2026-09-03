"""Data models for tripadvisor-intel."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class HighlightedReview(BaseModel):
    text: Optional[str] = None
    highlighted_texts: List[str] = Field(default_factory=list)
    mention_count: Optional[int] = None


class PlaceSummary(BaseModel):
    position: int = 0
    title: str
    place_id: str
    place_type: Optional[str] = "UNKNOWN"
    link: Optional[str] = None
    serpapi_link: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = 0
    location: Optional[str] = None
    thumbnail: Optional[str] = None
    highlighted_review: Optional[HighlightedReview] = None


class Subrating(BaseModel):
    category: str
    score: float


class PriceRange(BaseModel):
    low: Optional[float] = None
    high: Optional[float] = None
    currency: Optional[str] = "USD"


class ReviewAuthor(BaseModel):
    username: Optional[str] = None
    link: Optional[str] = None
    avatar: Optional[str] = None
    contributions: Optional[int] = 0
    hometown: Optional[str] = None


class ReviewItem(BaseModel):
    review_id: Optional[str] = None
    title: Optional[str] = None
    snippet: str
    rating: float = 0.0
    date: Optional[str] = None
    link: Optional[str] = None
    trip_type: Optional[str] = None
    language: Optional[str] = None
    votes: Optional[int] = 0
    author: Optional[ReviewAuthor] = None


class ReviewDistribution(BaseModel):
    star_5: int = 0
    star_4: int = 0
    star_3: int = 0
    star_2: int = 0
    star_1: int = 0

    @property
    def total(self) -> int:
        return self.star_5 + self.star_4 + self.star_3 + self.star_2 + self.star_1

    @property
    def negative_ratio(self) -> float:
        """Percentage of reviews that are 1-star or 2-star."""
        if self.total == 0:
            return 0.0
        return (self.star_1 + self.star_2) / self.total


class PlaceDetail(BaseModel):
    place_id: str
    name: str
    place_type: Optional[str] = "ACCOMMODATION"
    rating: Optional[float] = 0.0
    reviews: Optional[int] = 0
    ranking: Optional[str] = None
    ranking_position: Optional[int] = None
    ranking_total: Optional[int] = None
    ranking_category: Optional[str] = None
    ranking_location: Optional[str] = None
    price_range: Optional[PriceRange] = None
    hotel_stars: Optional[float] = None
    hotel_class: Optional[str] = None
    hotel_style: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    languages_spoken: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    subratings: List[Subrating] = Field(default_factory=list)
    amenities: List[Dict[str, Any]] = Field(default_factory=list)
    room_features: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    room_types: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    address: Optional[str] = None
    gps_coordinates: Optional[Dict[str, float]] = None
    walk_score: Optional[int] = None
    review_distribution: Optional[ReviewDistribution] = None
    reviews_highlights: List[Dict[str, Any]] = Field(default_factory=list)
    reviews_list: List[ReviewItem] = Field(default_factory=list)
    nearby: Optional[Dict[str, Any]] = None


class PersonaFitScore(BaseModel):
    persona: str  # e.g., "solo_nomad", "couples", "family", "budget_backpacker"
    score: float  # 0.0 to 10.0
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)
    recommendation: str


class RedFlagItem(BaseModel):
    category: str  # cleanliness, noise, scam_and_billing, maintenance, safety, food_and_hygiene, etc.
    severity: str  # high, medium, low
    description: str
    evidence_snippet: Optional[str] = None


class DossierReport(BaseModel):
    place_id: str
    name: str
    category: str
    rating: float
    review_count: int
    ranking: Optional[str]
    rank_percentile: Optional[float] = None  # top X%
    price_range: Optional[PriceRange] = None
    value_discrepancy_score: float = 0.0  # discrepancy between rating and value subrating
    value_rating_vs_overall: Optional[str] = None
    authenticity_score: Optional[float] = 10.0  # 0.0 - 10.0 rating authenticity metric
    authenticity_assessment: Optional[str] = None
    red_flags: List[RedFlagItem] = Field(default_factory=list)
    key_strengths: List[str] = Field(default_factory=list)
    key_weaknesses: List[str] = Field(default_factory=list)
    persona_fits: Dict[str, PersonaFitScore] = Field(default_factory=dict)
    walk_in_brief: str
    negotiation_baseline: Optional[str] = None
    source_coverage: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str
