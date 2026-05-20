import pandas as pd
import pytest

from options_engine import OptionsEngine


# -------------------------
# Mock yfinance Ticker
# -------------------------
class MockTicker:

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period="1d"):
        """
        Strong bullish trend:
        - Enough data for DMA50 / DMA200
        - Rising prices create valid RSI
        - Should pass strategy filters
        """
        closes = list(range(50, 300))  # 250 trading days
        return pd.DataFrame({
            "Close": closes
        })

    @property
    def options(self):
        return ["2026-06-20"]

    def option_chain(self, expiry):
        """
        Stock price ≈ 299
        Valid CSP strikes should be ~5–15% below spot
        """
        puts = pd.DataFrame([
            {
                "strike": 275,   # ~8% below
                "bid": 4.5,
                "ask": 4.8,
                "volume": 100,
                "openInterest": 200
            },
            {
                "strike": 260,   # ~13% below
                "bid": 3.0,
                "ask": 3.2,
                "volume": 50,
                "openInterest": 80
            }
        ])

        calls = pd.DataFrame([])

        class Chain:
            def __init__(self, puts, calls):
                self.puts = puts
                self.calls = calls

        return Chain(puts, calls)


# -------------------------
# Tests
# -------------------------

def test_csp_engine_returns_results(monkeypatch):

    import options_engine

    # Replace yf.Ticker with bullish mock
    monkeypatch.setattr(options_engine.yf, "Ticker", MockTicker)

    engine = OptionsEngine()

    results = engine.find_csp_opportunities("AAPL")

    assert isinstance(results, list)
    assert len(results) > 0

    r = results[0]

    assert "symbol" in r
    assert "strike" in r
    assert "premium" in r
    assert "score" in r
    assert "recommendation" in r

    assert r["recommendation"] in ("STRONG", "GOOD", "OK", "WEAK")
    assert r["score"] > 0


def test_csp_engine_filters_bad_trend(monkeypatch):
    """
    If stock is in a confirmed downtrend
    (below 200 DMA / bearish structure),
    engine should reject all CSP setups.
    """

    import options_engine

    class BadTicker(MockTicker):
        def history(self, period="1d"):
            # Strong bearish decline
            closes = list(range(300, 50, -1))
            return pd.DataFrame({
                "Close": closes
            })

    monkeypatch.setattr(options_engine.yf, "Ticker", BadTicker)

    engine = OptionsEngine()

    results = engine.find_csp_opportunities("BAD")

    assert results == []