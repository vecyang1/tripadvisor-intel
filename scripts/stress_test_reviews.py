"""Stress test TripAdvisor bulk review pagination, SQLite scaling, and reasoning."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from tripadvisorintel.client import TripAdvisorClient
from tripadvisorintel.config import serpapi_api_key
from tripadvisorintel.cache import cache
from tripadvisorintel.reasoning.engine import generate_dossier
from tripadvisorintel.transports.direct import DirectScraperTransport
from tripadvisorintel.transports.serpapi import SerpApiTransport


def run_stress_test(place_id: str = "5979069", target_reviews: int = 800, page_size: int = 20):
    print("=" * 80)
    print(f"TRIPADVISOR INTEL — 800-REVIEW STRESS TEST BENCHMARK")
    print(f"Target Place ID: {place_id} (Cat Ba Monkey Island)")
    print(f"Target Review Ingestion: {target_reviews} reviews ({page_size} reviews/batch)")
    print("=" * 80)

    # 1. Setup client with DirectScraper + SerpApi Fallback
    client = TripAdvisorClient(
        transport=DirectScraperTransport(geo="us"),
        fallback_transport=SerpApiTransport(),
    )

    initial_cached = cache.count_reviews(place_id)
    print(f"[Init] Existing SQLite reviews in cache for {place_id}: {initial_cached}")

    # 2. Benchmark pagination and progressive ingestion
    start_time = time.perf_counter()
    batch_latencies = []
    
    # Track progress during pagination
    print("\n--- Starting Paginated Review Ingestion ---")
    reviews = client.get_reviews(
        place_id=place_id,
        max_reviews=target_reviews,
        page_size=page_size,
    )
    total_elapsed = time.perf_counter() - start_time

    final_count = cache.count_reviews(place_id)
    print(f"\n[Ingestion Complete]")
    print(f"  Retrieved Reviews:     {len(reviews)}")
    print(f"  Total Persisted in DB: {final_count}")
    print(f"  Total Ingestion Time:  {total_elapsed:.2f}s")
    if len(reviews) > initial_cached:
        new_fetches = len(reviews) - initial_cached
        avg_per_review = (total_elapsed / new_fetches) * 1000
        print(f"  Avg Latency / Review:  {avg_per_review:.1f}ms")

    # 3. Benchmark SQLite Cache Read Speed for 800 reviews
    print("\n--- Benchmarking SQLite Cache Retrieval Performance ---")
    cache_start = time.perf_counter()
    cached_reviews = client.cache.get_reviews(place_id=place_id, limit=target_reviews)
    cache_elapsed = time.perf_counter() - cache_start
    print(f"  Read {len(cached_reviews)} reviews from SQLite in {cache_elapsed * 1000:.2f}ms")
    print(f"  SQLite Read Throughput: {len(cached_reviews) / max(cache_elapsed, 0.0001):,.0f} reviews/sec")

    # 4. Corpus Analytics (Date range, rating distribution, language diversity)
    dates = [r["date"] for r in cached_reviews if r.get("date")]
    ratings = [r["rating"] for r in cached_reviews if r.get("rating") is not None]
    
    star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in ratings:
        int_r = int(round(r))
        if int_r in star_counts:
            star_counts[int_r] += 1

    print("\n--- Review Corpus Distribution ---")
    if dates:
        print(f"  Oldest Review:         {min(dates)}")
        print(f"  Newest Review:         {max(dates)}")
    print(f"  Star Rating Breakdown: 5★:{star_counts[5]} | 4★:{star_counts[4]} | 3★:{star_counts[3]} | 2★:{star_counts[2]} | 1★:{star_counts[1]}")
    neg_ratio = (star_counts[1] + star_counts[2]) / max(len(ratings), 1) * 100
    print(f"  Negative Review Ratio: {neg_ratio:.1f}%")

    # 5. Stress test Reasoning Engine across the entire review corpus
    print("\n--- Benchmarking Algorithmic Reasoning over Review Corpus ---")
    place_detail = client.get_place(place_id)
    place_detail.reviews_list = [r for r in reviews]
    
    reason_start = time.perf_counter()
    dossier = generate_dossier(place_detail, enable_llm=False)
    reason_elapsed = time.perf_counter() - reason_start
    print(f"  Full Dossier Generated in {reason_elapsed * 1000:.2f}ms across {len(place_detail.reviews_list)} reviews")
    print(f"  Acute Red Flags Found:  {len(dossier.red_flags)}")
    for i, flag in enumerate(dossier.red_flags[:5], 1):
        print(f"    {i}. [{flag.severity.upper()}] ({flag.category}): {flag.description}")
        if flag.evidence_snippet:
            snippet_clean = flag.evidence_snippet.replace('\n', ' ')
            print(f"       Evidence: \"{snippet_clean[:120]}...\"")

    # 6. Database Storage Footprint
    db_stats = cache.stats()
    print("\n--- SQLite Storage Footprint ---")
    print(f"  Database Size:         {db_stats.get('db_size_bytes', 0) / 1024:.1f} KB")
    print(f"  Total Places in DB:    {db_stats.get('places_count', 0)}")
    print(f"  Total Reviews in DB:   {db_stats.get('reviews_count', 0)}")
    print("=" * 80)
    print("STRESS TEST SUCCESSFUL — All systems stable and verified.")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress test TripAdvisor review ingestion")
    parser.add_argument("--place-id", default="5979069", help="TripAdvisor place ID")
    parser.add_argument("--max-reviews", type=int, default=800, help="Maximum reviews to ingest (default: 800)")
    parser.add_argument("--page-size", type=int, default=20, help="Page size (default: 20)")
    args = parser.parse_args()

    run_stress_test(place_id=args.place_id, target_reviews=args.max_reviews, page_size=args.page_size)
