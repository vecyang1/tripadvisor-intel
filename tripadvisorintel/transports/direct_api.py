"""Direct mobile API transport for TripAdvisor.

Bypasses DataDome Web JavaScript shield by targeting TripAdvisor's internal
mobile API endpoint (api.tripadvisor.com/api/internal/1.14).
Supports direct connection and residential proxy pools (DataImpulse) via ultra-low-cost-scraper.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseTransport
from ..models import PlaceSummary, PlaceDetail, ReviewItem, ReviewAuthor, Subrating, PriceRange

DEFAULT_CLIENT_KEY = "ce957ab2-0385-40f2-a32d-ed80296ff67f"
BASE_API_URL = "https://api.tripadvisor.com/api/internal/1.14"

CATEGORY_MAP = {
    "hotels": "lodging",
    "hotel": "lodging",
    "stays": "lodging",
    "lodging": "lodging",
    "restaurants": "restaurants",
    "restaurant": "restaurants",
    "dining": "restaurants",
    "food": "restaurants",
    "attractions": "activities",
    "attraction": "activities",
    "activities": "activities",
    "things_to_do": "activities",
    "geos": "geos",
    "destinations": "geos",
    "all": "activities",
}


def _resolve_residential_proxy(geo: Optional[str] = "us") -> Optional[str]:
    """Attempt to resolve user residential proxy from ultra-low-cost-scraper."""
    try:
        scraper_paths = [
            "/Users/vecsatfoxmailcom/.gemini/config/skills/ultra-low-cost-scraper/scripts",
            os.path.expanduser("~/.agents/skills/ultra-low-cost-scraper/scripts"),
        ]
        for p in scraper_paths:
            if os.path.exists(p) and p not in sys.path:
                sys.path.insert(0, p)
        import proxy_resolver  # type: ignore
        return proxy_resolver.resolve_proxy_url(geo=geo)
    except Exception:
        return None


class DirectApiTransport(BaseTransport):
    """Direct TripAdvisor API transport bypassing DataDome bot shields."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        proxy_url: Optional[str] = None,
        use_residential_proxy: bool = False,
        geo: str = "us",
        timeout: float = 20.0,
        retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("TRIPADVISOR_INTERNAL_KEY") or os.getenv("TRIPADVISOR_API_KEY") or DEFAULT_CLIENT_KEY
        self.geo = geo
        self.timeout = timeout
        self.retries = retries

        resolved_proxy = proxy_url
        if not resolved_proxy and use_residential_proxy:
            resolved_proxy = _resolve_residential_proxy(geo=geo)

        self.proxy_url = resolved_proxy
        if self.proxy_url:
            proxy_handler = urllib.request.ProxyHandler({"http": self.proxy_url, "https": self.proxy_url})
            self.opener = urllib.request.build_opener(proxy_handler)
        else:
            self.opener = urllib.request.build_opener()

    def _request_json(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{BASE_API_URL}/{endpoint.lstrip('/')}"
        if params:
            encoded_params = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}?{encoded_params}"

        headers = {
            "X-TripAdvisor-API-Key": self.api_key,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
            "User-Agent": "TripAdvisor/26.0 (Android; Mobile)",
        }

        req = urllib.request.Request(url, headers=headers)

        last_err: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                with self.opener.open(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    try:
                        decompressed = gzip.decompress(raw)
                    except Exception:
                        decompressed = raw
                    data = json.loads(decompressed.decode("utf-8"))
                    if isinstance(data, dict) and data.get("errors"):
                        err_msg = data["errors"][0].get("message", "Unknown API error")
                        raise RuntimeError(f"TripAdvisor Direct API Error: {err_msg}")
                    return data
            except urllib.error.HTTPError as e:
                try:
                    err_bytes = e.read()
                    try:
                        err_decomp = gzip.decompress(err_bytes)
                    except Exception:
                        err_decomp = err_bytes
                    err_json = json.loads(err_decomp.decode("utf-8", errors="replace"))
                    msg = err_json.get("errors", [{}])[0].get("message", str(e))
                except Exception:
                    msg = str(e)
                last_err = RuntimeError(f"TripAdvisor API HTTP {e.code}: {msg}")
                if e.code in (401, 403, 404):
                    raise last_err from e
            except Exception as e:
                last_err = e

            if attempt < self.retries:
                time.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"TripAdvisor Direct API failed after {self.retries + 1} attempts: {last_err}") from last_err

    def search_places(
        self,
        query: str,
        category: str = "all",
        domain: str = "www.tripadvisor.com",
        limit: int = 30,
    ) -> List[PlaceSummary]:
        api_category = CATEGORY_MAP.get(category.lower(), "activities")
        data = self._request_json("typeahead", {"query": query, "category_type": api_category})
        results: List[PlaceSummary] = []
        raw_items = data.get("data", [])

        for idx, item in enumerate(raw_items[:limit], 1):
            res_obj = item.get("result_object") or {}
            loc_id = res_obj.get("location_id")
            if not loc_id:
                continue

            photo = res_obj.get("photo") or {}
            images = photo.get("images") or {}
            thumb = (images.get("thumbnail") or images.get("small") or images.get("medium") or {}).get("url")

            num_revs = None
            try:
                num_revs = int(res_obj.get("num_reviews", 0) or 0)
            except (ValueError, TypeError):
                num_revs = 0

            rating_val = None
            try:
                if res_obj.get("rating") is not None:
                    rating_val = float(res_obj.get("rating"))
            except (ValueError, TypeError):
                rating_val = None

            results.append(
                PlaceSummary(
                    position=idx,
                    title=res_obj.get("name") or "Unknown Place",
                    place_id=str(loc_id),
                    place_type=item.get("result_type", "UNKNOWN").upper(),
                    link=res_obj.get("web_url") or res_obj.get("url"),
                    rating=rating_val,
                    reviews=num_revs,
                    location=res_obj.get("location_string") or res_obj.get("address"),
                    thumbnail=thumb,
                )
            )

        return results

    def get_place_detail(
        self,
        place_id: str,
        domain: str = "www.tripadvisor.com",
        reviews_pages: int = 1,
    ) -> PlaceDetail:
        data = self._request_json(f"location/{place_id}")
        
        # Parse ranking
        ranking_str = data.get("ranking")
        pos = None
        tot = None
        try:
            if data.get("ranking_position"):
                pos = int(data.get("ranking_position"))
            if data.get("ranking_denominator"):
                tot = int(data.get("ranking_denominator"))
        except (ValueError, TypeError):
            pass

        # Parse GPS
        gps = None
        if data.get("latitude") and data.get("longitude"):
            try:
                gps = {
                    "latitude": float(data.get("latitude")),
                    "longitude": float(data.get("longitude")),
                }
            except (ValueError, TypeError):
                pass

        # Rating and review count
        r_val = 0.0
        try:
            r_val = float(data.get("rating") or 0.0)
        except (ValueError, TypeError):
            r_val = 0.0

        n_revs = 0
        try:
            n_revs = int(data.get("num_reviews") or 0)
        except (ValueError, TypeError):
            n_revs = 0

        # Subratings
        subratings_list: List[Subrating] = []
        for s in data.get("subratings") or []:
            name = s.get("name")
            val = s.get("value")
            if name and val:
                try:
                    subratings_list.append(Subrating(category=str(name), score=float(val)))
                except (ValueError, TypeError):
                    pass

        # Fetch recent reviews to populate reviews_list
        recent_reviews, _ = self.get_reviews(place_id=place_id, limit=20, offset=0, domain=domain)

        return PlaceDetail(
            place_id=str(data.get("location_id") or place_id),
            name=data.get("name") or "Unknown",
            place_type=str(data.get("subcategory_type_label") or "ACCOMMODATION").upper(),
            rating=r_val,
            reviews=n_revs,
            ranking=ranking_str,
            ranking_position=pos,
            ranking_total=tot,
            address=data.get("address") or data.get("location_string"),
            gps_coordinates=gps,
            subratings=subratings_list,
            reviews_list=recent_reviews,
        )

    def get_reviews(
        self,
        place_id: str,
        limit: int = 20,
        offset: int = 0,
        domain: str = "www.tripadvisor.com",
    ) -> Tuple[List[ReviewItem], Optional[str]]:
        params = {
            "limit": min(limit, 20),
            "offset": offset,
        }
        data = self._request_json(f"location/{place_id}/reviews", params)
        raw_reviews = data.get("data", [])
        paging = data.get("paging") or {}
        next_token = paging.get("next")

        reviews: List[ReviewItem] = []
        for r in raw_reviews:
            u = r.get("user") or {}
            author = ReviewAuthor(
                username=u.get("username"),
                hometown=(u.get("user_location") or {}).get("name"),
                avatar=((u.get("avatar") or {}).get("small") or {}).get("url"),
                contributions=int((u.get("contributions") or {}).get("reviews", 0) or 0),
            )
            r_val = 0.0
            try:
                r_val = float(r.get("rating") or 0.0)
            except (ValueError, TypeError):
                r_val = 0.0

            pub_date = r.get("published_date")
            date_str = pub_date[:10] if pub_date else None

            votes_val = 0
            try:
                votes_val = int(r.get("helpful_votes") or 0)
            except (ValueError, TypeError):
                votes_val = 0

            reviews.append(
                ReviewItem(
                    review_id=str(r.get("id")),
                    title=r.get("title"),
                    snippet=r.get("text") or "",
                    rating=r_val,
                    date=date_str,
                    link=r.get("url"),
                    language=r.get("lang"),
                    votes=votes_val,
                    author=author,
                )
            )

        return reviews, next_token
