"""SerpApi transport for TripAdvisor extraction."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any, Tuple
from .base import BaseTransport
from ..parsers import parse_search_results, parse_place_details, parse_reviews_response
from ..config import serpapi_api_key, serpapi_api_keys


CATEGORY_MAP = {
    # Hotels
    "hotels": "h",
    "hotel": "h",
    "stays": "h",
    "resorts": "h",
    "resort": "h",
    "hostels": "h",
    "hostel": "h",
    "homestay": "h",
    "villas": "h",
    "h": "h",
    # Restaurants
    "restaurants": "r",
    "restaurant": "r",
    "food": "r",
    "dining": "r",
    "cafes": "r",
    "cafe": "r",
    "bars": "r",
    "bar": "r",
    "coffee": "r",
    "bakery": "r",
    "r": "r",
    # Attractions
    "attractions": "A",
    "attraction": "A",
    "things_to_do": "A",
    "experiences": "A",
    "activities": "A",
    "activity": "A",
    "tours": "A",
    "tour": "A",
    "sightseeing": "A",
    "museums": "A",
    "A": "A",
    # Destinations & Forums
    "destinations": "g",
    "g": "g",
    "forums": "f",
    "forum": "f",
    "f": "f",
    "all": "a",
    "a": "a",
}


class SerpApiTransport(BaseTransport):
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        timeout: float = 45.0,
        retries: int = 2,
    ):
        if api_keys:
            self.keys = [k for k in api_keys if k]
        elif api_key:
            self.keys = [api_key]
        else:
            self.keys = serpapi_api_keys() or ([serpapi_api_key()] if serpapi_api_key() else [])

        self.current_key_idx = 0
        self.timeout = timeout
        self.retries = retries

    @property
    def api_key(self) -> Optional[str]:
        if not self.keys:
            return None
        return self.keys[self.current_key_idx % len(self.keys)]

    def _rotate_key(self) -> bool:
        """Rotate to next available key in the pool. Returns True if rotated, False if pool exhausted."""
        if len(self.keys) <= 1:
            return False
        old_idx = self.current_key_idx
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        import sys
        sys.stderr.write(f"[SerpApi Pool] Rotated key #{old_idx + 1} -> #{self.current_key_idx + 1} of {len(self.keys)}\n")
        return True

    def _ensure_key(self) -> str:
        k = self.api_key
        if not k:
            raise RuntimeError(
                "SerpAPI key not found. Please set SERPAPI_API_KEY environment variable "
                "or place it in .env"
            )
        return k

    def _get_json(self, params: Dict[str, Any]) -> Dict[str, Any]:
        req_params = dict(params)
        for attempt in range(self.retries + len(self.keys)):
            key = self._ensure_key()
            req_params["api_key"] = key
            query_str = urllib.parse.urlencode(req_params)
            url = f"https://serpapi.com/search.json?{query_str}"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "tripadvisor-intel/1.0.0 (+https://github.com/vecyang1)",
                    "Accept": "application/json",
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw_bytes = resp.read()
                    data = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(data, dict) and "error" in data:
                        err_str = str(data["error"])
                        if any(term in err_str.lower() for term in ["run out of searches", "monthly search limit", "invalid api key"]) and self._rotate_key():
                            continue
                        raise RuntimeError(f"SerpAPI Error: {err_str}")
                    return data
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                if (e.code in (401, 429) or any(term in err_body.lower() for term in ["run out of searches", "monthly search limit"])) and self._rotate_key():
                    continue
                raise RuntimeError(f"SerpAPI HTTP {e.code} Error: {err_body}") from e
            except (TimeoutError, urllib.error.URLError) as e:
                if attempt < self.retries:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise RuntimeError(f"Network error querying SerpAPI: {e}") from e
            except Exception as e:
                raise RuntimeError(f"Network error querying SerpAPI: {e}") from e

    def search_places(
        self,
        query: str,
        category: str = "all",
        domain: str = "www.tripadvisor.com",
        limit: int = 30,
    ) -> List[PlaceSummary]:
        ssrc = CATEGORY_MAP.get(category.lower(), "a")
        page_limit = min(limit, 30)
        params = {
            "engine": "tripadvisor",
            "q": query,
            "ssrc": ssrc,
            "tripadvisor_domain": domain,
            "limit": page_limit,
        }
        data = self._get_json(params)
        results = parse_search_results(data)

        # Multi-page search fetch if limit > 30 and first page was full
        if limit > 30 and len(results) >= 30:
            offset = 30
            while len(results) < limit:
                remaining = limit - len(results)
                fetch_count = min(remaining, 30)
                next_params = dict(params)
                next_params["offset"] = offset
                next_params["limit"] = fetch_count
                try:
                    next_data = self._get_json(next_params)
                    more_places = parse_search_results(next_data)
                    if not more_places:
                        break
                    results.extend(more_places)
                    offset += len(more_places)
                    if len(more_places) < fetch_count:
                        break
                except Exception:
                    break

        return results[:limit]

    def get_place_detail(
        self,
        place_id: str,
        domain: str = "www.tripadvisor.com",
        reviews_pages: int = 1,
    ) -> PlaceDetail:
        params = {
            "engine": "tripadvisor_place",
            "place_id": str(place_id),
            "tripadvisor_domain": domain,
        }
        data = self._get_json(params)
        detail = parse_place_details(data, place_id=str(place_id))

        # Optional review pagination
        if reviews_pages > 1:
            for page_num in range(2, reviews_pages + 1):
                page_params = dict(params)
                page_params["page"] = page_num
                try:
                    p_data = self._get_json(page_params)
                    p_detail = parse_place_details(p_data, place_id=str(place_id))
                    if p_detail.reviews_list:
                        # Deduplicate by snippet or title
                        seen_snippets = {r.snippet for r in detail.reviews_list}
                        for r in p_detail.reviews_list:
                            if r.snippet not in seen_snippets:
                                detail.reviews_list.append(r)
                                seen_snippets.add(r.snippet)
                    else:
                        break
                except Exception:
                    # Fail-open: retain existing loaded reviews
                    break

        return detail

    def get_reviews(
        self,
        place_id: str,
        limit: int = 20,
        offset: int = 0,
        domain: str = "www.tripadvisor.com",
    ) -> Tuple[List[ReviewItem], Optional[str]]:
        """Fetch paginated reviews for a place via SerpApi tripadvisor_reviews engine."""
        params = {
            "engine": "tripadvisor_reviews",
            "place_id": str(place_id),
            "limit": min(limit, 20),
            "offset": offset,
            "tripadvisor_domain": domain,
        }
        data = self._get_json(params)
        return parse_reviews_response(data)
