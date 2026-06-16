# market_data/provider.py
import json
import logging
import os
import time

import pandas as pd
import requests

logger = logging.getLogger(__name__)

EOD_API_KEY = os.getenv("EODHD_API_KEY")
if not EOD_API_KEY:
    raise RuntimeError("EODHD_API_KEY environment variable not set")

BASE_URL = "https://eodhd.com/api/eod"

_CACHE_DIR = "/tmp" if os.path.exists("/tmp") else "."
_SNAPSHOT_CACHE_TTL = 4 * 3600  # 4 hours — EOD data changes once per day


def _snapshot_cache_path(symbol: str) -> str:
    return os.path.join(_CACHE_DIR, f"snapshot_cache_{symbol}.json")


def _load_snapshot_cache(symbol: str):
    try:
        path = _snapshot_cache_path(symbol)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        age = time.time() - data.get("timestamp", 0)
        if age < _SNAPSHOT_CACHE_TTL:
            logger.warning(f"{symbol}: snapshot cache hit (age={int(age)}s)")
            return data["snapshot"]
        logger.warning(f"{symbol}: snapshot cache expired (age={int(age)}s)")
        return None
    except Exception as ex:
        logger.error(f"{symbol}: snapshot cache load error: {ex}")
        return None


def _save_snapshot_cache(symbol: str, snapshot: dict):
    try:
        path = _snapshot_cache_path(symbol)
        with open(path, "w") as f:
            json.dump({"timestamp": time.time(), "snapshot": snapshot}, f)
        logger.warning(f"{symbol}: snapshot cache saved")
    except Exception as ex:
        logger.error(f"{symbol}: snapshot cache save error: {ex}")


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

    try:
        logger.warning(f"{symbol}: fetching fresh market data")

        url = f"{BASE_URL}/{symbol}.US"
        params = {
            "api_token": EOD_API_KEY,
            "period": "d",
            "fmt": "json",
        }

        # FIXED: Increased timeout from 10 to 30 seconds
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, list) or len(data) < 20:
            raise ValueError("Insufficient OHLC data")

        df = pd.DataFrame(data)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.dropna(inplace=True)

        if len(df) < 20:
            raise ValueError("Not enough clean rows")

        close = df["close"]

        snapshot = {
            "symbol": symbol,
            "current_price": safe_float(close.iloc[-1]),
            "dma_50": safe_float(close.rolling(50).mean().iloc[-1]) if len(df) >= 50 else None,
            "dma_200": safe_float(close.rolling(200).mean().iloc[-1]) if len(df) >= 200 else None,
            "rsi_14": calculate_rsi(close),
            "volume": safe_float(df["volume"].iloc[-1]),
            "52w_high": safe_float(close.tail(252).max()),
            "52w_low": safe_float(close.tail(252).min()),
        }

        logger.warning(
            f"{symbol}: RSI={snapshot['rsi_14']} "
            f"DMA50={snapshot['dma_50']} "
            f"DMA200={snapshot['dma_200']} "
            f"VOL={snapshot['volume']}"
        )

        _save_snapshot_cache(symbol, snapshot)
        return snapshot

    except requests.exceptions.Timeout:
        logger.error(f"{symbol}: request timed out after 30 seconds")
        stale = _load_snapshot_cache(symbol)
        if stale is not None:
            logger.warning(f"{symbol}: serving stale snapshot after timeout")
            return stale
        return {"symbol": symbol, "current_price": None, "dma_50": None,
                "dma_200": None, "rsi_14": None, "volume": None,
                "52w_high": None, "52w_low": None}

    except Exception as e:
        logger.error(f"{symbol}: fetch failed → {e}")
        stale = _load_snapshot_cache(symbol)
        if stale is not None:
            logger.warning(f"{symbol}: serving stale snapshot after error")
            return stale
        return {"symbol": symbol, "current_price": None, "dma_50": None,
                "dma_200": None, "rsi_14": None, "volume": None,
                "52w_high": None, "52w_low": None}