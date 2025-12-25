import time
import copy
import logging
import yfinance as yf
import pandas as pd

# =========================
# Logging
# =========================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# Simple in-memory cache
# =========================

CACHE = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

# =========================
# Indicators
# =========================

def calculate_rsi(series: pd.Series, period: int = 14) -> float | None:
    if series is None or len(series) < period + 1:
        return None

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return round(rsi.iloc[-1], 2)

# =========================
# Step 1: Data collection
# =========================

def get_trade_advisor_data(ticker: str) -> dict:
    ticker = ticker.upper()
    now = time.time()

    # ---------- CACHE CHECK ----------
    cached = CACHE.get(ticker)
    if cached:
        age = now - cached["timestamp"]
        if age < CACHE_TTL_SECONDS:
            logger.info(f"Cache hit for {ticker} (age={int(age)}s)")
            return copy.deepcopy(cached["data"])
        else:
            logger.info(f"Cache expired for {ticker}")

    # ---------- FETCH FROM YFINANCE ----------
    logger.info(f"Fetching fresh data for {ticker}")

    stock = yf.Ticker(ticker)
    info = stock.info

    dma_200 = dma_50 = rsi_14 = None

    try:
        hist = stock.history(period="1y")
        if not hist.empty:
            close = hist["Close"]

            if len(close) >= 200:
                dma_200 = round(close.rolling(200).mean().iloc[-1], 2)

            if len(close) >= 50:
                dma_50 = round(close.rolling(50).mean().iloc[-1], 2)

            rsi_14 = calculate_rsi(close)

    except Exception as e:
        logger.warning(f"Indicator calculation failed for {ticker}: {e}")

    data = {
        "ticker": ticker,
        "current_price": info.get("currentPrice"),
        "previous_close": info.get("previousClose"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "market_cap": info.get("marketCap"),
        "dma_200": dma_200,
        "dma_50": dma_50,
        "rsi_14": rsi_14,
    }

    # ---------- STORE IN CACHE ----------
    CACHE[ticker] = {
        "timestamp": now,
        "data": copy.deepcopy(data)
    }

    return data

# =========================
# Step 2 + 3: Business logic
# =========================

def get_trade_recommendation(data: dict) -> str:
    price = data.get("current_price")
    low = data.get("52w_low")
    high = data.get("52w_high")
    dma_200 = data.get("dma_200")
    dma_50 = data.get("dma_50")
    rsi = data.get("rsi_14")

    if None in (price, low, high, dma_200, dma_50, rsi):
        return "HOLD"

    near_low = price <= low * 1.10
    near_high = price >= high * 0.90
    above_200 = price > dma_200
    above_50 = price > dma_50

    # BUY: controlled oversold rebound
    if near_low and above_200 and above_50 and 30 <= rsi <= 35:
        return "BUY"

    # SELL: weakness near highs
    if near_high and not above_200:
        return "SELL"

    return "HOLD"

# =========================
# Explanation (WHY)
# =========================

def explain_trade_recommendation(data: dict) -> str:
    price = data.get("current_price")
    low = data.get("52w_low")
    high = data.get("52w_high")
    dma_200 = data.get("dma_200")
    dma_50 = data.get("dma_50")
    rsi = data.get("rsi_14")

    if None in (price, low, high, dma_200, dma_50, rsi):
        return "Insufficient data to make a confident recommendation."

    reasons = []

    if price <= low * 1.10:
        reasons.append("Price is near the 52-week low")

    if price >= high * 0.90:
        reasons.append("Price is near the 52-week high")

    reasons.append(
        "Price is above the 200-day moving average"
        if price > dma_200
        else "Price is below the 200-day moving average"
    )

    reasons.append(
        "Price is above the 50-day moving average"
        if price > dma_50
        else "Price is below the 50-day moving average"
    )

    if rsi < 30:
        reasons.append("RSI indicates heavy oversold conditions")
    elif 30 <= rsi <= 35:
        reasons.append("RSI is weak but stabilizing (potential rebound zone)")
    elif rsi > 70:
        reasons.append("RSI indicates overbought conditions")
    else:
        reasons.append("RSI is neutral")

    return " • ".join(reasons)

# =========================
# Console runner
# =========================

def run_console():
    print("Welcome to TradeAdvisor (Python Edition)\n")

    while True:
        ticker = input("Enter ticker (or 'exit'): ").strip()
        if ticker.lower() == "exit":
            break

        data = get_trade_advisor_data(ticker)
        recommendation = get_trade_recommendation(data)
        explanation = explain_trade_recommendation(data)

        print("\n=== TradeAdvisor Report ===")
        for k, v in data.items():
            print(f"{k}: {v}")
        print(f"recommendation: {recommendation}")
        print(f"why: {explanation}")
        print("==========================\n")

if __name__ == "__main__":
    run_console()
