"""Self-diagnostic suite for tripadvisor-intel."""

from __future__ import annotations

import os
import sys
from typing import Dict, Any
from .config import (
    serpapi_api_key,
    vectorengine_api_key,
    google_api_key,
    DB_PATH,
    DATA_DIR,
    ensure_dirs,
)
from .cache import cache


def run_doctor(live: bool = False) -> Dict[str, Any]:
    """Run system diagnostics."""
    results: Dict[str, Any] = {
        "status": "healthy",
        "python_version": sys.version.split()[0],
        "keys": {},
        "storage": {},
        "checks": [],
    }

    # 1. Check Keys
    s_key = serpapi_api_key()
    if s_key:
        masked_s = f"{s_key[:4]}...{s_key[-4:]}" if len(s_key) > 8 else "***"
        results["keys"]["serpapi"] = {"configured": True, "masked": masked_s}
    else:
        results["keys"]["serpapi"] = {"configured": False, "note": "SERPAPI_API_KEY missing"}
        results["status"] = "degraded"

    ve_key = vectorengine_api_key()
    g_key = google_api_key()
    if ve_key:
        masked_ve = f"{ve_key[:6]}...{ve_key[-4:]}"
        results["keys"]["llm_reasoning"] = {"provider": "VectorEngine", "configured": True, "masked": masked_ve}
    elif g_key:
        masked_g = f"{g_key[:6]}...{g_key[-4:]}"
        results["keys"]["llm_reasoning"] = {"provider": "Google Official", "configured": True, "masked": masked_g}
    else:
        results["keys"]["llm_reasoning"] = {"configured": False, "note": "Rule-based reasoning only (LLM key absent)"}

    # 2. Check Storage
    try:
        ensure_dirs()
        stats = cache.stats()
        results["storage"] = {
            "writable": os.access(DATA_DIR, os.W_OK),
            "db_path": str(DB_PATH),
            "stats": stats,
        }
    except Exception as e:
        results["storage"] = {"writable": False, "error": str(e)}
        results["status"] = "unhealthy"

    # 3. Live check if requested
    if live and s_key:
        try:
            from .transports.serpapi import SerpApiTransport
            transport = SerpApiTransport(api_key=s_key, timeout=10)
            probe = transport.search_places("Hoi An", category="hotels", limit=1)
            results["checks"].append({
                "name": "live_serpapi_probe",
                "passed": bool(probe),
                "sample_title": probe[0].title if probe else None
            })
        except Exception as e:
            results["checks"].append({
                "name": "live_serpapi_probe",
                "passed": False,
                "error": str(e)
            })
            results["status"] = "degraded"

    return results
