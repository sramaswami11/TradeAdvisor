import time
import copy
import yfinance as yf
import logging

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
        if not hist.empty and len(hist) >= 200:
            dma_200 = hist["Close"].rolling(window=200).mean().iloc[-1]
        if not hist.empty and len(hist) >= 50:
            dma_50 = hist["Close"].rolling(window=50).mean().iloc[-1]

        # Compute 14-day RSI
        if not hist.empty and len(hist) >= 15:
            delta = hist["Close"].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(window=14).mean().iloc[-1]
            avg_loss = loss.rolling(window=14).mean().iloc[-1]
            if avg_loss != 0:
                rs = avg_gain / avg_loss
                rsi_14 = 100 - (100 / (1 + rs))
            else:
                rsi_14 = 100
    except Exception as e:
        logger.warning(f"Failed to calculate DMA or RSI for {ticker}: {e}")

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
# Step 2 + 3: Business logic (DMA + RSI-aware)
# =========================

def get_trade_recommendation(data: dict) -> str:
    price = data.get("current_price")
    low = data.get("52w_low")
    high = data.get("52w_high")
    dma_200 = data.get("dma_200")
    dma_50 = data.get("dma_50")
    rsi = data.get("rsi_14")

    # Require all indicators to be present for BUY decision
    if None in (price, low, high, dma_200, dma_50, rsi):
        return "HOLD"

    near_low = price <= low * 1.10
    near_high = price >= high * 0.90
    above_dma = price > dma_200 and price > dma_50

    # BUY zone: near low + above 50 & 200 DMA + RSI 30–35
    if near_low and above_dma and 30 <= rsi <= 35:
        return "BUY"

    # SELL zone: near high + below 50 or 200 DMA
    elif near_high and not above_dma:
        return "SELL"

    return "HOLD"


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

        print("\n=== TradeAdvisor Report ===")
        for k, v in data.items():
            print(f"{k}: {v}")
        print(f"recommendation: {recommendation}")
        print("==========================\n")


if __name__ == "__main__":
    run_console()
