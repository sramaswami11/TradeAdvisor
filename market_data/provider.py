# market_data/provider.py
import logging
from functools import lru_cache
import os

import pandas as pd
import requests

logger = logging.getLogger(__name__)

EOD_API_KEY = os.getenv("EODHD_API_KEY")  
if not EOD_API_KEY:
    raise RuntimeError("EODHD_API_KEY environment variable not set")



BASE_URL = "https://eodhd.com/api/eod"


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


@lru_cache(maxsize=256)
def fetch_snapshot(symbol: str) -> dict:
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

        return snapshot

    except requests.exceptions.Timeout as e:
        # More specific timeout error message
        logger.error(f"{symbol}: Request timed out after 30 seconds - try again later")
        
        return {
            "symbol": symbol,
            "current_price": None,
            "dma_50": None,
            "dma_200": None,
            "rsi_14": None,
            "volume": None,
            "52w_high": None,
            "52w_low": None,
        }
    
    except Exception as e:
        logger.error(f"{symbol}: fetch failed → {e}")

        return {
            "symbol": symbol,
            "current_price": None,
            "dma_50": None,
            "dma_200": None,
            "rsi_14": None,
            "volume": None,
            "52w_high": None,
            "52w_low": None,
        }