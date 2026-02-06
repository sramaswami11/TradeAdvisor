import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "trade_advisor.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


# =========================
# Schema
# =========================
def init_db():
    conn = get_connection()
    c = conn.cursor()

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


def ensure_name_column():
    conn = get_connection()
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in c.fetchall()]
    if "name" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN name TEXT")
    conn.commit()
    conn.close()


# =========================
# Users
# =========================
def create_user(email: str, name: str | None = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (email, name) VALUES (?, ?)",
        (email, name)
    )
    conn.commit()
    conn.close()


def get_user_by_email(email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, email, name FROM users WHERE email = ?",
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
        "SELECT id, email, name FROM users WHERE id = ?",
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
        "SELECT symbol FROM user_tickers WHERE user_id = ? ORDER BY symbol",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def add_ticker_to_user(user_id: int, symbol: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO user_tickers (user_id, symbol) VALUES (?, ?)",
        (user_id, symbol)
    )
    conn.commit()
    conn.close()


def remove_ticker_from_user(user_id: int, symbol: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM user_tickers WHERE user_id = ? AND symbol = ?",
        (user_id, symbol)
    )
    conn.commit()
    conn.close()

def update_user_name_if_missing(user_id: int, name: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        UPDATE users
        SET name = ?
        WHERE id = ? AND (name IS NULL OR name = '')
        """,
        (name, user_id)
    )
    conn.commit()
    conn.close()
