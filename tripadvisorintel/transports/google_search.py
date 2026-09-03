"""Google Custom Search API integration for TripAdvisor URL & Place ID resolution."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Optional, Tuple, Dict, Any, List
from ..models import PlaceSummary


class GoogleSearchResolver:
    """Discovers TripAdvisor Place IDs and URLs via Google Custom Search JSON API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        cx: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.api_key = api_key
        self.cx = cx
        self.timeout = timeout

    def search_tripadvisor(self, query: str, limit: int = 5, use_agent_sdk: bool = True) -> List[PlaceSummary]:
        """Search for TripAdvisor listings matching query via agent-search-sdk cascade or Google CSE."""
        results: List[PlaceSummary] = []

        # 1. Try agent-search-sdk cascade first (Brave -> Tavily -> SerpApi -> DuckDuckGo)
        if use_agent_sdk:
            try:
                sdk_paths = [
                    "/Users/vecsatfoxmailcom/Documents/A-coding/26.09.03-agent-search-sdk",
                ]
                import sys
                for p in sdk_paths:
                    if p not in sys.path:
                        sys.path.insert(0, p)
                from search_sdk import search as agent_search  # type: ignore

                sdk_resp = agent_search(query, domain="tripadvisor.com", limit=limit)
                for item in sdk_resp.results:
                    match = re.search(r"-d(\d+)-", item.url)
                    if match:
                        place_id = match.group(1)
                        clean_title = re.sub(r"\s*-\s*Tripadvisor.*$", "", item.title, flags=re.IGNORECASE)
                        results.append(
                            PlaceSummary(
                                position=len(results) + 1,
                                place_id=place_id,
                                title=clean_title,
                                link=item.url,
                                location=item.snippet[:60] if item.snippet else None,
                            )
                        )
                if results:
                    return results[:limit]
            except Exception:
                pass

        # 2. Fallback to Google Custom Search JSON API
        if not self.api_key or not self.cx:
            return []

        search_query = f"{query} site:tripadvisor.com"
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": search_query,
            "num": min(limit, 10),
        }
        url = f"https://www.googleapis.com/customsearch/v1?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "tripadvisor-intel/1.0.0 (+https://github.com/vecyang1)"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        results: List[PlaceSummary] = []
        for item in data.get("items", []):
            link = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")

            # Extract TripAdvisor numeric place ID from URL pattern: -d(\d+)-
            match = re.search(r"-d(\d+)-", link)
            if match:
                place_id = match.group(1)
                clean_title = re.sub(r"\s*-\s*Tripadvisor.*$", "", title, flags=re.IGNORECASE)
                results.append(
                    PlaceSummary(
                        position=len(results) + 1,
                        place_id=place_id,
                        title=clean_title,
                        link=link,
                        location=snippet[:60] if snippet else None,
                    )
                )

        return results
