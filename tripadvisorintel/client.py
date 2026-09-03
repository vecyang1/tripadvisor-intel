"""High-level Client coordinating transport, caching, and reasoning."""

from __future__ import annotations

from typing import List, Optional, Union
from .parsers import extract_place_id
from .models import PlaceSummary, PlaceDetail, DossierReport, ReviewItem
from .transports.base import BaseTransport
from .transports.serpapi import SerpApiTransport
from .transports.direct_api import DirectApiTransport
from .config import serpapi_api_key
from .cache import cache, CacheDB
from .reasoning.engine import generate_dossier


class TripAdvisorClient:
    def __init__(
        self,
        transport: Optional[BaseTransport] = None,
        fallback_transport: Optional[BaseTransport] = None,
        cache_instance: Optional[CacheDB] = None,
        enable_llm: bool = True,
        transport_mode: Optional[str] = None,
        use_residential_proxy: bool = False,
        proxy_url: Optional[str] = None,
        geo: str = "us",
    ):
        if transport is not None:
            self.transport = transport
            self.fallback_transport = fallback_transport
        else:
            has_serp = bool(serpapi_api_key())
            # Mode selection:
            # - "direct_api": Direct internal API (fast, free, no DataDome)
            # - "serpapi": SerpApi managed solver
            mode = transport_mode or ("serpapi" if has_serp else "direct_api")
            
            if mode == "direct_api":
                self.transport = DirectApiTransport(
                    proxy_url=proxy_url,
                    use_residential_proxy=use_residential_proxy,
                    geo=geo,
                )
                self.fallback_transport = fallback_transport or (SerpApiTransport() if has_serp else None)
            else:
                self.transport = SerpApiTransport()
                self.fallback_transport = fallback_transport or DirectApiTransport(
                    proxy_url=proxy_url,
                    use_residential_proxy=use_residential_proxy,
                    geo=geo,
                )

        self.cache = cache_instance or cache
        self.enable_llm = enable_llm

    def _execute_with_fallback(self, method_name: str, *args, **kwargs):
        """Execute method on primary transport, falling back to secondary if blocked."""
        try:
            method = getattr(self.transport, method_name)
            return method(*args, **kwargs)
        except Exception as err:
            if self.fallback_transport is not None:
                fallback_method = getattr(self.fallback_transport, method_name)
                return fallback_method(*args, **kwargs)
            raise

    def search(
        self,
        query: str,
        category: str = "all",
        domain: str = "www.tripadvisor.com",
        limit: int = 30,
        force_refresh: bool = False,
    ) -> List[PlaceSummary]:
        """Search TripAdvisor places with automatic caching."""
        if not force_refresh:
            cached = self.cache.get_search(query=query, category=category, domain=domain)
            if cached is not None:
                return [PlaceSummary.model_validate(p) for p in cached][:limit]

        results = self._execute_with_fallback(
            "search_places", query=query, category=category, domain=domain, limit=limit
        )
        self.cache.set_search(
            query=query,
            category=category,
            places=[r.model_dump() for r in results],
            domain=domain,
        )
        return results

    def get_place(
        self,
        target: str,
        domain: str = "www.tripadvisor.com",
        reviews_pages: int = 1,
        force_refresh: bool = False,
    ) -> PlaceDetail:
        """Fetch full place details, ranking, and reviews with caching."""
        place_id = extract_place_id(target) or str(target)

        if not force_refresh:
            cached = self.cache.get_place(place_id=place_id, domain=domain)
            if cached is not None:
                # If requested more review pages than cached, re-fetch
                cached_reviews = len(cached.get("reviews_list", []))
                if reviews_pages <= 1 or cached_reviews >= reviews_pages * 4:
                    return PlaceDetail.model_validate(cached)

        detail = self._execute_with_fallback(
            "get_place_detail", place_id=place_id, domain=domain, reviews_pages=reviews_pages
        )
        self.cache.set_place(place_id=place_id, detail=detail.model_dump(), domain=domain)
        return detail

    def get_reviews(
        self,
        target: Optional[str] = None,
        place_id: Optional[str] = None,
        max_reviews: int = 40,
        page_size: int = 20,
        domain: str = "www.tripadvisor.com",
        force_refresh: bool = False,
    ) -> List[ReviewItem]:
        """Retrieve paginated reviews for a place with progressive SQLite caching."""
        import time
        raw_target = target or place_id or ""
        resolved_place_id = extract_place_id(raw_target) or str(raw_target)

        # 1. Check local SQLite cache first
        if not force_refresh:
            cached_rows = self.cache.get_reviews(place_id=resolved_place_id, limit=max_reviews)
            if cached_rows and len(cached_rows) >= max_reviews:
                return [ReviewItem(**r) for r in cached_rows[:max_reviews]]

        all_reviews: List[ReviewItem] = []
        if not force_refresh:
            existing = self.cache.get_reviews(place_id=resolved_place_id)
            all_reviews = [ReviewItem(**r) for r in existing]

        seen_ids = {r.review_id for r in all_reviews if r.review_id}
        offset = len(all_reviews)

        while len(all_reviews) < max_reviews:
            batch_limit = min(page_size, max_reviews - len(all_reviews))
            try:
                batch, next_token = self._execute_with_fallback(
                    "get_reviews",
                    place_id=resolved_place_id,
                    limit=batch_limit,
                    offset=offset,
                    domain=domain,
                )
            except Exception:
                break

            if not batch:
                break

            new_in_batch = []
            for item in batch:
                if item.review_id and item.review_id in seen_ids:
                    continue
                if item.review_id:
                    seen_ids.add(item.review_id)
                all_reviews.append(item)
                new_in_batch.append(item)

            if new_in_batch:
                self.cache.save_reviews(place_id=resolved_place_id, reviews=[r.model_dump() for r in new_in_batch])
                if max_reviews > 20:
                    print(f"  [Progress] Ingested offset {offset:>3}: +{len(new_in_batch)} reviews -> {len(all_reviews)}/{max_reviews} in SQLite", flush=True)

            if not next_token or len(batch) < batch_limit:
                break
            offset += len(batch)
            time.sleep(0.2)

        return all_reviews[:max_reviews]

    def analyze(
        self,
        target: str,
        category: str = "all",
        domain: str = "www.tripadvisor.com",
        persona: str = "general",
        reviews_pages: int = 1,
        max_reviews: Optional[int] = None,
        force_refresh: bool = False,
        enable_llm: Optional[bool] = None,
    ) -> DossierReport:
        """Analyze a place ID, TripAdvisor URL, or name query and return an actionable DossierReport."""
        # 1. Resolve place_id via extract_place_id or search
        extracted_id = extract_place_id(target)
        if extracted_id:
            place_id = extracted_id
        else:
            search_results = self.search(
                query=target, category=category, domain=domain, limit=1, force_refresh=force_refresh
            )
            if not search_results:
                raise ValueError(f"No TripAdvisor place found matching query: '{target}'")
            place_id = search_results[0].place_id

        # 2. Check cached report
        if not force_refresh and reviews_pages <= 1 and not max_reviews:
            cached_report = self.cache.get_report(place_id=place_id, persona=persona)
            if cached_report is not None:
                return DossierReport.model_validate(cached_report)

        # 3. Fetch full details
        place_detail = self.get_place(
            target=place_id, domain=domain, reviews_pages=reviews_pages, force_refresh=force_refresh
        )

        # 3b. Optional deep review pagination
        if max_reviews and max_reviews > len(place_detail.reviews_list):
            deep_reviews = self.get_reviews(
                target=place_id, max_reviews=max_reviews, domain=domain, force_refresh=force_refresh
            )
            if deep_reviews:
                place_detail.reviews_list = deep_reviews

        # 4. Generate reasoning dossier
        use_llm = self.enable_llm if enable_llm is None else enable_llm
        report = generate_dossier(place_detail, enable_llm=use_llm)

        # 5. Persist to cache
        self.cache.set_report(place_id=place_id, persona=persona, report=report.model_dump())
        return report
