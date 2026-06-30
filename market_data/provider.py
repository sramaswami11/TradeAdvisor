# market_data/provider.py
import json
import logging
import os
import threading
import time

import pandas as pd
import yfinance as yf

from database import get_cache, set_cache

logger = logging.getLogger(__name__)

_CACHE_DIR = "/tmp" if os.path.exists("/tmp") else "."
_SNAPSHOT_CACHE_TTL = 900  # 15 minutes — refresh prices during market hours

# Single semaphore shared with options_engine to cap concurrent yfinance calls.
# Both dashboard snapshot fetches and the CSP scanner acquire this before
# calling yfinance, keeping memory within Render's 512 MB free tier.
_yf_semaphore = threading.Semaphore(1)


def _snapshot_cache_path(symbol: str) -> str:
    return os.path.join(_CACHE_DIR, f"snapshot_cache_{symbol}.json")


def _load_snapshot_cache(symbol: str, ignore_ttl: bool = False):
    # Try file cache first (fastest path)
    try:
        path = _snapshot_cache_path(symbol)
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            age = time.time() - data.get("timestamp", 0)
            if ignore_ttl or age < _SNAPSHOT_CACHE_TTL:
                return data["snapshot"]
    except Exception:
        pass

    # Fall back to DB cache (survives Render restarts)
    try:
        row = get_cache(f"snapshot:{symbol}")
        if row:
            age = time.time() - row["timestamp"]
            if ignore_ttl or age < _SNAPSHOT_CACHE_TTL:
                return json.loads(row["value"])
    except Exception:
        pass

    return None


def _save_snapshot_cache(symbol: str, snapshot: dict):
    ts = time.time()
    # Write to file cache
    try:
        path = _snapshot_cache_path(symbol)
        with open(path, "w") as f:
            json.dump({"timestamp": ts, "snapshot": snapshot}, f)
    except Exception:
        pass
    # Write to DB cache (persists across restarts)
    try:
        set_cache(f"snapshot:{symbol}", json.dumps(snapshot), ts)
    except Exception:
        pass


def calculate_rsi(series: pd.Series, period: int = 14) -> float | None:
    if len(series) < period + 1:
        return None

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def safe_float(value):
    try:
        return round(float(value), 2)
    except Exception:
        return None


def fetch_snapshot(symbol: str) -> dict:
    cached = _load_snapshot_cache(symbol)
    if cached is not None:
        return cached

    _yf_semaphore.acquire()
    try:
        logger.info(f"{symbol}: fetching snapshot from yfinance")
        hist = yf.Ticker(symbol).history(period="1y", auto_adjust=True)

        if hist is None or hist.empty or len(hist) < 2:
            raise ValueError(f"Insufficient price history for {symbol}")

        close = hist["Close"]
        last_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])

        change_pct = round((last_close / prev_close - 1) * 100, 2)

        last_ts = hist.index[-1]
        as_of = last_ts.date().isoformat() if hasattr(last_ts, "date") else str(last_ts)[:10]

        snapshot = {
            "symbol": symbol,
            "current_price": safe_float(last_close),
            "change_pct": change_pct,
            "as_of": as_of,
            "dma_50": safe_float(close.rolling(50).mean().iloc[-1]) if len(hist) >= 50 else None,
            "dma_200": safe_float(close.rolling(200).mean().iloc[-1]) if len(hist) >= 200 else None,
            "rsi_14": calculate_rsi(close),
            "52w_high": safe_float(close.tail(252).max()),
            "52w_low": safe_float(close.tail(252).min()),
        }

        _save_snapshot_cache(symbol, snapshot)
        return snapshot

    except Exception as e:
        logger.error(f"{symbol}: snapshot fetch failed → {e}")
        stale = _load_snapshot_cache(symbol, ignore_ttl=True)
        if stale:
            return stale
        return {
            "symbol": symbol,
            "current_price": None,
            "change_pct": None,
            "as_of": None,
            "dma_50": None,
            "dma_200": None,
            "rsi_14": None,
            "52w_high": None,
            "52w_low": None,
        }

    finally:
        _yf_semaphore.release()
