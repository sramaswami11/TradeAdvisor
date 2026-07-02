import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith(("postgres://", "postgresql://")))

if _POSTGRES:
    import psycopg2

_P = "%s" if _POSTGRES else "?"
_DB_PATH = Path(__file__).parent / "trade_advisor.db"


def get_connection():
    if _POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect(_DB_PATH)


# =========================
# Schema
# =========================
def init_db():
    conn = get_connection()
    c = conn.cursor()

    if _POSTGRES:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                digest_opt_in BOOLEAN DEFAULT TRUE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_tickers (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                UNIQUE(user_id, symbol),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        # Migration: add digest_opt_in to existing tables
        c.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS digest_opt_in BOOLEAN DEFAULT TRUE
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                digest_opt_in BOOLEAN DEFAULT 1
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_tickers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                UNIQUE(user_id, symbol),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        # Migration: add digest_opt_in to existing tables
        try:
            c.execute("ALTER TABLE users ADD COLUMN digest_opt_in BOOLEAN DEFAULT 1")
        except Exception:
            pass  # Column already exists

    c.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            timestamp FLOAT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS iv_history (
            symbol TEXT NOT NULL,
            iv FLOAT NOT NULL,
            recorded_at FLOAT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# =========================
# Users
# =========================
def create_user(email: str, name: str | None = None):
    conn = get_connection()
    c = conn.cursor()
    if _POSTGRES:
        c.execute(
            f"INSERT INTO users (email, name) VALUES ({_P}, {_P}) ON CONFLICT (email) DO NOTHING",
            (email, name)
        )
    else:
        c.execute(
            f"INSERT OR IGNORE INTO users (email, name) VALUES ({_P}, {_P})",
            (email, name)
        )
    conn.commit()
    conn.close()


def get_user_by_email(email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        f"SELECT id, email, name, digest_opt_in FROM users WHERE email = {_P}",
        (email,)
    )
    row = c.fetchone()
    conn.close()

    if row:
        return {"id": row[0], "email": row[1], "name": row[2], "digest_opt_in": bool(row[3]) if row[3] is not None else True}
    return None


def get_user_by_id(user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        f"SELECT id, email, name, digest_opt_in FROM users WHERE id = {_P}",
        (user_id,)
    )
    row = c.fetchone()
    conn.close()

    if row:
        return {"id": row[0], "email": row[1], "name": row[2], "digest_opt_in": bool(row[3]) if row[3] is not None else True}
    return None


# =========================
# Tickers
# =========================
def get_all_tickers() -> list[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT symbol FROM user_tickers ORDER BY symbol")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_tickers_for_user(user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        f"SELECT symbol FROM user_tickers WHERE user_id = {_P} ORDER BY symbol",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def add_ticker_to_user(user_id: int, symbol: str):
    conn = get_connection()
    c = conn.cursor()
    if _POSTGRES:
        c.execute(
            f"INSERT INTO user_tickers (user_id, symbol) VALUES ({_P}, {_P}) ON CONFLICT DO NOTHING",
            (user_id, symbol)
        )
    else:
        c.execute(
            f"INSERT OR IGNORE INTO user_tickers (user_id, symbol) VALUES ({_P}, {_P})",
            (user_id, symbol)
        )
    conn.commit()
    conn.close()


def remove_ticker_from_user(user_id: int, symbol: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        f"DELETE FROM user_tickers WHERE user_id = {_P} AND symbol = {_P}",
        (user_id, symbol)
    )
    conn.commit()
    conn.close()


def get_all_users() -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, email, name FROM users WHERE email IS NOT NULL ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "email": r[1], "name": r[2]} for r in rows]


def get_digest_users() -> list[dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, email, name FROM users WHERE email IS NOT NULL AND digest_opt_in = TRUE ORDER BY id"
    )
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "email": r[1], "name": r[2]} for r in rows]


def set_digest_opt_in(user_id: int, opt_in: bool):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        f"UPDATE users SET digest_opt_in = {_P} WHERE id = {_P}",
        (opt_in, user_id)
    )
    conn.commit()
    conn.close()


def update_user_name_if_missing(user_id: int, name: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        f"""
        UPDATE users
        SET name = {_P}
        WHERE id = {_P} AND (name IS NULL OR name = '')
        """,
        (name, user_id)
    )
    conn.commit()
    conn.close()


# =========================
# Cache
# =========================
def get_cache(key: str):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            f"SELECT value, timestamp FROM cache WHERE key = {_P}",
            (key,)
        )
        row = c.fetchone()
        conn.close()
        if row:
            return {"value": row[0], "timestamp": row[1]}
        return None
    except Exception as ex:
        print(f"DB CACHE GET ERROR ({key}):", ex)
        return None


def set_cache(key: str, value: str, timestamp: float):
    try:
        conn = get_connection()
        c = conn.cursor()
        if _POSTGRES:
            c.execute(
                f"""
                INSERT INTO cache (key, value, timestamp)
                VALUES ({_P}, {_P}, {_P})
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, timestamp = EXCLUDED.timestamp
                """,
                (key, value, timestamp)
            )
        else:
            c.execute(
                f"INSERT OR REPLACE INTO cache (key, value, timestamp) VALUES ({_P}, {_P}, {_P})",
                (key, value, timestamp)
            )
        conn.commit()
        conn.close()
    except Exception as ex:
        print(f"DB CACHE SET ERROR ({key}):", ex)


# =========================
# IV History
# =========================
_IV_HISTORY_WINDOW = 365 * 86400  # 52 weeks
_IV_RANK_MIN_SAMPLES = 5


def record_iv(symbol: str, iv: float):
    import time
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            f"INSERT INTO iv_history (symbol, iv, recorded_at) VALUES ({_P}, {_P}, {_P})",
            (symbol.upper(), iv, time.time())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_iv_rank(symbol: str):
    import time
    try:
        conn = get_connection()
        c = conn.cursor()
        cutoff = time.time() - _IV_HISTORY_WINDOW
        c.execute(
            f"""
            SELECT MIN(iv), MAX(iv), COUNT(*), MAX(iv) - MIN(iv)
            FROM iv_history
            WHERE symbol = {_P} AND iv > 0 AND recorded_at > {_P}
            """,
            (symbol.upper(), cutoff)
        )
        row = c.fetchone()
        conn.close()

        if not row or row[2] < _IV_RANK_MIN_SAMPLES:
            return None

        min_iv, max_iv, count, iv_range = row

        if iv_range <= 0:
            return None

        # Fetch the most recent IV reading for this symbol
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            f"""
            SELECT iv FROM iv_history
            WHERE symbol = {_P} AND iv > 0
            ORDER BY recorded_at DESC LIMIT 1
            """,
            (symbol.upper(),)
        )
        latest = c.fetchone()
        conn.close()

        if not latest:
            return None

        current_iv = latest[0]
        iv_rank = (current_iv - min_iv) / iv_range * 100
        return {"iv_rank": round(iv_rank, 1), "sample_count": count}

    except Exception:
        return None
