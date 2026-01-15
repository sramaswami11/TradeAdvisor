import sqlite3
import json
import time
from pathlib import Path

DB_PATH = Path("tradeadvisor.db")

def _init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS market_cache (
            ticker TEXT PRIMARY KEY,
            payload TEXT,
            timestamp INTEGER
        )
        """)

_init_db()

# -------- Memory cache --------
_MEMORY_CACHE = {}

def _is_eod_expired(ts: int) -> bool:
    now = time.localtime()
    cached = time.localtime(ts)
    return (now.tm_yday != cached.tm_yday or now.tm_year != cached.tm_year)

def get_cached(ticker: str):
    # Memory
    entry = _MEMORY_CACHE.get(ticker)
    if entry and not _is_eod_expired(entry["timestamp"]):
        return entry["data"]

    # SQLite
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT payload, timestamp FROM market_cache WHERE ticker=?",
            (ticker,)
        ).fetchone()

    if not row:
        return None

    payload, ts = row
    if _is_eod_expired(ts):
        return None

    data = json.loads(payload)
    _MEMORY_CACHE[ticker] = {"data": data, "timestamp": ts}
    return data

def set_cached(ticker: str, data: dict):
    ts = int(time.time())
    payload = json.dumps(data)

    _MEMORY_CACHE[ticker] = {"data": data, "timestamp": ts}

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        INSERT OR REPLACE INTO market_cache (ticker, payload, timestamp)
        VALUES (?, ?, ?)
        """, (ticker, payload, ts))
