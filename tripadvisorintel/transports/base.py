"""Abstract base transport for TripAdvisor data retrieval."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from ..models import PlaceSummary, PlaceDetail


class BaseTransport(ABC):
    @abstractmethod
    def search_places(
        self,
        query: str,
        category: str = "all",
        domain: str = "www.tripadvisor.com",
        limit: int = 30,
    ) -> List[PlaceSummary]:
        """Search TripAdvisor for places matching query."""
        pass

    @abstractmethod
    def get_place_detail(
        self,
        place_id: str,
        domain: str = "www.tripadvisor.com",
        reviews_pages: int = 1,
    ) -> PlaceDetail:
        """Fetch full details and recent reviews for a place."""
        pass

    @abstractmethod
    def get_reviews(
        self,
        place_id: str,
        limit: int = 20,
        offset: int = 0,
        domain: str = "www.tripadvisor.com",
    ) -> Tuple[List[Any], Optional[str]]:
        """Fetch paginated reviews for a place. Returns (reviews, next_page_token_or_url)."""
        pass
