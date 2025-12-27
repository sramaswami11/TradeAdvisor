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
# Helpers
# =========================

def calculate_rsi(series: pd.Series, period: int = 14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

# =========================
# Confidence Scoring
# =========================

def calculate_confidence(action: str, data: dict) -> int:
    price = data.get("current_price")
    low = data.get("52w_low")
    high = data.get("52w_high")
    dma_200 = data.get("dma_200")
    dma_50 = data.get("dma_50")
    rsi = data.get("rsi_14")

    # Missing data → low confidence
    if None in (price, low, high, dma_200, dma_50, rsi):
        return 30

    confidence = 0

    if action == "BUY":
        if price <= low * 1.10:
            confidence += 25
        if price > dma_200:
            confidence += 25
        if price > dma_50:
            confidence += 20
        if 30 <= rsi <= 35:
            confidence += 30

    elif action == "SELL":
        if price >= high * 0.90:
            confidence += 50
        if price < dma_200:
            confidence += 50

    else:  # HOLD
        confidence = 50
        if price > dma_200 and rsi > 40:
            confidence += 10
        if rsi < 30 or rsi > 70:
            confidence -= 10

    return min(max(confidence, 0), 100)

# =========================
# Step 1: Data collection
# =========================

def get_trade_advisor_data(ticker: str) -> dict:
    ticker = ticker.upper()
    now = time.time()

    cached = CACHE.get(ticker)
    if cached:
        age = now - cached["timestamp"]
        if age < CACHE_TTL_SECONDS:
            logger.info(f"Cache hit for {ticker} ({int(age)}s)")
            return copy.deepcopy(cached["data"])

    logger.info(f"Fetching fresh data for {ticker}")

    stock = yf.Ticker(ticker)
    info = stock.info

    dma_200 = dma_50 = rsi_14 = None

    try:
        hist = stock.history(period="1y")
        if len(hist) >= 200:
            dma_200 = hist["Close"].rolling(200).mean().iloc[-1]
        if len(hist) >= 50:
            dma_50 = hist["Close"].rolling(50).mean().iloc[-1]
        if len(hist) >= 15:
            rsi_14 = calculate_rsi(hist["Close"])
    except Exception as e:
        logger.warning(f"Indicator calc failed for {ticker}: {e}")

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

    CACHE[ticker] = {
        "timestamp": now,
        "data": copy.deepcopy(data)
    }

    return data

# =========================
# Step 2 + 3: Explainable logic
# =========================

def get_trade_recommendation(data: dict) -> dict:
    reasons = []

    price = data.get("current_price")
    low = data.get("52w_low")
    high = data.get("52w_high")
    dma_200 = data.get("dma_200")
    dma_50 = data.get("dma_50")
    rsi = data.get("rsi_14")

    if None in (price, low, high, dma_200, dma_50, rsi):
        return {
            "action": "HOLD",
            "confidence": 30,
            "reasons": ["Insufficient data to form a reliable signal"]
        }

    near_low = price <= low * 1.10
    near_high = price >= high * 0.90
    above_200 = price > dma_200
    above_50 = price > dma_50

    # ----- BUY evaluation -----
    if near_low:
        reasons.append("Price is near 52-week low")
    else:
        reasons.append("BUY blocked: price not near 52-week low")

    if above_200:
        reasons.append("Price is above 200-day moving average")
    else:
        reasons.append("BUY blocked: price below 200-day moving average")

    if above_50:
        reasons.append("Price is above 50-day moving average")
    else:
        reasons.append("BUY blocked: price below 50-day moving average")

    if 30 <= rsi <= 35:
        reasons.append("RSI in 30–35 accumulation zone")
    elif rsi < 30:
        reasons.append("BUY blocked: RSI < 30 (falling knife protection)")
    else:
        reasons.append("BUY blocked: RSI not in buy zone")

    if near_low and above_200 and above_50 and 30 <= rsi <= 35:
        return {
            "action": "BUY",
            "confidence": calculate_confidence("BUY", data),
            "reasons": reasons
        }

    # ----- SELL evaluation -----
    if near_high and not above_200:
        return {
            "action": "SELL",
            "confidence": calculate_confidence("SELL", data),
            "reasons": [
                "Price near 52-week high",
                "Price below 200-day moving average (distribution risk)"
            ]
        }

    # ----- HOLD -----
    return {
        "action": "HOLD",
        "confidence": calculate_confidence("HOLD", data),
        "reasons": reasons
    }

# =========================
# Step 4: Explainability wrapper
# =========================

def explain_trade_recommendation(data: dict) -> list:
    result = get_trade_recommendation(data)
    return result.get("reasons", [])

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
        result = get_trade_recommendation(data)

        print("\n=== TradeAdvisor Report ===")
        for k, v in data.items():
            print(f"{k}: {v}")

        print(f"\nRecommendation: {result['action']}")
        print(f"Confidence: {result['confidence']}%")
        print("Reasons:")
        for r in result["reasons"]:
            print(f" - {r}")
        print("==========================\n")

if __name__ == "__main__":
    run_console()
