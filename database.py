#--- database.py ---
import sqlite3
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import json

DB_PATH = "tradeadvisor.db"

# =========================
# Database Initialization
# =========================

def init_db():
    """Initialize database schema"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User tickers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, ticker)
        )
    ''')
    
    # Magic links table (secure token storage)
    c.execute('''
        CREATE TABLE IF NOT EXISTS magic_links (
            token TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT 0
        )
    ''')
    
    # Recommendations history
    c.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create indexes for performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_magic_links_email ON magic_links(email)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_user ON recommendations(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_ticker ON recommendations(ticker)')
    
    conn.commit()
    conn.close()

# =========================
# User Management
# =========================

def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user and their tickers"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM users WHERE email = ? COLLATE NOCASE', (email,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return None
    
    c.execute('SELECT ticker FROM user_tickers WHERE user_id = ?', (user['id'],))
    tickers = [row['ticker'] for row in c.fetchall()]
    
    conn.close()
    
    return {
        'id': user['id'],
        'name': user['name'],
        'email': user['email'],
        'tickers': tickers
    }


def create_user(name: str, email: str, tickers: List[str] = None) -> Optional[int]:
    """Create a new user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
        user_id = c.lastrowid
        
        if tickers:
            for ticker in tickers:
                c.execute('INSERT INTO user_tickers (user_id, ticker) VALUES (?, ?)', 
                         (user_id, ticker.upper()))
        
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def add_ticker_to_user(user_id: int, ticker: str) -> bool:
    """Add a ticker to user's watchlist"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute('INSERT INTO user_tickers (user_id, ticker) VALUES (?, ?)', 
                 (user_id, ticker.upper()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_ticker_from_user(user_id: int, ticker: str) -> bool:
    """Remove a ticker from user's watchlist"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('DELETE FROM user_tickers WHERE user_id = ? AND ticker = ?', 
             (user_id, ticker.upper()))
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    
    return success

# =========================
# Magic Link Management
# =========================

def save_magic_link(token: str, email: str, expires_minutes: int = 15) -> bool:
    """Save magic link with expiration"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    expires_at = datetime.now() + timedelta(minutes=expires_minutes)
    
    try:
        c.execute('''
            INSERT INTO magic_links (token, email, expires_at)
            VALUES (?, ?, ?)
        ''', (token, email, expires_at))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving magic link: {e}")
        return False
    finally:
        conn.close()


def verify_magic_link(token: str) -> Optional[str]:
    """Verify and consume magic link"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Find the link
    c.execute('''
        SELECT * FROM magic_links 
        WHERE token = ? AND used = 0
    ''', (token,))
    
    link = c.fetchone()
    
    if not link:
        conn.close()
        return None
    
    # Check expiration
    expires_at = datetime.fromisoformat(link['expires_at'])
    if datetime.now() > expires_at:
        conn.close()
        return None
    
    # Mark as used
    c.execute('UPDATE magic_links SET used = 1 WHERE token = ?', (token,))
    conn.commit()
    
    email = link['email']
    conn.close()
    
    return email


def cleanup_expired_links():
    """Remove expired magic links (run periodically)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('DELETE FROM magic_links WHERE expires_at < ?', (datetime.now(),))
    deleted = c.rowcount
    
    conn.commit()
    conn.close()
    
    return deleted

# =========================
# Recommendations History
# =========================

def save_recommendation(user_id: int, ticker: str, action: str, 
                       confidence: int, price: float):
    """Save a recommendation to history"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute('''
            INSERT INTO recommendations 
            (user_id, ticker, action, confidence, price)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, ticker, action, confidence, price))
        conn.commit()
    except Exception as e:
        print(f"Error saving recommendation: {e}")
    finally:
        conn.close()


def get_user_recommendation_history(user_id: int, days: int = 30) -> List[Dict]:
    """Get user's recommendation history"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    c.execute('''
        SELECT * FROM recommendations
        WHERE user_id = ? AND timestamp >= ?
        ORDER BY timestamp DESC
    ''', (user_id, cutoff_date))
    
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return results


def get_ticker_recommendation_history(ticker: str, days: int = 30) -> List[Dict]:
    """Get all recommendations for a specific ticker"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    c.execute('''
        SELECT * FROM recommendations
        WHERE ticker = ? AND timestamp >= ?
        ORDER BY timestamp DESC
    ''', (ticker.upper(), cutoff_date))
    
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return results

# =========================
# Migration Helper
# =========================

def migrate_from_json(json_path: str = "ticker_list.json"):
    """Migrate users from JSON file to database"""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        migrated = 0
        for user in data.get('users', []):
            if user.get('name') and user.get('email'):
                user_id = create_user(
                    user['name'], 
                    user['email'], 
                    user.get('tickers', [])
                )
                if user_id:
                    migrated += 1
                    print(f"Migrated user: {user['email']}")
        
        return migrated
    except Exception as e:
        print(f"Migration error: {e}")
        return 0