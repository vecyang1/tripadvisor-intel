"""Unified reasoning engine for TripAdvisor dossiers."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional
from ..models import PlaceDetail, DossierReport, RedFlagItem
from ..parsers import audit_review_authenticity
from .rules import (
    audit_value_discrepancy,
    scan_red_flags,
    calculate_rank_percentile,
    evaluate_persona_fits,
    generate_walk_in_brief,
)
from .llm import synthesize_with_llm


def generate_dossier(place: PlaceDetail, enable_llm: bool = True) -> DossierReport:
    """Analyze a PlaceDetail and return a complete, actionable DossierReport."""
    # 1. Deterministic Rule Metrics & Authenticity Audit
    disc_score, disc_msg = audit_value_discrepancy(place)
    red_flags = scan_red_flags(place)
    auth_score, auth_assessment = audit_review_authenticity(place)

    if auth_score < 6.5:
        red_flags.append(
            RedFlagItem(
                category="review_manipulation",
                severity="high" if auth_score <= 4.0 else "medium",
                description=f"Authenticity Risk ({auth_score}/10): {auth_assessment}",
                evidence_snippet="Detected via reviewer contribution profile & curve distribution audit."
            )
        )

    rank_pct, rank_summary = calculate_rank_percentile(place)
    persona_fits = evaluate_persona_fits(place, red_flags=red_flags)
    walk_in_brief, negotiation_baseline = generate_walk_in_brief(place, disc_msg, red_flags)

    # 2. Extract baseline strengths and weaknesses from subratings & reviews
    key_strengths = []
    key_weaknesses = []

    sorted_sub = sorted(place.subratings, key=lambda x: x.score, reverse=True)
    if sorted_sub:
        top_sub = sorted_sub[0]
        if top_sub.score >= 4.5:
            key_strengths.append(f"Outstanding {top_sub.category}: Rated {top_sub.score}★ by travelers.")
        low_sub = sorted_sub[-1]
        if low_sub.score < 4.2:
            key_weaknesses.append(f"Lagging {low_sub.category}: Scored lower at {low_sub.score}★ compared to property average.")

    if place.walk_score and place.walk_score >= 85:
        key_strengths.append(f"Prime Walkability: Walk Score of {place.walk_score}/100.")

    if red_flags:
        for rf in red_flags[:3]:
            key_weaknesses.append(f"{rf.description}")

    # 3. Optional LLM Synthesis Enhancement
    llm_data = synthesize_with_llm(place, red_flags) if enable_llm else None
    if llm_data and isinstance(llm_data, dict):
        if llm_data.get("walk_in_brief"):
            walk_in_brief = f"{llm_data['walk_in_brief']}\n\n{walk_in_brief}"
        if llm_data.get("negotiation_baseline"):
            negotiation_baseline = llm_data["negotiation_baseline"]
        if llm_data.get("key_strengths") and isinstance(llm_data["key_strengths"], list):
            key_strengths = list(dict.fromkeys(llm_data["key_strengths"] + key_strengths))
        if llm_data.get("key_weaknesses") and isinstance(llm_data["key_weaknesses"], list):
            key_weaknesses = list(dict.fromkeys(llm_data["key_weaknesses"] + key_weaknesses))

        # Enrich persona fits if available
        if llm_data.get("nomad_verdict") and "solo_nomad" in persona_fits:
            persona_fits["solo_nomad"].recommendation = llm_data["nomad_verdict"]
        if llm_data.get("couple_verdict") and "couples" in persona_fits:
            persona_fits["couples"].recommendation = llm_data["couple_verdict"]

    # 4. Confidence Score Calculation
    reviews_count = place.reviews or 0
    subratings_count = len(place.subratings)
    confidence = 0.5
    if reviews_count >= 500:
        confidence += 0.3
    elif reviews_count >= 50:
        confidence += 0.2
    if subratings_count >= 4:
        confidence += 0.2
    confidence = min(1.0, round(confidence, 2))

    return DossierReport(
        place_id=place.place_id,
        name=place.name,
        category=place.place_type or "ACCOMMODATION",
        rating=place.rating or 0.0,
        review_count=reviews_count,
        ranking=place.ranking,
        rank_percentile=rank_pct,
        price_range=place.price_range,
        value_discrepancy_score=disc_score,
        value_rating_vs_overall=disc_msg,
        authenticity_score=auth_score,
        authenticity_assessment=auth_assessment,
        red_flags=red_flags,
        key_strengths=key_strengths,
        key_weaknesses=key_weaknesses,
        persona_fits=persona_fits,
        walk_in_brief=walk_in_brief,
        negotiation_baseline=negotiation_baseline,
        source_coverage={
            "analyzed_reviews_count": len(place.reviews_list),
            "total_listed_reviews": reviews_count,
            "has_subratings": bool(place.subratings),
            "has_distribution": bool(place.review_distribution),
            "confidence": confidence,
        },
        generated_at=datetime.now().isoformat(),
    )
