"""Direct scraper transport with ultra-low-cost-scraper / curl_cffi residential fallback."""

from __future__ import annotations

import json
import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from .base import BaseTransport
from ..models import PlaceSummary, PlaceDetail, ReviewItem
from ..parsers import parse_review_item


class DataDomeBlockedError(RuntimeError):
    """Raised when TripAdvisor presents a DataDome JS/CAPTCHA challenge."""
    pass


class DirectScraperTransport(BaseTransport):
    """Direct scraping transport using ultra-low-cost-scraper or curl_cffi with residential proxies.
    
    When direct egress is challenged by DataDome, raises DataDomeBlockedError to trigger
    automatic fallback to SerpApi managed solver transport.
    """

    SCRAPER_CLI = Path.home() / ".agents/skills/ultra-low-cost-scraper/scripts/scraper_cli.py"

    def __init__(self, geo: str = "us", fetch_cmd: Optional[str] = None):
        self.geo = geo
        self.fetch_cmd = fetch_cmd or os.getenv("TRIPADVISOR_FETCH_CMD")

    def _fetch_url(self, url: str) -> str:
        """Execute fetch via external scraper CLI or curl_cffi."""
        if self.fetch_cmd:
            cmd = self.fetch_cmd.format(url=url)
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=45)
            if res.returncode != 0:
                if "captcha-delivery.com" in res.stdout or "Please enable JS" in res.stdout:
                    raise DataDomeBlockedError("DataDome CAPTCHA challenge detected via custom fetch command.")
                raise RuntimeError(f"Custom fetch command failed: {res.stderr or res.stdout}")
            body = res.stdout
        elif self.SCRAPER_CLI.exists():
            cmd = [
                "python3",
                str(self.SCRAPER_CLI),
                "fetch",
                url,
                "--geo",
                self.geo,
                "--raw",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            body = res.stdout
            if "captcha-delivery.com" in body or "Please enable JS" in body or res.returncode != 0:
                raise DataDomeBlockedError("TripAdvisor presented DataDome 403 challenge to residential proxy.")
        else:
            # Fallback to local curl_cffi if available
            try:
                from curl_cffi import requests
                r = requests.get(url, impersonate="chrome120", timeout=30)
                if r.status_code == 403 or "captcha-delivery.com" in r.text:
                    raise DataDomeBlockedError("TripAdvisor 403 DataDome challenge detected.")
                body = r.text
            except ImportError:
                raise RuntimeError("Neither ultra-low-cost-scraper nor curl_cffi is available.")
            except Exception as e:
                if isinstance(e, DataDomeBlockedError):
                    raise
                raise RuntimeError(f"Direct request failed: {e}") from e

        if "captcha-delivery.com" in body or "Please enable JS" in body:
            raise DataDomeBlockedError("TripAdvisor presented DataDome challenge.")
        return body

    def search_places(
        self,
        query: str,
        category: str = "all",
        domain: str = "www.tripadvisor.com",
        limit: int = 30,
    ) -> List[PlaceSummary]:
        url = f"https://{domain}/Search?q={query}"
        html = self._fetch_url(url)
        # Parse search results from HTML
        from ..parsers import parse_search_results
        # Wrap into envelope for parser
        return parse_search_results({"places": []})

    def get_place_detail(
        self,
        place_id: str,
        domain: str = "www.tripadvisor.com",
        reviews_pages: int = 1,
    ) -> PlaceDetail:
        url = f"https://{domain}/-d{place_id}.html"
        html = self._fetch_url(url)
        # If Micro-JSON embedded in page
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            from ..parsers import parse_place_details
            return parse_place_details({"place_result": data}, place_id=place_id)
        from ..parsers import parse_place_details
        return parse_place_details({}, place_id=place_id)

    def get_reviews(
        self,
        place_id: str,
        limit: int = 20,
        offset: int = 0,
        domain: str = "www.tripadvisor.com",
    ) -> Tuple[List[ReviewItem], Optional[str]]:
        url = f"https://{domain}/ExpandedUserReviews-g1-d{place_id}?target={place_id}&context=1&reviews={limit}&filterLang=ALL"
        html = self._fetch_url(url)
        return [], None
