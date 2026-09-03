"""Optional LLM synthesis layer for TripAdvisor intelligence.

Enriches algorithmic reasoning with nuanced Gemini synthesis when API keys are present.
Fail-open architecture: if LLM fails, system continues seamlessly with rule-based outputs.
"""

from __future__ import annotations

import json
from typing import Optional, Dict, Any
from datetime import datetime
from ..models import PlaceDetail, RedFlagItem
from ..config import llm_credentials


PROMPT_TEMPLATE = """You are a senior travel intelligence analyst and negotiation strategist.
Analyze the following TripAdvisor data for a business and produce a concise, high-signal intelligence dossier.

Current Date: {today}
Place Name: {name}
Category: {category}
Overall Rating: {rating}★ ({reviews_count} reviews)
Official Ranking: {ranking}
Price Range: {price_range}
Sub-ratings: {subratings}
Detected Red Flag Patterns: {red_flags}

Sample Recent Reviews:
{reviews}

Provide a JSON object response with the following keys:
{{
  "walk_in_brief": "2-3 sentence executive summary of whether this place is worth it, its real quality tier, and what to expect upon arrival.",
  "negotiation_baseline": "Actionable advice on target walk-in rates, direct discount margin vs OTA commissions, and what free perks/upgrades to request.",
  "key_strengths": ["3-4 bullet points of genuine standouts substantiated by reviews"],
  "key_weaknesses": ["2-3 recurring traveler grievances or trade-offs to be aware of"],
  "nomad_verdict": "Specific advice for solo travelers / digital nomads (WiFi, noise, workspace).",
  "couple_verdict": "Specific advice for couples (ambiance, privacy, romance)."
}}
Respond ONLY with the JSON object.
"""


def synthesize_with_llm(place: PlaceDetail, red_flags: list[RedFlagItem]) -> Optional[Dict[str, Any]]:
    """Synthesize deep reasoning via Gemini / VectorEngine. Returns None on failure."""
    api_key, http_options = llm_credentials()
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key, http_options=http_options)

        subratings_str = ", ".join(f"{sr.category}: {sr.score}★" for sr in place.subratings) or "N/A"
        price_str = f"{place.price_range.currency}{place.price_range.low} - {place.price_range.currency}{place.price_range.high}" if place.price_range and place.price_range.low else "Unlisted"
        flags_str = "; ".join(f"[{f.category.upper()}] {f.description}" for f in red_flags) or "None detected"

        reviews_summary = []
        for i, r in enumerate(place.reviews_list[:6], 1):
            reviews_summary.append(f"{i}. [{r.rating}★ | {r.date or 'recent'}] \"{r.title or ''}\": {r.snippet[:200]}")
        reviews_str = "\n".join(reviews_summary) or "No text reviews available"

        today = datetime.now().strftime("%Y-%m-%d")
        prompt = PROMPT_TEMPLATE.format(
            today=today,
            name=place.name,
            category=place.place_type or "General",
            rating=place.rating or 0.0,
            reviews_count=place.reviews or 0,
            ranking=place.ranking or "Unranked",
            price_range=price_str,
            subratings=subratings_str,
            red_flags=flags_str,
            reviews=reviews_str,
        )

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1000,
                response_mime_type="application/json"
            )
        )
        if resp.text:
            return json.loads(resp.text)
    except Exception:
        # Fail-open guarantee: return None and allow deterministic engine to handle it
        return None

    return None
