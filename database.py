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
                name TEXT
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
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT
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
        f"SELECT id, email, name FROM users WHERE email = {_P}",
        (email,)
    )
    row = c.fetchone()
    conn.close()

    if row:
        return {"id": row[0], "email": row[1], "name": row[2]}
    return None


def get_user_by_id(user_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        f"SELECT id, email, name FROM users WHERE id = {_P}",
        (user_id,)
    )
    row = c.fetchone()
    conn.close()

    if row:
        return {"id": row[0], "email": row[1], "name": row[2]}
    return None


# =========================
# Tickers
# =========================
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
