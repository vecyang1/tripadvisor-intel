"""SQLite-backed persistent caching with TTL for TripAdvisor intelligence."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Optional, Dict, Any, List
from .config import DB_PATH, CACHE_ENABLED, CACHE_TTL_HOURS, ensure_dirs


from contextlib import contextmanager

class CacheDB:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_conn(self):
        ensure_dirs()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS searches (
                    cache_key TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    category TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS places (
                    place_id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    report_key TEXT PRIMARY KEY,
                    place_id TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    place_id TEXT NOT NULL,
                    review_id TEXT NOT NULL,
                    rating REAL,
                    title TEXT,
                    snippet TEXT,
                    date TEXT,
                    link TEXT,
                    trip_type TEXT,
                    language TEXT,
                    votes INTEGER DEFAULT 0,
                    author_json TEXT,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (place_id, review_id)
                )
            """)
            conn.commit()

    def _is_expired(self, created_at: int) -> bool:
        if not CACHE_ENABLED:
            return True
        ttl_seconds = CACHE_TTL_HOURS * 3600
        return (time.time() - created_at) > ttl_seconds

    # --- Searches ---
    def get_search(self, query: str, category: str, domain: str = "www.tripadvisor.com") -> Optional[List[Dict[str, Any]]]:
        if not CACHE_ENABLED:
            return None
        cache_key = f"{domain}:{category}:{query.strip().lower()}"
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT response_json, created_at FROM searches WHERE cache_key = ?",
                (cache_key,)
            ).fetchone()
            if row and not self._is_expired(row["created_at"]):
                try:
                    return json.loads(row["response_json"])
                except Exception:
                    return None
        return None

    def set_search(self, query: str, category: str, places: List[Dict[str, Any]], domain: str = "www.tripadvisor.com") -> None:
        if not CACHE_ENABLED:
            return
        cache_key = f"{domain}:{category}:{query.strip().lower()}"
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO searches (cache_key, query, category, domain, response_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cache_key, query, category, domain, json.dumps(places, ensure_ascii=False), int(time.time()))
            )
            conn.commit()

    # --- Places ---
    def get_place(self, place_id: str, domain: str = "www.tripadvisor.com") -> Optional[Dict[str, Any]]:
        if not CACHE_ENABLED:
            return None
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT detail_json, created_at FROM places WHERE place_id = ?",
                (str(place_id),)
            ).fetchone()
            if row and not self._is_expired(row["created_at"]):
                try:
                    return json.loads(row["detail_json"])
                except Exception:
                    return None
        return None

    def set_place(self, place_id: str, detail: Dict[str, Any], domain: str = "www.tripadvisor.com") -> None:
        if not CACHE_ENABLED:
            return
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO places (place_id, domain, detail_json, created_at)
                   VALUES (?, ?, ?, ?)""",
                (str(place_id), domain, json.dumps(detail, ensure_ascii=False), int(time.time()))
            )
            conn.commit()

    # --- Reports ---
    def get_report(self, place_id: str, persona: str = "general") -> Optional[Dict[str, Any]]:
        if not CACHE_ENABLED:
            return None
        report_key = f"{place_id}:{persona}"
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT report_json, created_at FROM reports WHERE report_key = ?",
                (report_key,)
            ).fetchone()
            if row and not self._is_expired(row["created_at"]):
                try:
                    return json.loads(row["report_json"])
                except Exception:
                    return None
        return None

    def set_report(self, place_id: str, persona: str, report: Dict[str, Any]) -> None:
        if not CACHE_ENABLED:
            return
        report_key = f"{place_id}:{persona}"
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO reports (report_key, place_id, persona, report_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (report_key, str(place_id), persona, json.dumps(report, ensure_ascii=False), int(time.time()))
            )
            conn.commit()

    # --- Reviews Cache ---
    def get_reviews(self, place_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            query = "SELECT * FROM reviews WHERE place_id = ? ORDER BY date DESC, created_at DESC"
            params: list = [str(place_id)]
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = {
                    "review_id": row["review_id"],
                    "rating": row["rating"],
                    "title": row["title"],
                    "snippet": row["snippet"],
                    "date": row["date"],
                    "link": row["link"],
                    "trip_type": row["trip_type"],
                    "language": row["language"],
                    "votes": row["votes"],
                    "author": json.loads(row["author_json"]) if row["author_json"] else None,
                }
                results.append(item)
            return results

    def save_reviews(self, place_id: str, reviews: List[Dict[str, Any]]) -> int:
        now = int(time.time())
        inserted = 0
        with self._get_conn() as conn:
            for r in reviews:
                author_json = json.dumps(r.get("author")) if r.get("author") else None
                review_id = str(r.get("review_id") or "")
                if not review_id:
                    import hashlib
                    raw_str = f"{r.get('title')}{r.get('snippet')}{r.get('date')}"
                    review_id = f"hash_{hashlib.sha256(raw_str.encode()).hexdigest()[:16]}"
                cur = conn.execute(
                    """
                    INSERT OR REPLACE INTO reviews (
                        place_id, review_id, rating, title, snippet, date, link, trip_type, language, votes, author_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(place_id),
                        review_id,
                        r.get("rating") or 0.0,
                        r.get("title"),
                        r.get("snippet") or "",
                        r.get("date"),
                        r.get("link"),
                        r.get("trip_type"),
                        r.get("language"),
                        r.get("votes") or 0,
                        author_json,
                        now,
                    )
                )
                if cur.rowcount > 0:
                    inserted += 1
            conn.commit()
        return inserted

    def count_reviews(self, place_id: str) -> int:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM reviews WHERE place_id = ?", (str(place_id),))
            return cur.fetchone()[0]

    # --- Management ---
    def clear(self) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM searches")
            conn.execute("DELETE FROM places")
            conn.execute("DELETE FROM reports")
            conn.execute("DELETE FROM reviews")
            conn.commit()

    def stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            s_count = conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0]
            p_count = conn.execute("SELECT COUNT(*) FROM places").fetchone()[0]
            r_count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            rev_count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            return {
                "searches_count": s_count,
                "places_count": p_count,
                "reports_count": r_count,
                "reviews_count": rev_count,
                "db_size_bytes": db_size,
                "ttl_hours": CACHE_TTL_HOURS,
                "cache_enabled": CACHE_ENABLED,
            }


# Default singleton
cache = CacheDB()
