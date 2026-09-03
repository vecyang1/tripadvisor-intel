"""Defensive parsers for TripAdvisor API and data envelopes."""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple
from .models import (
    PlaceSummary,
    HighlightedReview,
    PlaceDetail,
    Subrating,
    PriceRange,
    ReviewDistribution,
    ReviewItem,
    ReviewAuthor,
)


def safe_float(val: Any) -> Optional[float]:
    """Safely convert numeric, string, or bubble ratings into float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Handle "bubble_45" -> 4.5 or "bubble_50" -> 5.0
        m_bubble = re.search(r"bubble_(\d+)", val, re.IGNORECASE)
        if m_bubble:
            return float(m_bubble.group(1)) / 10.0
        # Handle "4.5 of 5", "4,5", "4.5"
        val_clean = val.replace(",", ".")
        m = re.search(r"([\d\.]+)", val_clean)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def safe_int(val: Any) -> Optional[int]:
    """Safely convert numeric or formatted string with commas into int."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str):
        m = re.search(r"(\d+)", val.replace(",", ""))
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
    return None


def extract_place_id(target: Optional[str]) -> Optional[str]:
    """Extract numeric TripAdvisor place ID from raw ID, URL, or identifier string.

    Returns numeric ID string if recognized, otherwise None.
    Examples:
        - "7182682" -> "7182682"
        - "d7182682" -> "7182682"
        - "https://www.tripadvisor.com/Hotel_Review-g298082-d7182682-Reviews-..." -> "7182682"
        - "https://www.tripadvisor.com/...place_id=7182682" -> "7182682"
    """
    if not target or not isinstance(target, str):
        return None
    s = target.strip()

    # 1. Pure numeric ID
    if s.isdigit():
        return s

    # 2. 'd' prefix e.g. 'd7182682'
    if s.lower().startswith("d") and s[1:].isdigit():
        return s[1:]

    # 3. URL patterns with -d<ID>- or /d<ID> or -d<ID>.html
    m_url = re.search(r"[-/]d(\d+)(?:[-_.]|$)", s)
    if m_url:
        return m_url.group(1)

    # 4. Query param place_id=12345 or id=12345 or d=12345
    m_param = re.search(r"[?&](?:place_id|id|d)=(\d+)", s)
    if m_param:
        return m_param.group(1)

    return None


def parse_ranking_string(raw: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
    """Parse string like '#45 of 466 hotels in Hoi An', '#45 of 466', or regional variations.
    
    Returns (position, total, category, location).
    """
    if not raw or not isinstance(raw, str):
        return None, None, None, None
    s = raw.strip()

    # 1. Chinese format: 466家酒店中排名第45
    m_cn1 = re.search(r"([\d,]+)\s*家(?:.+?)中(?:排名)?第\s*([\d,]+)", s)
    if m_cn1:
        return int(m_cn1.group(2).replace(",", "")), int(m_cn1.group(1).replace(",", "")), None, None

    # 2. Chinese format: 第45名（共466家酒店）
    m_cn2 = re.search(r"第\s*([\d,]+)\s*名[（\(]共\s*([\d,]+)", s)
    if m_cn2:
        return int(m_cn2.group(1).replace(",", "")), int(m_cn2.group(2).replace(",", "")), None, None

    # 3. Vietnamese: #1 trong số 466 khách sạn tại Hội An
    m_vn = re.search(r"#?([\d,]+)\s+trong\s+số\s+([\d,]+)(?:\s+(.+?)\s+tại\s+(.+))?", s, re.IGNORECASE)
    if m_vn:
        pos = int(m_vn.group(1).replace(",", ""))
        total = int(m_vn.group(2).replace(",", ""))
        cat = m_vn.group(3).strip() if m_vn.group(3) else None
        loc = m_vn.group(4).strip() if m_vn.group(4) else None
        return pos, total, cat, loc

    # 4. French: #45 sur 466 hôtels à Hoi An
    m_fr = re.search(r"#?([\d,]+)\s+sur\s+([\d,]+)(?:\s+(.+?)\s+[àa]\s+(.+))?", s, re.IGNORECASE)
    if m_fr:
        pos = int(m_fr.group(1).replace(",", ""))
        total = int(m_fr.group(2).replace(",", ""))
        cat = m_fr.group(3).strip() if m_fr.group(3) else None
        loc = m_fr.group(4).strip() if m_fr.group(4) else None
        return pos, total, cat, loc

    # 5. English explicit: #45 of 466 hotels in Hoi An
    m_en_exp = re.search(r"#?([\d,]+)\s+of\s+([\d,]+)\s+(.+?)\s+in\s+(.+)", s, re.IGNORECASE)
    if m_en_exp:
        pos = int(m_en_exp.group(1).replace(",", ""))
        total = int(m_en_exp.group(2).replace(",", ""))
        cat = m_en_exp.group(3).strip()
        loc = m_en_exp.group(4).strip()
        return pos, total, cat, loc

    # 6. English with 'in': #45 of 466 in Hoi An
    m_en_in = re.search(r"#?([\d,]+)\s+of\s+([\d,]+)\s+in\s+(.+)", s, re.IGNORECASE)
    if m_en_in:
        pos = int(m_en_in.group(1).replace(",", ""))
        total = int(m_en_in.group(2).replace(",", ""))
        loc = m_en_in.group(3).strip()
        return pos, total, None, loc

    # 7. English bare of: #45 of 466 or 45 of 466
    m_bare = re.search(r"#?([\d,]+)\s+of\s+([\d,]+)$", s, re.IGNORECASE)
    if m_bare:
        pos = int(m_bare.group(1).replace(",", ""))
        total = int(m_bare.group(2).replace(",", ""))
        return pos, total, None, None

    # 8. Standard fallback: #45 of 466 places to stay in Hoi An
    m_std = re.search(
        r"#?([\d,]+)\s+of\s+([\d,]+)\s+(?:(?:places to stay|accommodations|things to do|restaurants|hotels)\s+in\s+)?(.+)",
        s,
        re.IGNORECASE,
    )
    if m_std:
        pos = int(m_std.group(1).replace(",", ""))
        total = int(m_std.group(2).replace(",", ""))
        loc = m_std.group(3).strip()
        if loc.lower().startswith("in "):
            loc = loc[3:].strip()
        return pos, total, None, loc

    return None, None, None, None


def parse_review_distribution(raw: Any) -> Optional[ReviewDistribution]:
    """Parse list of {'rating': 'Excellent', 'count': 2252} into ReviewDistribution."""
    if not raw:
        return None

    dist = ReviewDistribution()
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            rating_label = str(item.get("rating", "")).lower().strip()
            count = item.get("count", 0)
            if not isinstance(count, (int, float)):
                continue
            count = int(count)

            if "excellent" in rating_label or "5" in rating_label:
                dist.star_5 = count
            elif "very good" in rating_label or "good" in rating_label or "4" in rating_label:
                dist.star_4 = count
            elif "average" in rating_label or "3" in rating_label:
                dist.star_3 = count
            elif "poor" in rating_label or "2" in rating_label:
                dist.star_2 = count
            elif "terrible" in rating_label or "1" in rating_label:
                dist.star_1 = count
        return dist

    if isinstance(raw, dict):
        for k, v in raw.items():
            k_str = str(k).lower().strip()
            val = int(v) if isinstance(v, (int, float)) else 0
            if "5" in k_str or "excellent" in k_str:
                dist.star_5 = val
            elif "4" in k_str or "good" in k_str:
                dist.star_4 = val
            elif "3" in k_str or "average" in k_str:
                dist.star_3 = val
            elif "2" in k_str or "poor" in k_str:
                dist.star_2 = val
            elif "1" in k_str or "terrible" in k_str:
                dist.star_1 = val
        return dist

    return None


def parse_search_results(data: Dict[str, Any]) -> List[PlaceSummary]:
    """Parse search response containing `places` list into PlaceSummary models."""
    places_raw = data.get("places", [])
    results: List[PlaceSummary] = []

    for item in places_raw:
        if not isinstance(item, dict):
            continue

        hl_raw = item.get("highlighted_review")
        highlighted = None
        if isinstance(hl_raw, dict):
            highlighted = HighlightedReview(
                text=hl_raw.get("text"),
                highlighted_texts=hl_raw.get("highlighted_texts", []),
                mention_count=hl_raw.get("mention_count"),
            )

        rating_float = safe_float(item.get("rating"))
        reviews_int = safe_int(item.get("reviews")) or 0

        summary = PlaceSummary(
            position=int(item.get("position", 0)),
            title=str(item.get("title", "Unknown")),
            place_id=str(item.get("place_id", "")),
            place_type=item.get("place_type"),
            link=item.get("link"),
            serpapi_link=item.get("serpapi_link"),
            rating=rating_float,
            reviews=reviews_int,
            location=item.get("location"),
            thumbnail=item.get("thumbnail"),
            highlighted_review=highlighted,
        )
        results.append(summary)

    return results


def parse_place_details(data: Dict[str, Any], place_id: str) -> PlaceDetail:
    """Parse place response containing `place_result` into a PlaceDetail model."""
    pr = data.get("place_result", {})
    if not pr and "places" in data:
        # If passed a search payload containing one place
        pr = data["places"][0] if data["places"] else {}

    # Ranking parsing
    raw_ranking = pr.get("ranking")
    r_pos, r_total, r_cat, r_loc = parse_ranking_string(raw_ranking)

    # Subratings
    subratings: List[Subrating] = []
    for sr in pr.get("subratings", []):
        if isinstance(sr, dict) and "category" in sr and "score" in sr:
            s_val = safe_float(sr.get("score"))
            if s_val is not None:
                subratings.append(Subrating(category=str(sr["category"]), score=s_val))

    # Price range
    pr_price = pr.get("price_range")
    price_range = None
    if isinstance(pr_price, dict):
        price_range = PriceRange(
            low=safe_float(pr_price.get("low")),
            high=safe_float(pr_price.get("high")),
            currency=pr_price.get("currency", "USD"),
        )

    # Review distribution
    dist = parse_review_distribution(pr.get("review_distribution"))

    # Reviews list
    reviews: List[ReviewItem] = []
    for r in pr.get("reviews_list", []):
        if not isinstance(r, dict):
            continue
        author = None
        a_raw = r.get("author")
        if isinstance(a_raw, dict):
            author = ReviewAuthor(
                username=a_raw.get("username"),
                link=a_raw.get("link"),
                avatar=a_raw.get("avatar"),
                contributions=safe_int(a_raw.get("contributions")) or 0,
                hometown=a_raw.get("hometown"),
            )
        r_score = safe_float(r.get("rating")) or 0.0

        reviews.append(
            ReviewItem(
                title=r.get("title"),
                snippet=r.get("snippet", ""),
                rating=r_score,
                date=r.get("date"),
                link=r.get("link"),
                author=author,
            )
        )

    rating_float = safe_float(pr.get("rating")) or 0.0
    reviews_int = safe_int(pr.get("reviews")) or 0

    return PlaceDetail(
        place_id=str(place_id),
        name=str(pr.get("name") or pr.get("title") or "Unknown Place"),
        place_type=pr.get("type") or pr.get("place_type", "ACCOMMODATION"),
        rating=rating_float,
        reviews=reviews_int,
        ranking=raw_ranking,
        ranking_position=r_pos,
        ranking_total=r_total,
        ranking_category=r_cat,
        ranking_location=r_loc,
        price_range=price_range,
        hotel_stars=safe_float(pr.get("hotel_stars")),
        hotel_class=str(pr.get("hotel_class")) if pr.get("hotel_class") else None,
        hotel_style=pr.get("hotel_style", []),
        languages_spoken=pr.get("languages_spoken", []),
        subratings=subratings,
        amenities=pr.get("amenities", []),
        room_features=pr.get("room_features", []),
        room_types=pr.get("room_types", []),
        address=pr.get("address"),
        gps_coordinates=pr.get("gps_coordinates"),
        walk_score=safe_int(pr.get("walk_score")),
        review_distribution=dist,
        reviews_highlights=pr.get("reviews_highlights", []),
        reviews_list=reviews,
        nearby=pr.get("nearby"),
    )


def audit_review_authenticity(place: PlaceDetail) -> Tuple[float, str]:
    """Audit review author credibility and review curve distribution for authenticity and astroturfing.
    
    Returns:
        (score, verdict) where score is 0.0 - 10.0 (10.0 = highly organic, < 6.0 = elevated risk).
    """
    score = 10.0
    deductions: List[str] = []

    # 1. Author profile check on top reviews
    if place.reviews_list:
        five_star_reviews = [r for r in place.reviews_list if r.rating >= 4.5]
        if len(five_star_reviews) >= 3:
            single_contrib = sum(1 for r in five_star_reviews if r.author and (r.author.contributions or 0) <= 1)
            ratio = single_contrib / len(five_star_reviews)
            if ratio >= 0.7:
                score -= 3.0
                deductions.append(f"Suspicious 5★ Concentration: {int(ratio * 100)}% of top reviews come from single-contribution accounts")
            elif ratio >= 0.4:
                score -= 1.5
                deductions.append("Moderate presence of novice reviewer accounts on top ratings")

    # 2. Distribution polarization check
    if place.review_distribution and place.review_distribution.total >= 20:
        total = place.review_distribution.total
        dist = place.review_distribution
        p5 = dist.star_5 / total
        p1 = dist.star_1 / total
        p_mid = (dist.star_4 + dist.star_3 + dist.star_2) / total
        if p5 >= 0.6 and p1 >= 0.15 and p_mid < 0.12:
            score -= 2.5
            deductions.append("Severe Bimodal Polarization: Disproportionate split between 5★ praise and 1★ complaints with minimal organic middle ground")

    # 3. Overall rating vs subratings disparity
    sub_scores = [sr.score for sr in place.subratings]
    if sub_scores and place.rating:
        avg_sub = sum(sub_scores) / len(sub_scores)
        if place.rating - avg_sub >= 0.7:
            score -= 1.5
            deductions.append(f"Rating Subrating Mismatch: Overall rating ({place.rating}★) sits unusually higher than subrating average ({avg_sub:.1f}★)")

    score = max(1.0, min(10.0, round(score, 1)))
    if score >= 8.5:
        verdict = "High Organic Authenticity: Strong signals of genuine, varied traveler experiences."
    elif score >= 6.5:
        verdict = "Normal Travel Profile: Standard reviewer mix with typical distribution."
    else:
        verdict = f"Caution (Authenticity Risk): {'; '.join(deductions)}"

    return score, verdict


def parse_review_item(r: Dict[str, Any]) -> ReviewItem:
    """Parse a single review dictionary from SerpApi or TripAdvisor into ReviewItem."""
    author = None
    a_raw = r.get("author")
    if isinstance(a_raw, dict):
        author = ReviewAuthor(
            username=a_raw.get("username") or a_raw.get("display_name"),
            link=a_raw.get("link"),
            avatar=a_raw.get("avatar"),
            contributions=safe_int(a_raw.get("contributions")) or 0,
            hometown=a_raw.get("hometown"),
        )
    r_score = safe_float(r.get("rating")) or 0.0

    # Extract trip type if structured
    trip_type = None
    trip_info = r.get("trip_info")
    if isinstance(trip_info, dict):
        trip_type = trip_info.get("type")

    return ReviewItem(
        review_id=str(r.get("review_id") or r.get("id") or ""),
        title=r.get("title"),
        snippet=r.get("snippet") or r.get("text") or "",
        rating=r_score,
        date=r.get("date"),
        link=r.get("link"),
        trip_type=trip_type,
        language=r.get("language") or r.get("original_language"),
        votes=safe_int(r.get("votes")) or 0,
        author=author,
    )


def parse_reviews_response(data: Dict[str, Any]) -> Tuple[List[ReviewItem], Optional[str]]:
    """Parse SerpApi tripadvisor_reviews endpoint response into (reviews, next_page_token/url)."""
    raw_reviews = data.get("reviews", [])
    if not isinstance(raw_reviews, list):
        return [], None
    items = [parse_review_item(r) for r in raw_reviews if isinstance(r, dict)]
    next_url = data.get("serpapi_pagination", {}).get("next")
    return items, next_url
