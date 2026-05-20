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

    def find_csp_opportunities(self, symbol, max_dte=60):

        ticker = yf.Ticker(symbol)

        # ---- Current price ----
        hist = ticker.history(period="5d")

        if hist.empty:
            print(f"{symbol}: No price history")
            return []

        price = float(hist["Close"].iloc[-1])

        # ---- Technical signals ----
        data = self._build_indicator_data(ticker, price)

        if not data:
            print(f"{symbol}: Insufficient indicator data")
            return []

        strategy = StrategyEngine(data).evaluate()
        signals = strategy.get("signals", {})

        print(f"{symbol}: SIGNALS -> {signals}")

        # Relaxed requirement:
        # allow above_200 OR above_50
        if not (signals.get("above_200_dma") or signals.get("above_50_dma")):
            print(f"{symbol}: Failed trend filter")
            return []

        opportunities = []

        # ---- Expirations ----
        for expiry in ticker.options:

            dte = self._days_to_expiry(expiry)

            # Broaden acceptable DTE
            if dte < 7 or dte > max_dte:
                continue

            try:
                chain = ticker.option_chain(expiry)
                puts = chain.puts
            except Exception as e:
                print(f"{symbol}: Option chain error for {expiry}: {e}")
                continue

            if puts.empty:
                continue

            for _, row in puts.iterrows():

                strike = float(row.get("strike", 0))
                bid = row.get("bid", 0)
                ask = row.get("ask", 0)

                premium = float(bid or 0)

                # fallback to midpoint if bid missing
                if premium <= 0 and ask:
                    premium = float(ask) * 0.5

                if premium <= 0:
                    continue

                # ---- Distance ----
                distance_pct = (strike - price) / price

                # Broaden strike selection:
                # Accept 3–25% below spot
                if distance_pct > -0.03 or distance_pct < -0.25:
                    continue

                # ---- Liquidity ----
                volume = row.get("volume", 0) or 0
                oi = row.get("openInterest", 0) or 0

                if volume < 1 and oi < 1:
                    continue

                # ---- Yield ----
                yield_pct = premium / strike
                annualized = yield_pct * (365 / dte)

                # Minimum worthwhile premium
                if yield_pct < 0.003:
                    continue

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
                    "recommendation": self._label(score),
                    "volume": int(volume),
                    "open_interest": int(oi)
                })

        print(f"{symbol}: Found {len(opportunities)} CSP opportunities")

        return sorted(
            opportunities,
            key=lambda x: (
                x["score"],
                x["annualized"],
                x["volume"]
            ),
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