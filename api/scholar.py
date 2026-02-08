"""
Google Scholar citation count API
Fetches and caches citation count from Google Scholar profile
"""

import os
import sys
import json
import re
import logging
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

# Add api/ directory to sys.path for sibling imports
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, jsonify
from flask_cors import CORS

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

SCHOLAR_USER_ID = "1ckaPgwAAAAJ"
SCHOLAR_URL = f"https://scholar.google.com/citations?user={SCHOLAR_USER_ID}&hl=en"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
FALLBACK_CITATIONS = 1114  # Static fallback value


def _ensure_cache_table(conn):
    """Create the scholar_cache table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scholar_cache (
                key VARCHAR(64) PRIMARY KEY,
                value INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()


def _get_cached(conn):
    """Get cached citation count if still fresh."""
    try:
        _ensure_cache_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value, updated_at FROM scholar_cache WHERE key = %s",
                ("citations",),
            )
            row = cur.fetchone()
            if row:
                from datetime import datetime, timezone

                updated = row["updated_at"]
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - updated).total_seconds()
                if age < CACHE_TTL_SECONDS:
                    return row["value"], False  # value, is_stale
                return row["value"], True  # stale but usable as fallback
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
    return None, True


def _set_cached(conn, value):
    """Update the cached citation count."""
    try:
        _ensure_cache_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scholar_cache (key, value, updated_at)
                   VALUES (%s, %s, NOW())
                   ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = NOW()""",
                ("citations", value, value),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")


def _fetch_scholar_citations():
    """Fetch citation count from Google Scholar profile page."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    req = Request(SCHOLAR_URL, headers=headers)
    try:
        with urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Google Scholar profile page has citation count in the Citations row
        # Look for "Citations" label followed by the first number in gsc_rsb_std cell
        # This is more robust than just taking the first gsc_rsb_std cell
        match = re.search(r'Citations</a></td>\s*<td class="gsc_rsb_std">(\d+)</td>', html)
        if match:
            # This is the "All" citations count (first column after Citations label)
            return int(match.group(1))
    except (URLError, Exception) as e:
        logger.warning(f"Scholar fetch failed: {e}")
    return None


@app.route("/api/scholar", methods=["GET"])
def get_citations():
    """Return the citation count, using cache when possible."""
    from db_utils import get_db_connection

    conn = get_db_connection()
    citations = None
    source = "fallback"

    if conn:
        try:
            cached_value, is_stale = _get_cached(conn)

            if cached_value is not None and not is_stale:
                return jsonify({"citations": cached_value, "source": "cache"})

            # Cache is stale or missing – try fetching fresh data
            fresh = _fetch_scholar_citations()
            if fresh is not None:
                _set_cached(conn, fresh)
                return jsonify({"citations": fresh, "source": "scholar"})

            # Fetch failed – return stale cache if available
            if cached_value is not None:
                citations = cached_value
                source = "stale_cache"
        except Exception as e:
            logger.error(f"Scholar endpoint error: {e}")
        finally:
            conn.close()
    else:
        # No DB available – try direct fetch
        fresh = _fetch_scholar_citations()
        if fresh is not None:
            return jsonify({"citations": fresh, "source": "scholar"})

    if citations is None:
        citations = FALLBACK_CITATIONS
        source = "fallback"

    return jsonify({"citations": citations, "source": source})
