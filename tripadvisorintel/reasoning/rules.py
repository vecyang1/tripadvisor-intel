"""First-principles algorithmic reasoning and audit metrics for TripAdvisor data."""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple
from ..models import (
    PlaceDetail,
    RedFlagItem,
    PersonaFitScore,
    PriceRange,
)

RED_FLAG_PATTERNS = {
    "cleanliness": [
        (re.compile(r"\b(bed\s*bugs?|fleas?|ticks?)\b", re.I), "high", "Bed bugs / insect infestation reported in reviews."),
        (re.compile(r"\b(mould|mold|damp|mildew)\b", re.I), "medium", "Reports of dampness or mold in rooms."),
        (re.compile(r"\b(cockroach(es)?|roach(es)?|rats?|mice)\b", re.I), "high", "Pest issues (cockroaches/rodents) noted by guests."),
        (re.compile(r"\b(filthy|stained\s+sheets?|dirty\s+towels?|dirty\s+bathroom)\b", re.I), "medium", "Cleanliness and housekeeping hygiene lapses."),
        (re.compile(r"\b(sewage|smelly|foul\s+odor|stink)\b", re.I), "medium", "Foul odor or plumbing/sewage smell mentioned."),
    ],
    "noise": [
        (re.compile(r"\b(construction\s+noise|drilling|heavy\s+machinery)\b", re.I), "high", "Nearby construction noise disrupting rest."),
        (re.compile(r"\b(paper\s*thin\s+walls?|loud\s+neighbors?|hear\s+everything)\b", re.I), "medium", "Poor acoustic insulation / paper-thin walls."),
        (re.compile(r"\b(rooftop\s+bar\s+noise|nightclub|club\s+music|thumping\s+bass)\b", re.I), "medium", "Late-night music or bar bass vibration."),
    ],
    "scam_and_billing": [
        (re.compile(r"\b(scam|rip\s*off|con\s*artists?|cheated)\b", re.I), "high", "Explicit allegations of scams or being cheated."),
        (re.compile(r"\b(deposit\s+not\s+returned|stole\s+my\s+deposit|kept\s+deposit)\b", re.I), "high", "Deposit retention or return disputes."),
        (re.compile(r"\b(double\s+charged|unauthorized\s+charge|hidden\s+fees?)\b", re.I), "medium", "Billing discrepancies or unexpected hidden fees."),
        (re.compile(r"\b(taxi\s+scam|rigged\s+meter|commission\s+kickback)\b", re.I), "medium", "Associated transport or commission kickback warnings."),
    ],
    "service_and_safety": [
        (re.compile(r"\b(theft|stolen|robbed|break\s*in)\b", re.I), "high", "Guest room theft or safety incidents reported."),
        (re.compile(r"\b(aggressive|shouted\s+at|threatened|hostile\s+staff)\b", re.I), "high", "Hostile or threatening staff behavior reported."),
    ],
    "bait_and_switch": [
        (re.compile(r"\b(bait\s*and\s*switch|not\s+(?:the\s+)?room\s+pictured|downgraded|fake\s+photos?|misleading\s+photos?|moved\s+us\s+to\s+(?:another|different)\s+(?:building|hotel|annex))\b", re.I), "high", "Bait-and-switch room allocation or misleading photos."),
    ],
    "food_and_hygiene": [
        (re.compile(r"\b(food\s+poisoning|vomiting|diarrhea|salmonella|sick\s+from\s+the\s+(?:food|breakfast|buffet)|stomach\s+bug|hair\s+in\s+(?:my\s+)?food)\b", re.I), "high", "Food poisoning or severe culinary hygiene hazards."),
    ],
    "infrastructure_failure": [
        (re.compile(r"\b(?:aircon|air\s*con|air\s*conditioning|a\s*/\s*c)\s+(?:was\s+|is\s+)?(?:broken|didn['’]?t\s+work|not\s+working|hot\s+air|leaking)\b|\bno\s+air\s*conditioning\b|\bno\s+a\s*/\s*c\b", re.I), "high", "Air conditioning failure / inoperable cooling."),
        (re.compile(r"\b(no\s+hot\s+water|freezing\s+shower|cold\s+shower\s+only)\b", re.I), "medium", "Water heater failure / no hot water."),
        (re.compile(r"\b(blackout|power\s+cut|no\s+electricity|flooded\s+bathroom|broken\s+toilet|clogged\s+toilet)\b", re.I), "medium", "Severe infrastructure, electrical, or plumbing outage."),
    ],
    "wifi_and_connectivity": [
        (re.compile(r"\b(unusable\s+wi\s*[-]?fi|no\s+wi\s*[-]?fi|wi\s*[-]?fi\s+(?:didn['’]?t\s+work|broken|terrible|slow|kept\s+dropping)|no\s+internet)\b", re.I), "medium", "Severe Wi-Fi connectivity degradation."),
    ],
    "review_manipulation": [
        (re.compile(r"\b(bribed?|bribe|offered\s+(?:free\s+drinks?|discount)\s+for\s+(?:a\s+)?5\s*[-]?star|forced\s+to\s+write\s+(?:a\s+)?review|watched\s+me\s+write\s+(?:the\s+)?review)\b", re.I), "high", "Review bribery or on-site coercion for 5-star ratings."),
    ],
}


def audit_value_discrepancy(place: PlaceDetail) -> Tuple[float, str]:
    """Calculate the discrepancy between Overall Rating and Value Subrating.

    Returns:
        (discrepancy_score, description)
        discrepancy_score > 0 means overall rating is significantly higher than perceived value (overpriced).
        discrepancy_score < 0 means perceived value exceeds overall rating (bargain / high ROI).
    """
    overall = place.rating or 0.0
    value_subrating: Optional[float] = None
    for sr in place.subratings:
        if sr.category.lower() == "value":
            value_subrating = sr.score
            break

    if value_subrating is None or overall == 0.0:
        return 0.0, "Value subrating not available"

    diff = round(overall - value_subrating, 2)
    if diff >= 1.0:
        return diff, f"Severe Overpricing / Brand Trap: Overall rating ({overall}★) vastly exceeds Value ({value_subrating}★). Significant markups or hidden fees."
    elif diff >= 0.5:
        return diff, f"Luxury/Brand Surcharge: Overall rating ({overall}★) is much higher than Value ({value_subrating}★). Incidental pricing likely steep."
    elif diff >= 0.3:
        return diff, f"Mild Premium: Guests love the property ({overall}★), but feel it is slightly overpriced for what is delivered ({value_subrating}★)."
    elif diff <= -0.3:
        return diff, f"Exceptional Value: Guests rate the value ({value_subrating}★) higher than average expectations ({overall}★). High bang-for-buck."
    else:
        return diff, f"Fair Value Alignment: Overall rating ({overall}★) matches perceived value ({value_subrating}★) closely."


def scan_red_flags(place: PlaceDetail) -> List[RedFlagItem]:
    """Inspect all reviews and text snippets for acute red flags."""
    flags: List[RedFlagItem] = []
    seen_descriptions = set()

    for review in place.reviews_list:
        text = f"{review.title or ''} {review.snippet}"
        for cat, patterns in RED_FLAG_PATTERNS.items():
            for regex, severity, desc in patterns:
                m = regex.search(text)
                if m and desc not in seen_descriptions:
                    seen_descriptions.add(desc)
                    # Extract snippet context window around match
                    start = max(0, m.start() - 40)
                    end = min(len(text), m.end() + 60)
                    snippet = text[start:end].strip()
                    flags.append(
                        RedFlagItem(
                            category=cat,
                            severity=severity,
                            description=desc,
                            evidence_snippet=f"...{snippet}..."
                        )
                    )

    # Check high negative review ratio in distribution
    if place.review_distribution:
        neg_ratio = place.review_distribution.negative_ratio
        if neg_ratio >= 0.08:
            flags.append(
                RedFlagItem(
                    category="reputation_drift",
                    severity="high",
                    description=f"Elevated Negative Review Ratio: {round(neg_ratio * 100, 1)}% of all ratings are 1★ or 2★.",
                    evidence_snippet=f"1★: {place.review_distribution.star_1}, 2★: {place.review_distribution.star_2} out of {place.review_distribution.total} ratings."
                )
            )
        elif neg_ratio >= 0.04:
            flags.append(
                RedFlagItem(
                    category="reputation_drift",
                    severity="medium",
                    description=f"Moderate Dissatisfaction: {round(neg_ratio * 100, 1)}% of ratings are 1★ or 2★.",
                    evidence_snippet=f"1★: {place.review_distribution.star_1}, 2★: {place.review_distribution.star_2} total."
                )
            )

    return flags


def calculate_rank_percentile(place: PlaceDetail) -> Tuple[Optional[float], str]:
    """Calculate relative percentile in city (Top X%)."""
    if place.ranking_position and place.ranking_total and place.ranking_total > 0:
        percentile = round((place.ranking_position / place.ranking_total) * 100, 1)
        if percentile <= 5.0:
            summary = f"Top {percentile}% (Rank #{place.ranking_position} of {place.ranking_total}) - Elite Tier in destination."
        elif percentile <= 20.0:
            summary = f"Top {percentile}% (Rank #{place.ranking_position} of {place.ranking_total}) - Strong market contender."
        elif percentile <= 50.0:
            summary = f"Rank #{place.ranking_position} of {place.ranking_total} (Top {percentile}%) - Mid-tier offering."
        else:
            summary = f"Rank #{place.ranking_position} of {place.ranking_total} (Bottom {100 - percentile}%) - Lags behind market leaders."
        return percentile, summary

    return None, place.ranking or "Ranking information unlisted"


def evaluate_persona_fits(place: PlaceDetail, red_flags: Optional[List[RedFlagItem]] = None) -> Dict[str, PersonaFitScore]:
    """Evaluate suitability for various traveler personas based on evidence and detected red flags."""
    sub_map = {sr.category.lower(): sr.score for sr in place.subratings}
    cleanliness = sub_map.get("cleanliness", place.rating or 4.0)
    location = sub_map.get("location", place.rating or 4.0)
    service = sub_map.get("service", place.rating or 4.0)
    value = sub_map.get("value", place.rating or 4.0)
    sleep = sub_map.get("sleep quality", place.rating or 4.0)

    # 1. Solo Digital Nomad
    nomad_score = round(min(10.0, (cleanliness * 0.5 + location * 0.6 + sleep * 0.5 + value * 0.4)), 1)
    nomad_pros = []
    nomad_cons = []
    if location >= 4.5:
        nomad_pros.append("High walkability / central location makes local cafe and dining hops effortless.")
    if sleep >= 4.5:
        nomad_pros.append("High sleep score indicates quiet nights conducive to focused deep work.")
    if value < 4.0:
        nomad_cons.append("Value rating under 4.0★ makes it less viable for extended monthly stays.")

    # 2. Couples / Romance
    couple_score = round(min(10.0, (cleanliness * 0.6 + service * 0.6 + location * 0.5 + sleep * 0.3)), 1)
    couple_pros = []
    couple_cons = []
    if service >= 4.7 and cleanliness >= 4.7:
        couple_pros.append("Exceptional service and spotless cleanliness match boutique getaway standards.")
    if "Pool" in [a.get("name") for a in place.amenities]:
        couple_pros.append("On-site pool provides resort ambiance.")

    # 3. Family with Kids
    family_score = round(min(10.0, (cleanliness * 0.7 + service * 0.5 + location * 0.4 + value * 0.4)), 1)
    family_pros = []
    family_cons = []
    if cleanliness >= 4.8:
        family_pros.append("High hygiene scores are reassuring for young children.")
    if place.walk_score and place.walk_score >= 80:
        family_pros.append(f"Walk Score {place.walk_score}/100: Stroller and pedestrian-friendly surroundings.")

    # 4. Penalties for detected red flags
    if red_flags:
        for rf in red_flags:
            cat = rf.category.lower()
            if cat == "cleanliness" and rf.severity == "high":
                nomad_score = max(1.0, round(nomad_score - 2.0, 1))
                couple_score = max(1.0, round(couple_score - 3.0, 1))
                family_score = max(1.0, round(family_score - 3.5, 1))
                family_cons.append(f"Hygiene Risk: {rf.description}")
            elif cat in ("noise", "wifi_and_connectivity") and rf.severity in ("high", "medium"):
                nomad_score = max(1.0, round(nomad_score - 2.5, 1))
                nomad_cons.append(f"Work Disruption: {rf.description}")
            elif cat == "food_and_hygiene":
                family_score = max(1.0, round(family_score - 3.0, 1))
                couple_score = max(1.0, round(couple_score - 2.0, 1))
                family_cons.append(f"Culinary Warning: {rf.description}")
            elif cat in ("scam_and_billing", "bait_and_switch"):
                couple_score = max(1.0, round(couple_score - 2.0, 1))
                nomad_score = max(1.0, round(nomad_score - 1.5, 1))
                couple_cons.append(f"Trust Caveat: {rf.description}")
            elif cat == "infrastructure_failure" and rf.severity == "high":
                nomad_score = max(1.0, round(nomad_score - 2.0, 1))
                couple_score = max(1.0, round(couple_score - 2.5, 1))
                family_score = max(1.0, round(family_score - 2.5, 1))
                nomad_cons.append(f"Amenity Outage: {rf.description}")

    # Recommendations based on final scores
    if nomad_score >= 8.0:
        nomad_rec = "Recommended for remote workers and solo travelers."
    elif nomad_score >= 5.0:
        nomad_rec = "Viable short stay, check desk setup and quietness."
    else:
        nomad_rec = "Caution advised for remote work: Low hygiene, poor sleep, noise, or Wi-Fi deficits."

    if couple_score >= 8.5:
        couple_rec = "Prime pick for couples seeking relaxation and pampering."
    elif couple_score >= 5.0:
        couple_rec = "Solid couples stay; verify room privacy and noise levels."
    else:
        couple_rec = "Caution advised for romantic stays: Cleanliness, service, or trust deficits reported."

    if family_score >= 8.0:
        family_rec = "Well suited for family vacations."
    elif family_score >= 5.0:
        family_rec = "Adequate for families, but check room layout options and child-friendly amenities."
    else:
        family_rec = "Caution advised for families: Cleanliness, food hygiene, or safety falls below family standards."

    return {
        "solo_nomad": PersonaFitScore(persona="solo_nomad", score=nomad_score, pros=nomad_pros, cons=nomad_cons, recommendation=nomad_rec),
        "couples": PersonaFitScore(persona="couples", score=couple_score, pros=couple_pros, cons=couple_cons, recommendation=couple_rec),
        "family": PersonaFitScore(persona="family", score=family_score, pros=family_pros, cons=family_cons, recommendation=family_rec),
    }


def generate_walk_in_brief(place: PlaceDetail, value_msg: str, red_flags: List[RedFlagItem]) -> Tuple[str, str]:
    """Generate executive walk-in brief and negotiation baseline."""
    price_info = ""
    baseline = ""
    if place.price_range and place.price_range.low and place.price_range.high:
        curr = place.price_range.currency or "$"
        low, high = place.price_range.low, place.price_range.high
        price_info = f"Public rates fluctuate between {curr}{low} - {curr}{high}."
        target_walk_in = round(low * 0.85, 0)
        baseline = (
            f"Target Walk-in / Direct Booking Rate: ~{curr}{target_walk_in} - {curr}{low} per night. "
            f"Hotels pay 15-22% OTA commissions (Booking/Agoda/TripAdvisor partners). "
            f"If walking in or contacting direct front-desk via WhatsApp/Zalo, ask for the net OTA discount or complimentary breakfast/room upgrade."
        )
    else:
        baseline = (
            "No public base price detected. Mention online aggregator rates and negotiate for at least a 10-15% direct booking concession "
            "or an included room upgrade."
        )

    brief_parts = [
        f"**{place.name}** ({place.rating}★ across {place.reviews:,} reviews).",
        f"**Ranking:** {place.ranking or 'Unranked'}.",
        f"**Price Dynamic:** {price_info} {value_msg}",
    ]

    if red_flags:
        high_flags = [f.description for f in red_flags if f.severity == "high"]
        if high_flags:
            brief_parts.append(f"**Critical Caveats:** {' | '.join(high_flags)}")

    walk_in_brief = "\n".join(brief_parts)
    return walk_in_brief, baseline
