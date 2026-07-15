# market_data/provider.py
import json
import logging
import math
import os
import threading
import time

import pandas as pd
import yfinance as yf

from database import get_cache, set_cache, record_iv

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


def calculate_realized_vol(close: pd.Series, window: int = 30) -> float | None:
    if len(close) < window + 1:
        return None
    log_returns = close.pct_change().dropna()
    if len(log_returns) < window:
        return None
    return round(float(log_returns.tail(window).std() * math.sqrt(252)), 6)


def _pct(value):
    try:
        return round(float(value) * 100, 1)
    except Exception:
        return None


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

        recent_vol = calculate_realized_vol(close)
        prior_slice = close.iloc[-61:-30] if len(close) >= 61 else None
        prior_vol = calculate_realized_vol(prior_slice) if prior_slice is not None and len(prior_slice) >= 31 else None
        if recent_vol and prior_vol:
            if recent_vol < prior_vol * 0.9:
                vol_direction = "declining"
            elif recent_vol > prior_vol * 1.1:
                vol_direction = "rising"
            else:
                vol_direction = "stable"
        else:
            vol_direction = None

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
            "realized_vol": recent_vol,
            "vol_direction": vol_direction,
        }

        _save_snapshot_cache(symbol, snapshot)

        try:
            if recent_vol:
                record_iv(symbol, recent_vol)
        except Exception:
            pass

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


_FUNDAMENTALS_CACHE_TTL = 4 * 3600  # 4 hours


def _load_fundamentals_cache(symbol: str):
    try:
        row = get_cache(f"fundamentals:{symbol}")
        if row:
            age = time.time() - row["timestamp"]
            if age < _FUNDAMENTALS_CACHE_TTL:
                return json.loads(row["value"])
    except Exception:
        pass
    return None


def _save_fundamentals_cache(symbol: str, data: dict):
    try:
        set_cache(f"fundamentals:{symbol}", json.dumps(data), time.time())
    except Exception:
        pass


def fetch_fundamentals(symbol: str) -> dict:
    cached = _load_fundamentals_cache(symbol)
    if cached is not None:
        return cached

    _yf_semaphore.acquire()
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        eps_estimate = None
        eps_actual = None
        eps_surprise_pct = None
        try:
            ed = ticker.earnings_dates
            if ed is not None and not ed.empty:
                past = ed[ed.index < pd.Timestamp.now(tz="UTC")]
                if not past.empty:
                    row = past.iloc[0]
                    eps_estimate = safe_float(row.get("EPS Estimate"))
                    eps_actual = safe_float(row.get("Reported EPS"))
                    eps_surprise_pct = safe_float(row.get("Surprise(%)"))
        except Exception:
            pass

        result = {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "gross_margins": _pct(info.get("grossMargins")),
            "operating_margins": _pct(info.get("operatingMargins")),
            "revenue_growth": _pct(info.get("revenueGrowth")),
            "earnings_growth": _pct(info.get("earningsQuarterlyGrowth")),
            "trailing_eps": safe_float(info.get("trailingEps")),
            "forward_eps": safe_float(info.get("forwardEps")),
            "eps_estimate": eps_estimate,
            "eps_actual": eps_actual,
            "eps_surprise_pct": eps_surprise_pct,
        }

        _save_fundamentals_cache(symbol, result)
        return result
    except Exception as e:
        logger.error(f"{symbol}: fundamentals fetch failed → {e}")
        return {}
    finally:
        _yf_semaphore.release()
