"""
Options Engine - CSP (Cash Secured Put) Scanner

Uses:
- StrategyEngine (stock quality)
- yfinance (options chain)
- Scoring model (premium + safety)
"""

import traceback
import time

import pandas as pd
import yfinance as yf
from datetime import datetime

from trade_advisor import StrategyEngine


class OptionsEngine:

    # -----------------------------------
    # 5 minute in-memory cache
    # -----------------------------------
    _cache = {}
    CACHE_SECONDS = 300

    def __init__(self):
        pass

    def find_csp_opportunities(self, symbol, max_dte=45):

        print(f"=== CSP SCAN START: {symbol} ===")

        # -----------------------------------
        # Cache lookup
        # -----------------------------------
        cache_key = symbol.upper()

        cached = self._cache.get(cache_key)

        if cached:

            cache_time, cache_results = cached

            age = time.time() - cache_time

            if age < self.CACHE_SECONDS:

                print(
                    f"USING CACHE FOR {symbol} "
                    f"(age={age:.0f}s)"
                )

                return cache_results

        try:
            ticker = yf.Ticker(symbol)

            # -----------------------------------
            # Fetch recent price history
            # -----------------------------------
            print("FETCHING HISTORY...")
            hist = None

            for attempt in range(3):

                try:

                    print(f"HISTORY ATTEMPT {attempt + 1}")

                    hist = ticker.history(
                        period="5d",
                        auto_adjust=True
                    )

                    if hist is not None and not hist.empty:
                        break

                except Exception as ex:

                    print(
                        f"HISTORY ATTEMPT {attempt + 1} FAILED:",
                        ex
                    )

                    time.sleep(3)

            print("HIST EMPTY:", hist.empty)

            if hist is None or hist.empty:
                print(f"{symbol}: unable to fetch history")
                return []

            price = float(hist["Close"].iloc[-1])

            print(f"CURRENT PRICE: {price}")

            # -----------------------------------
            # Build indicators
            # -----------------------------------
            data = self._build_indicator_data(ticker, price)

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
            # Options availability
            # -----------------------------------
            print("FETCHING EXPIRATIONS...")
            expirations = ticker.options
            print("EXPIRATIONS FETCH COMPLETE")

            if not expirations:
                print(f"{symbol}: no option expirations returned")
                return []

            opportunities = []

            # -----------------------------------
            # Loop expirations
            # -----------------------------------
            for expiry in expirations:

                dte = self._days_to_expiry(expiry)

                print(f"\nCHECKING EXPIRY {expiry} | DTE={dte}")

                #
                # allow 5 DTE+
                #
                if dte < 5 or dte > max_dte:
                    print("SKIPPING DTE")
                    continue

                try:
                    print(f"FETCHING OPTION CHAIN {expiry}...")
                    chain = ticker.option_chain(expiry)
                    print(f"OPTION CHAIN COMPLETE {expiry}")
                    puts = chain.puts

                except Exception as e:
                    print(f"OPTION CHAIN ERROR {expiry}: {e}")
                    continue

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

                        #
                        # Better premium calculation
                        #
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

                        distance_pct = (
                            strike - price
                        ) / price

                        #
                        # 2%–18% OTM CSP window
                        #
                        if distance_pct > -0.02 or distance_pct < -0.18:
                            continue

                        #
                        # Optional liquidity filter
                        #
                        if ask > 0 and bid > 0:

                            spread_pct = (ask - bid) / ask

                            if spread_pct > 0.50:
                                continue

                        yield_pct = premium / strike
                        annualized = yield_pct * (
                            365 / max(dte, 1)
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
                            "yield_pct": round(
                                yield_pct * 100, 2
                            ),
                            "annualized": round(
                                annualized * 100, 2
                            ),
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
            print(f"========== CSP DEBUG FOR {symbol} ==========")
            print(f"TOTAL OPPORTUNITIES: {len(opportunities)}")

            if not opportunities:
                print("NO CSP OPPORTUNITIES FOUND")
                print("Possible causes:")
                print("- No strikes in OTM range")
                print("- Liquidity filter removing contracts")
                print("- Option chain missing premiums")
                print("- yfinance returned incomplete data")

            results = sorted(
                opportunities,
                key=lambda x: x["score"],
                reverse=True
            )

            # -----------------------------------
            # Save to cache
            # -----------------------------------
            self._cache[cache_key] = (
                time.time(),
                results
            )

            print(
                f"CACHED {len(results)} RESULTS "
                f"FOR {symbol}"
            )

            return results

        except Exception as e:
            print("========== EXCEPTION ==========")
            traceback.print_exc()
            print("===============================")
            print(f"CSP ENGINE FAILURE FOR {symbol}: {e}")

            return []

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