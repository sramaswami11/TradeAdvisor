"""
Options Engine - CSP (Cash Secured Put) Scanner

Uses:
- StrategyEngine (stock quality)
- yfinance (options chain)
- Scoring model (premium + safety)
"""

import json
import os
import time
import traceback

import pandas as pd
import yfinance as yf

from datetime import datetime

from trade_advisor import StrategyEngine


# ------------------------------------
# Render-safe: use /tmp for cache file
# (ephemeral but at least writable)
# ------------------------------------
_CACHE_DIR = "/tmp" if os.path.exists("/tmp") else "."


class OptionsEngine:

    # -----------------------------------
    # Cache file goes in /tmp on Render
    # -----------------------------------
    EXPIRATION_CACHE_FILE = os.path.join(
        _CACHE_DIR,
        "expiration_cache.json"
    )

    EXPIRATION_CACHE_SECONDS = 86400  # 24 hours

    # OPTION_CHAIN_CACHE is now an instance
    # variable (not class-level) to avoid
    # shared state across workers/requests
    OPTION_CHAIN_CACHE_SECONDS = 1800

    MAX_EXPIRATIONS_TO_SCAN = 5

    # ------------------------------------------
    # User-Agent header: prevents Yahoo blocking
    # cloud datacenter IPs (Render, Heroku, etc.)
    # ------------------------------------------
    YAHOO_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    def __init__(self):
        # Instance-level cache prevents shared
        # state corruption across workers
        self._option_chain_cache = {}

    def find_csp_opportunities(self, symbol, max_dte=45):

        print(f"=== CSP SCAN START: {symbol} ===")

        try:

            ticker = yf.Ticker(symbol)

            # -----------------------------------
            # Fetch 1y history once (covers both
            # price and indicator needs)
            # -----------------------------------
            print("FETCHING HISTORY...")

            hist = None

            for attempt in range(3):

                try:

                    print(f"HISTORY ATTEMPT {attempt + 1}")

                    hist = ticker.history(
                        period="1y",
                        auto_adjust=True
                    )

                    if hist is not None and not hist.empty:
                        print("HISTORY FETCH SUCCESS")
                        break

                except Exception as ex:

                    msg = str(ex).lower()
                    wait = (
                        15 * (2 ** attempt)
                        if ("429" in msg or "too many" in msg)
                        else 3 * (2 ** attempt)
                    )
                    print(
                        f"HISTORY ATTEMPT {attempt + 1} FAILED:",
                        ex
                    )
                    time.sleep(wait)

            if hist is None or hist.empty:
                print(f"{symbol}: unable to fetch history")
                return []

            price = float(hist["Close"].iloc[-1])
            print(f"CURRENT PRICE: {price}")

            # -----------------------------------
            # Build indicators from same hist
            # (no second Yahoo call needed)
            # -----------------------------------
            data = self._build_indicator_data_from_hist(
                hist,
                price
            )

            print("INDICATOR DATA:", data)

            if not data:
                print("NO INDICATOR DATA")
                return []

            strategy = StrategyEngine(data).evaluate()
            signals = strategy.get("signals", {})

            print("STRATEGY SIGNALS:", signals)

            # -----------------------------------
            # Trend filter
            # -----------------------------------
            if not signals.get("above_200_dma"):
                print("FAILED TREND FILTER")
                return []

            # -----------------------------------
            # Fetch expirations
            # -----------------------------------
            expirations = self._get_expirations(
                ticker,
                symbol
            )

            if not expirations:
                print(f"{symbol}: no option expirations returned")
                return []

            print(f"USING {len(expirations)} EXPIRATIONS")

            opportunities = []

            # -----------------------------------
            # Filter to valid DTE window
            # -----------------------------------
            valid_expirations = []

            for expiry in expirations:

                dte = self._days_to_expiry(expiry)

                if 5 <= dte <= max_dte:
                    valid_expirations.append((expiry, dte))

            valid_expirations.sort(key=lambda x: x[1])
            valid_expirations = valid_expirations[
                :self.MAX_EXPIRATIONS_TO_SCAN
            ]

            print(
                f"SCANNING "
                f"{len(valid_expirations)} "
                f"EXPIRATIONS"
            )

            for i, (expiry, dte) in enumerate(valid_expirations):

                if i > 0:
                    time.sleep(1)

                print(
                    f"\nCHECKING EXPIRY "
                    f"{expiry} | DTE={dte}"
                )

                chain = self._get_cached_option_chain(
                    ticker,
                    symbol,
                    expiry
                )

                if chain is None:
                    print(f"FAILED OPTION CHAIN {expiry}")
                    continue

                puts = chain.puts

                if puts is None or puts.empty:
                    print(f"NO PUTS FOR {expiry}")
                    continue

                print(f"PUT COUNT: {len(puts)}")

                # -----------------------------------
                # Loop put contracts
                # -----------------------------------
                for _, row in puts.iterrows():

                    try:

                        strike = float(row["strike"])

                        bid = row.get("bid", 0)
                        ask = row.get("ask", 0)
                        last = row.get("lastPrice", 0)

                        bid = 0 if pd.isna(bid) else float(bid)
                        ask = 0 if pd.isna(ask) else float(ask)
                        last = 0 if pd.isna(last) else float(last)

                        # -----------------------------------
                        # Premium calculation
                        # -----------------------------------
                        if last > 0:
                            premium = last
                        elif bid > 0 and ask > 0:
                            premium = (bid + ask) / 2
                        elif ask > 0:
                            premium = ask * 0.95
                        elif bid > 0:
                            premium = bid
                        else:
                            continue

                        print(
                            f"STRIKE={strike:.2f} "
                            f"BID={bid:.2f} "
                            f"ASK={ask:.2f} "
                            f"LAST={last:.2f} "
                            f"PREM={premium:.2f}"
                        )

                        distance_pct = (strike - price) / price

                        # -----------------------------------
                        # 2%–18% OTM window
                        # -----------------------------------
                        if (
                            distance_pct > -0.02
                            or distance_pct < -0.18
                        ):
                            continue

                        # -----------------------------------
                        # Liquidity filter
                        # -----------------------------------
                        if ask > 0 and bid > 0:

                            spread_pct = (ask - bid) / ask

                            if spread_pct > 0.50:
                                continue

                        yield_pct = premium / strike

                        annualized = (
                            yield_pct * (365 / max(dte, 1))
                        )

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
                            "strike": round(strike, 2),
                            "expiry": expiry,
                            "dte": dte,
                            "premium": round(premium, 2),
                            "yield_pct": round(yield_pct * 100, 2),
                            "annualized": round(annualized * 100, 2),
                            "distance_pct": round(
                                distance_pct * 100, 2
                            ),
                            "score": score,
                            "recommendation": self._label(score)
                        })

                    except Exception as e:
                        print("ROW ERROR:", e)

            # -----------------------------------
            # Final diagnostics
            # -----------------------------------
            print(
                f"========== CSP DEBUG "
                f"FOR {symbol} =========="
            )
            print(f"TOTAL OPPORTUNITIES: {len(opportunities)}")

            if not opportunities:
                print("NO CSP OPPORTUNITIES FOUND")

            return sorted(
                opportunities,
                key=lambda x: x["score"],
                reverse=True
            )

        except Exception as e:

            print("========== EXCEPTION ==========")
            traceback.print_exc()
            print("===============================")
            print(f"CSP ENGINE FAILURE FOR {symbol}: {e}")

            return []

   
    # -----------------------------------
    # Expiration Fetcher
    # -----------------------------------
    def _get_expirations(self, ticker, symbol):

        cache = self._load_expiration_cache()
        symbol = symbol.upper()

        if symbol in cache:

            entry = cache[symbol]
            age = time.time() - entry["timestamp"]

            if age < self.EXPIRATION_CACHE_SECONDS:

                print(
                    f"USING CACHED EXPIRATIONS "
                    f"FOR {symbol}"
                )

                return entry["expirations"]

        print("FETCHING EXPIRATIONS...")

        expirations = None

        for attempt in range(3):

            try:

                print(f"EXPIRATION ATTEMPT {attempt + 1}")

                print("FETCHING OPTIONS FOR:", symbol)
                print("YF VERSION:", yf.__version__)

                expirations = ticker.options

                if expirations:
                    print("EXPIRATIONS FETCH SUCCESS")
                    break

            except Exception as ex:

                msg = str(ex).lower()
                wait = (
                    15 * (2 ** attempt)
                    if ("429" in msg or "too many" in msg)
                    else 3 * (2 ** attempt)
                )
                print(
                    f"EXPIRATION ATTEMPT "
                    f"{attempt + 1} FAILED:",
                    ex
                )
                time.sleep(wait)

        if expirations:

            cache[symbol] = {
                "timestamp": time.time(),
                "expirations": list(expirations)
            }

            self._save_expiration_cache(cache)
            print(f"CACHED EXPIRATIONS FOR {symbol}")

            return expirations

        # Fallback to stale cache
        if symbol in cache:

            print(
                f"USING STALE CACHED "
                f"EXPIRATIONS FOR {symbol}"
            )

            return cache[symbol]["expirations"]

        return []

    # -----------------------------------
    # Load expiration cache
    # -----------------------------------
    def _load_expiration_cache(self):

        try:

            if not os.path.exists(
                self.EXPIRATION_CACHE_FILE
            ):
                return {}

            with open(
                self.EXPIRATION_CACHE_FILE, "r"
            ) as f:
                return json.load(f)

        except Exception as ex:

            print("CACHE LOAD ERROR:", ex)
            return {}

    # -----------------------------------
    # Save expiration cache
    # -----------------------------------
    def _save_expiration_cache(self, cache):

        try:

            with open(
                self.EXPIRATION_CACHE_FILE, "w"
            ) as f:
                json.dump(cache, f)

        except Exception as ex:
            print("CACHE SAVE ERROR:", ex)

    # -----------------------------------
    # Cached option chain fetch
    # -----------------------------------
    def _get_cached_option_chain(
        self,
        ticker,
        symbol,
        expiry
    ):

        key = f"{symbol}_{expiry}"
        cached = self._option_chain_cache.get(key)

        if cached:

            cache_time, chain = cached
            age = time.time() - cache_time

            if age < self.OPTION_CHAIN_CACHE_SECONDS:

                print(
                    f"USING OPTION "
                    f"CHAIN CACHE {expiry}"
                )

                return chain

        try:

            chain = ticker.option_chain(expiry)

            self._option_chain_cache[key] = (
                time.time(),
                chain
            )

            print(f"CACHED OPTION CHAIN {expiry}")

            return chain

        except Exception as ex:

            print(f"OPTION CHAIN FAILED {expiry}: {ex}")
            return None

    # -----------------------------------
    # Indicator Builder
    # (uses already-fetched hist — no
    #  second Yahoo call)
    # -----------------------------------
    def _build_indicator_data_from_hist(
        self,
        hist,
        price
    ):

        if (
            hist is None
            or hist.empty
            or len(hist) < 200
        ):
            return {}

        dma50 = (
            hist["Close"]
            .rolling(50)
            .mean()
            .iloc[-1]
        )

        dma200 = (
            hist["Close"]
            .rolling(200)
            .mean()
            .iloc[-1]
        )

        low_52w = hist["Close"].min()
        high_52w = hist["Close"].max()

        rsi = 50

        return {
            "current_price": price,
            "52w_low": float(low_52w),
            "52w_high": float(high_52w),
            "dma_200": float(dma200) if pd.notna(dma200) else None,
            "dma_50": float(dma50) if pd.notna(dma50) else None,
            "rsi_14": rsi
        }

    # -----------------------------------
    # Keep old name as alias for any
    # callers that used _build_indicator_data
    # -----------------------------------
    def _build_indicator_data(self, ticker, price):

        hist = None

        for attempt in range(3):

            try:

                hist = ticker.history(period="1y")

                if hist is not None and not hist.empty:
                    break

            except Exception as ex:

                print("INDICATOR HISTORY FAILED:", ex)
                time.sleep(3)

        return self._build_indicator_data_from_hist(
            hist, price
        )

    def _days_to_expiry(self, expiry_str):

        expiry_date = datetime.strptime(
            expiry_str, "%Y-%m-%d"
        )

        return (expiry_date - datetime.today()).days

    # -----------------------------------
    # Scoring
    # -----------------------------------
    def _score_csp(
        self,
        signals,
        yield_pct,
        annualized,
        distance_pct
    ):

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

    # -----------------------------------
    # Labels
    # -----------------------------------
    def _label(self, score):

        if score >= 8:
            return "STRONG"

        elif score >= 5:
            return "GOOD"

        elif score >= 3:
            return "OK"

        return "WEAK"


_shared_engine = None


def get_shared_engine():
    global _shared_engine
    if _shared_engine is None:
        _shared_engine = OptionsEngine()
    return _shared_engine
