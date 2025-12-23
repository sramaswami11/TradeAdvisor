import time
import yfinance as yf
import logging

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
    if ticker in CACHE:
        cached = CACHE[ticker]
        if now - cached["timestamp"] < CACHE_TTL_SECONDS:
            return cached["data"]

    # ---------- FETCH FROM YFINANCE ----------
    logger.info(f"Fetching fresh data for {ticker}")


    stock = yf.Ticker(ticker)
    info = stock.info

    dma_200 = None
    try:
        hist = stock.history(period="1y")
        if not hist.empty and len(hist) >= 200:
            dma_200 = hist["Close"].rolling(window=200).mean().iloc[-1]
    except Exception:
        pass

    data = {
        "ticker": ticker,
        "current_price": info.get("currentPrice"),
        "previous_close": info.get("previousClose"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "market_cap": info.get("marketCap"),
        "dma_200": dma_200,
    }

    # ---------- STORE IN CACHE ----------
    CACHE[ticker] = {
        "timestamp": now,
        "data": data
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

    if None in (price, low, high, dma_200):
        return "HOLD"

    near_low = price <= low * 1.10
    near_high = price >= high * 0.90
    above_dma = price > dma_200

    if near_low and above_dma:
        return "BUY"
    elif near_high and not above_dma:
        return "SELL"
    else:
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
