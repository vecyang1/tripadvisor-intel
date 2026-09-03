"""Model Context Protocol (MCP) server exposing TripAdvisor tools for agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tripadvisorintel.client import TripAdvisorClient
else:
    from .client import TripAdvisorClient


def handle_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an MCP tool call and return structured content."""
    client = TripAdvisorClient()

    if tool_name == "tripadvisor_search":
        query = arguments.get("query", "")
        category = arguments.get("category", "all")
        limit = int(arguments.get("limit", 15))
        domain = arguments.get("domain", "www.tripadvisor.com")
        refresh = bool(arguments.get("refresh", False))

        results = client.search(query=query, category=category, domain=domain, limit=limit, force_refresh=refresh)
        return {
            "places": [r.model_dump() for r in results],
            "count": len(results),
        }

    elif tool_name == "tripadvisor_place_details":
        target = str(arguments.get("place_id") or arguments.get("target", ""))
        domain = arguments.get("domain", "www.tripadvisor.com")
        reviews_pages = int(arguments.get("reviews_pages", 1))
        refresh = bool(arguments.get("refresh", False))

        detail = client.get_place(target=target, domain=domain, reviews_pages=reviews_pages, force_refresh=refresh)
        return detail.model_dump()

    elif tool_name == "tripadvisor_analyze_dossier":
        target = str(arguments.get("target", ""))
        category = arguments.get("category", "all")
        persona = arguments.get("persona", "general")
        domain = arguments.get("domain", "www.tripadvisor.com")
        reviews_pages = int(arguments.get("reviews_pages", 1))
        max_reviews = int(arguments.get("max_reviews", 0)) if arguments.get("max_reviews") else None
        refresh = bool(arguments.get("refresh", False))

        dossier = client.analyze(
            target=target,
            category=category,
            domain=domain,
            persona=persona,
            reviews_pages=reviews_pages,
            max_reviews=max_reviews,
            force_refresh=refresh,
        )
        return dossier.model_dump()

    elif tool_name == "tripadvisor_place_reviews":
        target = str(arguments.get("place_id") or arguments.get("target", ""))
        max_reviews = int(arguments.get("max_reviews", 40))
        domain = arguments.get("domain", "www.tripadvisor.com")
        refresh = bool(arguments.get("refresh", False))

        reviews = client.get_reviews(
            target=target, max_reviews=max_reviews, domain=domain, force_refresh=refresh
        )
        return {
            "place_id": target,
            "count": len(reviews),
            "reviews": [r.model_dump() for r in reviews],
        }

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


TOOL_DEFINITIONS = [
    {
        "name": "tripadvisor_search",
        "description": "Search TripAdvisor for hotels, restaurants, attractions, or destinations. Returns rankings, ratings, place IDs, and thumbnails.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or destination (e.g. 'Hoi An hotels', 'Tokyo omakase')"},
                "category": {"type": "string", "enum": ["hotels", "restaurants", "attractions", "all"], "default": "all"},
                "limit": {"type": "integer", "default": 15},
                "domain": {"type": "string", "default": "www.tripadvisor.com"},
                "refresh": {"type": "boolean", "default": False},
            },
            "required": ["query"],
        },
    },
    {
        "name": "tripadvisor_place_details",
        "description": "Fetch detailed info for a TripAdvisor place by place_id or URL, including ranking (#X of Y), sub-ratings, amenities, walk score, and recent reviews.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "place_id": {"type": "string", "description": "Numeric TripAdvisor place ID or full TripAdvisor URL"},
                "reviews_pages": {"type": "integer", "default": 1, "description": "Number of review pages to load (default: 1, 5-10 reviews/page)"},
                "domain": {"type": "string", "default": "www.tripadvisor.com"},
                "refresh": {"type": "boolean", "default": False},
            },
            "required": ["place_id"],
        },
    },
    {
        "name": "tripadvisor_analyze_dossier",
        "description": "Generate an AI travel intelligence dossier for a place (by name, place_id, or URL), analyzing Value Discrepancy, Review Authenticity, acute Red Flags, traveler persona fit, and walk-in negotiation baselines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "TripAdvisor place ID, full TripAdvisor URL, or business name"},
                "category": {"type": "string", "default": "all"},
                "persona": {"type": "string", "enum": ["solo_nomad", "couples", "family", "general"], "default": "general"},
                "reviews_pages": {"type": "integer", "default": 1, "description": "Number of review pages to load for deep audit"},
                "max_reviews": {"type": "integer", "description": "Optional maximum reviews to paginate and evaluate (e.g. 50, 100, 800)"},
                "domain": {"type": "string", "default": "www.tripadvisor.com"},
                "refresh": {"type": "boolean", "default": False},
            },
            "required": ["target"],
        },
    },
    {
        "name": "tripadvisor_place_reviews",
        "description": "Fetch paginated reviews for a TripAdvisor place with progressive SQLite caching and deduplication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "place_id": {"type": "string", "description": "TripAdvisor numeric place ID or URL"},
                "max_reviews": {"type": "integer", "default": 40, "description": "Maximum reviews to load (default: 40, up to 800+)"},
                "domain": {"type": "string", "default": "www.tripadvisor.com"},
                "refresh": {"type": "boolean", "default": False, "description": "Bypass local cache"},
            },
            "required": ["place_id"],
        },
    },
]


def run_stdio() -> None:
    """Standard JSON-RPC Stdio loop for MCP server."""
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")

            if method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOL_DEFINITIONS}}
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})
                content = handle_call(name, args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(content, ensure_ascii=False, indent=2)}]
                    },
                }
            elif method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "tripadvisor-intel", "version": "1.0.0"},
                        "capabilities": {"tools": {}},
                    },
                }
            else:
                resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio()
