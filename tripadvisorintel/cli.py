"""Command-line interface for tripadvisor-intel."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional
from .client import TripAdvisorClient
from .doctor import run_doctor
from .cache import cache


def _format_search_table(places) -> str:
    lines = [f"{'#':<3} {'Rating':<8} {'Reviews':<9} {'Title':<40} {'ID':<12} {'Location'}"]
    lines.append("-" * 95)
    for p in places:
        r_str = f"{p.rating}★" if p.rating else "N/A"
        rev_str = f"{p.reviews:,}" if p.reviews else "0"
        title_str = (p.title[:37] + "...") if len(p.title) > 40 else p.title
        loc_str = p.location or ""
        lines.append(f"{p.position:<3} {r_str:<8} {rev_str:<9} {title_str:<40} {p.place_id:<12} {loc_str}")
    return "\n".join(lines)


def _format_place_detail(p) -> str:
    lines = [
        f"================================================================================",
        f"  {p.name} ({p.rating}★ across {p.reviews:,} reviews)",
        f"================================================================================",
        f"Category:     {p.place_type}",
        f"Ranking:      {p.ranking or 'Unranked'}",
        f"Address:      {p.address or 'N/A'}",
    ]
    if p.hotel_stars:
        lines.append(f"Hotel Class:  {p.hotel_stars}★")
    if p.price_range and p.price_range.low:
        lines.append(f"Price Range:  {p.price_range.currency}{p.price_range.low} - {p.price_range.currency}{p.price_range.high}")
    if p.walk_score:
        lines.append(f"Walk Score:   {p.walk_score}/100")

    if p.subratings:
        lines.append("\nSub-ratings:")
        for sr in p.subratings:
            lines.append(f"  - {sr.category:<15}: {sr.score}★")

    if p.review_distribution:
        d = p.review_distribution
        lines.append(f"\nReview Distribution (Total: {d.total:,}):")
        lines.append(f"  5★: {d.star_5:,} | 4★: {d.star_4:,} | 3★: {d.star_3:,} | 2★: {d.star_2:,} | 1★: {d.star_1:,}")

    if p.reviews_list:
        lines.append(f"\nRecent Reviews ({len(p.reviews_list)} loaded):")
        for i, r in enumerate(p.reviews_list[:10], 1):
            date_str = f"[{r.date}] " if r.date else ""
            author_str = f" by {r.author.username}" if r.author and r.author.username else ""
            lines.append(f"  {i}. {date_str}{r.rating}★ {r.title or 'Review'}{author_str}")
            snippet = r.snippet.replace('\n', ' ')
            lines.append(f"     \"{snippet[:140]}...\"")

    return "\n".join(lines)


def _format_dossier(d) -> str:
    lines = [
        f"================================================================================",
        f"  TRAVEL INTELLIGENCE DOSSIER: {d.name}",
        f"================================================================================",
        f"Rating:             {d.rating}★ ({d.review_count:,} reviews)",
        f"Ranking Status:     {d.ranking or 'Unranked'}",
    ]
    if d.rank_percentile:
        lines.append(f"Rank Standing:      Top {d.rank_percentile}% of destination")
    if d.price_range and d.price_range.low:
        lines.append(f"Price Spectrum:     {d.price_range.currency}{d.price_range.low} - {d.price_range.currency}{d.price_range.high}")

    lines.append(f"\n[ VALUE & ROI ANALYSIS ]")
    lines.append(f"Discrepancy Score:  {d.value_discrepancy_score}")
    lines.append(f"Assessment:         {d.value_rating_vs_overall}")

    if d.authenticity_score is not None:
        lines.append(f"\n[ AUTHENTICITY & REVIEW INTEGRITY ]")
        lines.append(f"Authenticity Score: {d.authenticity_score}/10")
        if d.authenticity_assessment:
            lines.append(f"Assessment:         {d.authenticity_assessment}")

    if d.red_flags:
        lines.append(f"\n[ ⚠️ RED FLAGS & ACUTE RISKS ({len(d.red_flags)}) ]")
        for f in d.red_flags:
            lines.append(f"  • [{f.severity.upper()}] ({f.category}): {f.description}")
            if f.evidence_snippet:
                lines.append(f"    Evidence: {f.evidence_snippet}")
    else:
        lines.append(f"\n[ 🛡️ RED FLAGS ]: None detected in review distribution or recent text.")

    if d.key_strengths:
        lines.append(f"\n[ STANDOUT STRENGTHS ]")
        for s in d.key_strengths:
            lines.append(f"  ✓ {s}")

    if d.key_weaknesses:
        lines.append(f"\n[ REPORTED DOWNSIDES & TRADE-OFFS ]")
        for w in d.key_weaknesses:
            lines.append(f"  ✗ {w}")

    if d.persona_fits:
        lines.append(f"\n[ PERSONA SUITABILITY ]")
        for p_name, p_fit in d.persona_fits.items():
            lines.append(f"  • {p_name.upper():<16} Score: {p_fit.score}/10 | {p_fit.recommendation}")

    lines.append(f"\n[ 🎯 WALK-IN STRATEGY & BRIEF ]")
    lines.append(d.walk_in_brief)

    if d.negotiation_baseline:
        lines.append(f"\n[ 💵 NEGOTIATION BASELINE ]")
        lines.append(d.negotiation_baseline)

    lines.append(f"\nConfidence: {d.source_coverage.get('confidence', 0.0) * 100:.0f}% | Generated: {d.generated_at}")
    return "\n".join(lines)


def _write_output(content: str, output_path: Optional[str]) -> None:
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        print(f"Output saved to {output_path}")
    else:
        print(content)


def main() -> int:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--transport",
        choices=["direct_api", "serpapi", "mock"],
        default=None,
        help="Data acquisition transport (default: auto-select with fallback)",
    )
    common_parser.add_argument(
        "--residential-proxy",
        action="store_true",
        help="Route requests via ultra-low-cost-scraper residential proxy pool (DataImpulse)",
    )
    common_parser.add_argument("--proxy", help="Explicit proxy URL (http://user:pass@host:port)")
    common_parser.add_argument("--geo", default="us", help="Target residential proxy egress country (default: us)")

    parser = argparse.ArgumentParser(
        prog="tripadvisor-intel",
        description="Agentic TripAdvisor data acquisition, extraction, and AI reasoning engine.",
        parents=[common_parser],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- search ---
    p_search = subparsers.add_parser("search", parents=[common_parser], help="Search TripAdvisor places by destination or name")
    p_search.add_argument("query", help="Search query (e.g. 'Hoi An hotels', 'Tokyo sushi')")
    p_search.add_argument("--category", "-c", default="all", choices=["hotels", "restaurants", "attractions", "all"], help="Category filter")
    p_search.add_argument("--limit", "-l", type=int, default=15, help="Number of places to return (default: 15)")
    p_search.add_argument("--domain", default="www.tripadvisor.com", help="TripAdvisor regional domain")
    p_search.add_argument("--refresh", action="store_true", help="Bypass cache and force live fetch")
    p_search.add_argument("--json", action="store_true", help="Output raw JSON")
    p_search.add_argument("--output", "-o", help="Save output to file")

    # --- place ---
    p_place = subparsers.add_parser("place", parents=[common_parser], help="Get complete place details, subratings, and reviews")
    p_place.add_argument("target", help="TripAdvisor Place ID or URL")
    p_place.add_argument("--domain", default="www.tripadvisor.com", help="TripAdvisor regional domain")
    p_place.add_argument("--reviews-pages", type=int, default=1, help="Number of review pages to load (default: 1)")
    p_place.add_argument("--refresh", action="store_true", help="Bypass cache and force live fetch")
    p_place.add_argument("--json", action="store_true", help="Output raw JSON")
    p_place.add_argument("--output", "-o", help="Save output to file")

    # --- reason ---
    p_reason = subparsers.add_parser("reason", parents=[common_parser], help="Generate actionable AI travel intelligence dossier")
    p_reason.add_argument("target", help="Place ID, TripAdvisor URL, or property name")
    p_reason.add_argument("--category", default="all", help="Category if searching by name")
    p_reason.add_argument("--persona", default="general", help="Target traveler persona")
    p_reason.add_argument("--domain", default="www.tripadvisor.com", help="TripAdvisor regional domain")
    p_reason.add_argument("--reviews-pages", type=int, default=1, help="Number of review pages to load (default: 1)")
    p_reason.add_argument("--max-reviews", type=int, default=None, help="Maximum reviews to fetch & analyze (e.g. 100, 800)")
    p_reason.add_argument("--refresh", action="store_true", help="Bypass cache and force live fetch")
    p_reason.add_argument("--json", action="store_true", help="Output raw JSON")
    p_reason.add_argument("--output", "-o", help="Save output to file")

    # --- reviews ---
    p_rev = subparsers.add_parser("reviews", parents=[common_parser], help="Fetch paginated reviews with SQLite persistence")
    p_rev.add_argument("target", help="TripAdvisor place ID or URL")
    p_rev.add_argument("--max-reviews", type=int, default=40, help="Maximum reviews to load (default: 40, up to 800+)")
    p_rev.add_argument("--domain", default="www.tripadvisor.com", help="TripAdvisor regional domain")
    p_rev.add_argument("--refresh", action="store_true", help="Bypass local cache and force fresh pagination")
    p_rev.add_argument("--json", action="store_true", help="Output raw JSON")
    p_rev.add_argument("--output", "-o", help="Save output to file")

    # --- doctor ---
    p_doc = subparsers.add_parser("doctor", parents=[common_parser], help="Run system and connectivity diagnostics")
    p_doc.add_argument("--live", action="store_true", help="Perform live endpoint query probe")
    p_doc.add_argument("--json", action="store_true", help="Output raw JSON")
    p_doc.add_argument("--output", "-o", help="Save output to file")

    # --- cache ---
    p_cache = subparsers.add_parser("cache", parents=[common_parser], help="Manage SQLite cache")
    p_cache.add_argument("--clear", action="store_true", help="Purge all cached searches, places, and reports")
    p_cache.add_argument("--stats", action="store_true", default=True, help="Display cache storage statistics")
    p_cache.add_argument("--json", action="store_true", help="Output raw JSON")
    p_cache.add_argument("--output", "-o", help="Save output to file")

    args = parser.parse_args()

    client = TripAdvisorClient(
        transport_mode=args.transport,
        use_residential_proxy=args.residential_proxy,
        proxy_url=args.proxy,
        geo=args.geo,
    )

    if args.command == "search":
        try:
            results = client.search(
                query=args.query,
                category=args.category,
                domain=args.domain,
                limit=args.limit,
                force_refresh=args.refresh,
            )
            out_str = json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False) if args.json else _format_search_table(results)
            _write_output(out_str, args.output)
            return 0
        except Exception as e:
            sys.stderr.write(f"Error during search: {e}\n")
            return 1

    elif args.command == "place":
        try:
            detail = client.get_place(
                target=args.target,
                domain=args.domain,
                reviews_pages=args.reviews_pages,
                force_refresh=args.refresh,
            )
            out_str = json.dumps(detail.model_dump(), indent=2, ensure_ascii=False) if args.json else _format_place_detail(detail)
            _write_output(out_str, args.output)
            return 0
        except Exception as e:
            sys.stderr.write(f"Error fetching place {args.target}: {e}\n")
            return 1

    elif args.command == "reason":
        try:
            dossier = client.analyze(
                target=args.target,
                category=args.category,
                domain=args.domain,
                persona=args.persona,
                reviews_pages=args.reviews_pages,
                max_reviews=args.max_reviews,
                force_refresh=args.refresh,
            )
            out_str = json.dumps(dossier.model_dump(), indent=2, ensure_ascii=False) if args.json else _format_dossier(dossier)
            _write_output(out_str, args.output)
            return 0
        except Exception as e:
            sys.stderr.write(f"Error analyzing {args.target}: {e}\n")
            return 1

    elif args.command == "reviews":
        try:
            revs = client.get_reviews(
                target=args.target,
                max_reviews=args.max_reviews,
                domain=args.domain,
                force_refresh=args.refresh,
            )
            if args.json:
                out_str = json.dumps([r.model_dump() for r in revs], indent=2, ensure_ascii=False)
            else:
                lines = [f"Loaded {len(revs)} reviews for '{args.target}' (SQLite persisted):"]
                for i, r in enumerate(revs, 1):
                    date_str = f"[{r.date}] " if r.date else ""
                    author_str = f" by {r.author.username}" if r.author and r.author.username else ""
                    lines.append(f"  {i}. {date_str}{r.rating}★ {r.title or 'Review'}{author_str}")
                    snippet = r.snippet.replace('\n', ' ')
                    lines.append(f"     \"{snippet[:120]}...\"")
                out_str = "\n".join(lines)
            _write_output(out_str, args.output)
            return 0
        except Exception as e:
            sys.stderr.write(f"Error fetching reviews for {args.target}: {e}\n")
            return 1

    elif args.command == "doctor":
        doc_result = run_doctor(live=args.live)
        if args.json:
            out_str = json.dumps(doc_result, indent=2, ensure_ascii=False)
        else:
            lines = [
                "TripAdvisor Intel Diagnostic Report:",
                f"  Overall Status:  {doc_result['status'].upper()}",
                f"  Python Version:  {doc_result['python_version']}",
                f"  SerpAPI Key:     {'✓ Configured (' + doc_result['keys']['serpapi'].get('masked', '') + ')' if doc_result['keys']['serpapi']['configured'] else '✗ Missing'}",
            ]
            llm_k = doc_result['keys']['llm_reasoning']
            lines.append(f"  LLM Key:         {'✓ ' + llm_k.get('provider', '') + ' (' + llm_k.get('masked', '') + ')' if llm_k.get('configured') else '• Rule-based only'}")
            storage = doc_result['storage']
            lines.append(f"  Storage Status:  {'✓ Writable' if storage.get('writable') else '✗ Read-only or error'}")
            if "stats" in storage:
                s = storage["stats"]
                lines.append(f"  Cache Stats:     {s.get('places_count', 0)} places, {s.get('searches_count', 0)} searches ({s.get('db_size_bytes', 0) / 1024:.1f} KB)")
            for chk in doc_result.get("checks", []):
                lines.append(f"  Live Check:      {chk['name']} -> {'✓ PASSED' if chk.get('passed') else '✗ FAILED'}")
            out_str = "\n".join(lines)
        _write_output(out_str, args.output)
        return 0 if doc_result["status"] in ("healthy", "degraded") else 1

    elif args.command == "cache":
        if args.clear:
            cache.clear()
            print("TripAdvisor cache cleared successfully.")
            return 0
        stats = cache.stats()
        if args.json:
            out_str = json.dumps(stats, indent=2)
        else:
            lines = ["TripAdvisor SQLite Cache Statistics:"]
            for k, v in stats.items():
                lines.append(f"  {k:<20}: {v}")
            out_str = "\n".join(lines)
        _write_output(out_str, args.output)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
