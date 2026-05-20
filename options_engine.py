"""
Options Engine - CSP (Cash Secured Put) Scanner

Uses:
- StrategyEngine (stock quality)
- yfinance (options chain)
- Scoring model (premium + safety)
"""

import pandas as pd
import yfinance as yf
from datetime import datetime

from trade_advisor import StrategyEngine


class OptionsEngine:

    def __init__(self):
        pass

    def find_csp_opportunities(self, symbol, max_dte=45):

    print(f"=== CSP SCAN START: {symbol} ===")

    ticker = yf.Ticker(symbol)

    # ---- Get current price ----
    hist = ticker.history(period="1d")

    print("HIST EMPTY:", hist.empty)

    if hist.empty:
        return []

    price = float(hist["Close"].iloc[-1])

    print("PRICE:", price)

    # ---- Get technical signals ----
    data = self._build_indicator_data(ticker, price)

    print("INDICATOR DATA:", data)

    if not data:
        return []

    strategy = StrategyEngine(data).evaluate()
    signals = strategy.get("signals", {})

    print("SIGNALS:", signals)

    if not signals.get("above_200_dma"):
        print("FAILED: below 200 DMA")
        return []

    opportunities = []

    print("OPTIONS EXPIRIES:", ticker.options)

    for expiry in ticker.options:

        dte = self._days_to_expiry(expiry)

        print("EXPIRY:", expiry, "DTE:", dte)

        if dte <= 7 or dte > max_dte:
            print("SKIPPED DTE")
            continue

        chain = ticker.option_chain(expiry)
        puts = chain.puts

        print("PUT COUNT:", len(puts))

        if puts.empty:
            continue

        for _, row in puts.iterrows():

            strike = float(row["strike"])
            premium = float(row["bid"] or 0)

            distance_pct = (strike - price) / price

            print(
                f"STRIKE={strike} "
                f"PREMIUM={premium} "
                f"DIST={distance_pct:.2%}"
            )

            if premium <= 0:
                continue

            if distance_pct > -0.05 or distance_pct < -0.15:
                continue

            yield_pct = premium / strike
            annualized = yield_pct * (365 / dte)

            score = self._score_csp(
                signals,
                yield_pct,
                annualized,
                distance_pct
            )

            opportunities.append({
                "symbol": symbol,
                "strategy": "CSP",
                "price": round(price, 2),
                "strike": strike,
                "expiry": expiry,
                "dte": dte,
                "premium": round(premium, 2),
                "yield_pct": round(yield_pct * 100, 2),
                "annualized": round(annualized * 100, 2),
                "distance_pct": round(distance_pct * 100, 2),
                "score": score,
                "recommendation": self._label(score)
            })

    print("FINAL CSP COUNT:", len(opportunities))

    return sorted(
        opportunities,
        key=lambda x: x["score"],
        reverse=True
    )
    # --------------------------
    # Indicator Builder
    # --------------------------

    def _build_indicator_data(self, ticker, price):

        hist = ticker.history(period="1y")

        if hist.empty or len(hist) < 200:
            return {}

        dma50 = hist["Close"].rolling(50).mean().iloc[-1]
        dma200 = hist["Close"].rolling(200).mean().iloc[-1]

        low_52w = hist["Close"].min()
        high_52w = hist["Close"].max()

        # Placeholder RSI
        rsi = 50

        return {
            "current_price": price,
            "52w_low": float(low_52w),
            "52w_high": float(high_52w),
            "dma_200": float(dma200) if pd.notna(dma200) else None,
            "dma_50": float(dma50) if pd.notna(dma50) else None,
            "rsi_14": rsi
        }

    def _days_to_expiry(self, expiry_str):
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
        return (expiry_date - datetime.today()).days

    # --------------------------
    # Scoring
    # --------------------------

    def _score_csp(self, signals, yield_pct, annualized, distance_pct):

        score = 0

        if signals.get("above_200_dma"):
            score += 2

        if signals.get("above_50_dma"):
            score += 1

        if signals.get("rsi_state") == "neutral":
            score += 1

        if yield_pct > 0.005:
            score += 1

        if yield_pct > 0.01:
            score += 2

        if annualized > 0.10:
            score += 1

        if annualized > 0.20:
            score += 1

        if distance_pct < -0.07:
            score += 1

        if distance_pct < -0.15:
            score += 1

        return score

    # --------------------------
    # Labels
    # --------------------------

    def _label(self, score):

        if score >= 8:
            return "STRONG"
        elif score >= 5:
            return "GOOD"
        elif score >= 3:
            return "OK"
        return "WEAK"