"""
Options Engine - CSP (Cash Secured Put) Scanner

Uses:
- StrategyEngine (stock quality)
- yfinance (options chain)
- Scoring model (premium + safety)
"""

import json
import math
import os
import time

import pandas as pd
import yfinance as yf

from datetime import datetime, date, timedelta

from trade_advisor import StrategyEngine
from market_data.provider import calculate_rsi, _yf_semaphore
from database import get_cache, set_cache, record_iv, get_iv_rank


# ------------------------------------
# Render-safe: use /tmp for cache file
# (ephemeral but at least writable)
# ------------------------------------
_CACHE_DIR = "/tmp" if os.path.exists("/tmp") else "."


class OptionsEngine:

    EXPIRATION_CACHE_FILE = os.path.join(
        _CACHE_DIR,
        "expiration_cache.json"
    )

    EXPIRATION_CACHE_SECONDS = 86400  # 24 hours

    OPTION_CHAIN_CACHE_SECONDS = 1800

    MAX_EXPIRATIONS_TO_SCAN = 5

    def __init__(self):
        self._option_chain_cache = {}

    def find_csp_opportunities(self, symbol, max_dte=14):

        _yf_semaphore.acquire()
        try:

            ticker = yf.Ticker(symbol)

            # -----------------------------------
            # Fetch 1y history once (covers both
            # price and indicator needs)
            # -----------------------------------
            hist = None

            for attempt in range(3):

                try:

                    hist = ticker.history(
                        period="1y",
                        auto_adjust=True
                    )

                    if hist is not None and not hist.empty:
                        break

                except Exception as ex:

                    msg = str(ex).lower()
                    wait = (
                        5
                        if ("429" in msg or "too many" in msg)
                        else 3 * (2 ** attempt)
                    )
                    time.sleep(wait)

            if hist is None or hist.empty:
                return []

            price = float(hist["Close"].iloc[-1])

            # -----------------------------------
            # Build indicators from same hist
            # (no second Yahoo call needed)
            # -----------------------------------
            data = self._build_indicator_data_from_hist(
                hist,
                price
            )
            del hist  # free 1y of OHLCV data before options fetch

            if not data:
                return []

            strategy = StrategyEngine(data).evaluate()
            signals = strategy.get("signals", {})

            # -----------------------------------
            # Trend filter
            # -----------------------------------
            if not signals.get("above_200_dma"):
                return []

            # -----------------------------------
            # Fetch expirations
            # -----------------------------------
            time.sleep(2)  # space out burst calls after history fetch
            expirations = self._get_expirations(
                ticker,
                symbol
            )

            if not expirations:
                return []

            earnings_date = self._get_next_earnings(ticker)
            opportunities = []
            atm_iv = None
            atm_iv_distance = float("inf")

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

            for i, (expiry, dte) in enumerate(valid_expirations):

                expiry_date_obj = datetime.strptime(expiry, "%Y-%m-%d").date()
                near_earnings = (
                    earnings_date is not None
                    and abs((expiry_date_obj - earnings_date).days) <= 5
                )

                if i > 0:
                    time.sleep(1)

                chain = self._get_cached_option_chain(
                    ticker,
                    symbol,
                    expiry
                )

                if chain is None:
                    continue

                puts = chain.puts

                if puts is None or puts.empty:
                    continue

                # -----------------------------------
                # Loop put contracts
                # -----------------------------------
                for _, row in puts.iterrows():

                    try:

                        strike = float(row["strike"])

                        bid = row.get("bid", 0)
                        ask = row.get("ask", 0)
                        last = row.get("lastPrice", 0)
                        oi = row.get("openInterest", 0)
                        iv = row.get("impliedVolatility", 0)

                        bid = 0 if pd.isna(bid) else float(bid)
                        ask = 0 if pd.isna(ask) else float(ask)
                        last = 0 if pd.isna(last) else float(last)
                        oi = 0 if pd.isna(oi) else int(oi)
                        iv = 0.0 if pd.isna(iv) else float(iv)

                        # Track ATM IV (strike closest to price with valid IV)
                        if iv > 0:
                            dist = abs(strike - price)
                            if dist < atm_iv_distance:
                                atm_iv = iv
                                atm_iv_distance = dist

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

                        distance_pct = (strike - price) / price

                        # -----------------------------------
                        # ATM to 10% OTM window
                        # (exclude ITM puts; allow ATM and OTM)
                        # -----------------------------------
                        if (
                            distance_pct > 0
                            or distance_pct < -0.10
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

                        delta = self._put_delta(price, strike, dte, iv)

                        # Only filter on delta when IV is available to compute it.
                        # If IV is missing, let the strike through so rate-limited
                        # or partial chain responses don't silently drop everything.
                        if delta is not None and not (-0.30 <= delta <= -0.25):
                            continue

                        score = self._score_csp(
                            signals,
                            yield_pct,
                            annualized,
                            distance_pct
                        )

                        opportunities.append({
                            "symbol": symbol,
                            "strike": round(strike, 2),
                            "expiry": expiry,
                            "dte": dte,
                            "bid": round(bid, 2),
                            "ask": round(ask, 2),
                            "annualized": round(annualized * 100, 2),
                            "distance_pct": round(distance_pct * 100, 2),
                            "delta": delta,
                            "oi": oi,
                            "score": score,
                            "recommendation": self._label(score),
                            "earnings_warning": near_earnings,
                            "earnings_date": earnings_date.strftime("%Y-%m-%d") if earnings_date else None,
                        })

                    except Exception:
                        pass

            if atm_iv:
                record_iv(symbol, atm_iv)

            iv_rank_data = get_iv_rank(symbol)
            iv_rank = iv_rank_data["iv_rank"] if iv_rank_data else None

            for opp in opportunities:
                opp["iv_rank"] = iv_rank

            return sorted(
                opportunities,
                key=lambda x: x["score"],
                reverse=True
            )

        except Exception:

            return []

        finally:
            self._option_chain_cache.clear()  # free DataFrames between scans
            _yf_semaphore.release()

    # -----------------------------------
    # Earnings Date Fetcher
    # -----------------------------------
    def _get_next_earnings(self, ticker):
        try:
            cal = ticker.calendar
            if not cal:
                return None
            earnings = cal.get("Earnings Date")
            if not earnings:
                return None
            # yfinance returns a list of date objects
            dt = earnings[0] if isinstance(earnings, (list, tuple)) else earnings
            if isinstance(dt, date):
                return dt
            if isinstance(dt, str):
                return datetime.strptime(dt[:10], "%Y-%m-%d").date()
            return None
        except Exception:
            return None

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
                return entry["expirations"]

        expirations = None

        for attempt in range(3):

            try:

                expirations = ticker.options

                if expirations:
                    break

            except Exception as ex:

                msg = str(ex).lower()
                if "429" in msg or "too many" in msg:
                    if symbol in cache:
                        return cache[symbol]["expirations"]
                    # Don't retry 429 — retries hold memory and
                    # worsen throttling. Fail fast.
                    return []
                else:
                    time.sleep(3 * (2 ** attempt))

        if expirations:

            cache[symbol] = {
                "timestamp": time.time(),
                "expirations": list(expirations)
            }

            self._save_expiration_cache(cache)

            return expirations

        # Fallback to stale cache
        if symbol in cache:
            return cache[symbol]["expirations"]

        return []

    # -----------------------------------
    # Load expiration cache
    # -----------------------------------
    def _load_expiration_cache(self):

        try:

            if os.path.exists(self.EXPIRATION_CACHE_FILE):
                with open(self.EXPIRATION_CACHE_FILE, "r") as f:
                    return json.load(f)

        except Exception:
            pass

        # File missing (e.g. after Render redeploy) — fall back to DB
        try:
            row = get_cache("expiration_cache")
            if row:
                return json.loads(row["value"])
        except Exception:
            pass

        return {}

    # -----------------------------------
    # Save expiration cache
    # -----------------------------------
    def _save_expiration_cache(self, cache):

        try:
            with open(self.EXPIRATION_CACHE_FILE, "w") as f:
                json.dump(cache, f)
        except Exception:
            pass

        try:
            set_cache("expiration_cache", json.dumps(cache), time.time())
        except Exception:
            pass

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
                return chain

        try:

            chain = ticker.option_chain(expiry)

            self._option_chain_cache[key] = (
                time.time(),
                chain
            )

            return chain

        except Exception:
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

        rsi = calculate_rsi(hist["Close"])

        return {
            "current_price": price,
            "52w_low": float(low_52w),
            "52w_high": float(high_52w),
            "dma_200": float(dma200) if pd.notna(dma200) else None,
            "dma_50": float(dma50) if pd.notna(dma50) else None,
            "rsi_14": rsi
        }

    # -----------------------------------
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
    # Greeks
    # -----------------------------------
    def _put_delta(self, price, strike, dte, iv):
        T = dte / 365.0
        if T <= 0 or iv <= 0 or price <= 0 or strike <= 0:
            return None
        d1 = (math.log(price / strike) + (0.05 + 0.5 * iv ** 2) * T) / (iv * math.sqrt(T))
        return round(0.5 * math.erfc(-d1 / math.sqrt(2)) - 1, 2)

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
