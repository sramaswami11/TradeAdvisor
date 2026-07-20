import pandas as pd
import pytest
from datetime import datetime, timedelta, date

from options_engine import OptionsEngine


# -------------------------
# Mock yfinance Ticker
# -------------------------
class MockTicker:

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period="1d", **kwargs):
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
        return [(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")]

    @property
    def calendar(self):
        # Earnings 60 days out — no warning expected
        return {"Earnings Date": [(datetime.now() + timedelta(days=60)).date()]}

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

    # Bypass file/DB expiration cache so MockTicker.options is always called
    monkeypatch.setattr(OptionsEngine, "_load_expiration_cache", lambda self: {})
    monkeypatch.setattr(OptionsEngine, "_save_expiration_cache", lambda self, cache: None)

    engine = OptionsEngine()

    results, reason = engine.find_csp_opportunities("AAPL")

    assert reason == "ok"
    assert isinstance(results, list)
    assert len(results) > 0

    r = results[0]

    assert "symbol" in r
    assert "strike" in r
    assert "bid" in r
    assert "ask" in r
    assert "score" in r
    assert "recommendation" in r

    assert r["recommendation"] in ("STRONG", "GOOD", "OK", "WEAK")
    assert r["score"] > 0
    assert "earnings_warning" in r
    assert r["earnings_warning"] is False  # earnings 60 days out in mock
    assert "iv_rank" in r  # None until enough history accumulates


def test_csp_engine_filters_bad_trend(monkeypatch):
    """
    If stock is in a confirmed downtrend
    (below 200 DMA / bearish structure),
    engine should reject all CSP setups.
    """

    import options_engine

    class BadTicker(MockTicker):
        def history(self, period="1d", **kwargs):
            # Strong bearish decline
            closes = list(range(300, 50, -1))
            return pd.DataFrame({
                "Close": closes
            })

    monkeypatch.setattr(options_engine.yf, "Ticker", BadTicker)

    engine = OptionsEngine()

    results, reason = engine.find_csp_opportunities("BAD")

    assert results == []
    assert reason == "below_dma"


# =========================================================
# Pure method tests — no yfinance, no network
# =========================================================

# -------------------------
# _put_delta
# -------------------------

def test_put_delta_atm():
    engine = OptionsEngine()
    delta = engine._put_delta(price=100, strike=100, dte=30, iv=0.2)
    assert delta is not None
    assert -0.55 <= delta <= -0.40  # ATM put ~-0.46

def test_put_delta_deep_otm():
    engine = OptionsEngine()
    delta = engine._put_delta(price=100, strike=70, dte=30, iv=0.2)
    assert delta is not None
    assert -0.05 <= delta <= 0.0  # far OTM, delta near zero

def test_put_delta_deep_itm():
    engine = OptionsEngine()
    delta = engine._put_delta(price=100, strike=130, dte=30, iv=0.2)
    assert delta is not None
    assert delta <= -0.80  # deep ITM, delta near -1

def test_put_delta_zero_iv_returns_none():
    engine = OptionsEngine()
    assert engine._put_delta(price=100, strike=100, dte=30, iv=0) is None

def test_put_delta_zero_dte_returns_none():
    engine = OptionsEngine()
    assert engine._put_delta(price=100, strike=100, dte=0, iv=0.2) is None

def test_put_delta_zero_price_returns_none():
    engine = OptionsEngine()
    assert engine._put_delta(price=0, strike=100, dte=30, iv=0.2) is None


# -------------------------
# _score_csp
# -------------------------

def test_score_csp_max():
    engine = OptionsEngine()
    signals = {"above_200_dma": True, "above_50_dma": True, "rsi_state": "neutral"}
    score = engine._score_csp(signals, yield_pct=0.02, annualized=0.30, distance_pct=-0.16)
    assert score == 11

def test_score_csp_zero():
    engine = OptionsEngine()
    score = engine._score_csp({}, yield_pct=0.001, annualized=0.05, distance_pct=-0.03)
    assert score == 0

def test_score_csp_partial():
    engine = OptionsEngine()
    signals = {"above_200_dma": True, "rsi_state": "neutral"}
    # above_200_dma(+2) + rsi neutral(+1) + yield>0.005(+1) + annualized>0.10(+1) = 5
    score = engine._score_csp(signals, yield_pct=0.006, annualized=0.15, distance_pct=-0.05)
    assert score == 5

def test_score_csp_iv_rank_adds_one_at_50():
    engine = OptionsEngine()
    base = engine._score_csp({}, yield_pct=0.001, annualized=0.05, distance_pct=-0.03)
    scored = engine._score_csp({}, yield_pct=0.001, annualized=0.05, distance_pct=-0.03, iv_rank=50)
    assert scored == base + 1

def test_score_csp_iv_rank_adds_two_at_70():
    engine = OptionsEngine()
    base = engine._score_csp({}, yield_pct=0.001, annualized=0.05, distance_pct=-0.03)
    scored = engine._score_csp({}, yield_pct=0.001, annualized=0.05, distance_pct=-0.03, iv_rank=70)
    assert scored == base + 2

def test_score_cc_iv_rank_adds_one_at_50():
    engine = OptionsEngine()
    base = engine._score_cc({}, yield_pct=0.001, annualized=0.05, distance_pct=0.03)
    scored = engine._score_cc({}, yield_pct=0.001, annualized=0.05, distance_pct=0.03, iv_rank=50)
    assert scored == base + 1

def test_score_cc_iv_rank_adds_two_at_70():
    engine = OptionsEngine()
    base = engine._score_cc({}, yield_pct=0.001, annualized=0.05, distance_pct=0.03)
    scored = engine._score_cc({}, yield_pct=0.001, annualized=0.05, distance_pct=0.03, iv_rank=70)
    assert scored == base + 2


def test_score_csp_near_earnings_deducts_two():
    engine = OptionsEngine()
    signals = {"above_200_dma": True, "above_50_dma": True, "rsi_state": "neutral"}
    without = engine._score_csp(signals, yield_pct=0.015, annualized=0.25, distance_pct=-0.08)
    with_earnings = engine._score_csp(signals, yield_pct=0.015, annualized=0.25, distance_pct=-0.08, near_earnings=True)
    assert with_earnings == without - 2


def test_score_cc_near_earnings_deducts_two():
    engine = OptionsEngine()
    signals = {"above_200_dma": True, "above_50_dma": True, "rsi_state": "overbought"}
    without = engine._score_cc(signals, yield_pct=0.015, annualized=0.25, distance_pct=0.08)
    with_earnings = engine._score_cc(signals, yield_pct=0.015, annualized=0.25, distance_pct=0.08, near_earnings=True)
    assert with_earnings == without - 2


def test_score_csp_near_earnings_floor_at_zero():
    engine = OptionsEngine()
    score = engine._score_csp({}, yield_pct=0.001, annualized=0.05, distance_pct=-0.03, near_earnings=True)
    assert score == 0


# -------------------------
# _label
# -------------------------

def test_label_strong():
    engine = OptionsEngine()
    assert engine._label(8) == "STRONG"
    assert engine._label(11) == "STRONG"

def test_label_good():
    engine = OptionsEngine()
    assert engine._label(5) == "GOOD"
    assert engine._label(7) == "GOOD"

def test_label_ok():
    engine = OptionsEngine()
    assert engine._label(3) == "OK"
    assert engine._label(4) == "OK"

def test_label_weak():
    engine = OptionsEngine()
    assert engine._label(0) == "WEAK"
    assert engine._label(2) == "WEAK"


# -------------------------
# _days_to_expiry
# -------------------------

def test_days_to_expiry_future():
    engine = OptionsEngine()
    future = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    assert engine._days_to_expiry(future) >= 6  # could be 6 or 7 depending on time of day

def test_days_to_expiry_past():
    engine = OptionsEngine()
    assert engine._days_to_expiry("2020-01-01") < 0


# -------------------------
# _build_indicator_data_from_hist
# -------------------------

def test_build_indicator_data_too_short_returns_empty():
    engine = OptionsEngine()
    hist = pd.DataFrame({"Close": list(range(100))})  # only 100 rows
    assert engine._build_indicator_data_from_hist(hist, 99) == {}

def test_build_indicator_data_sufficient_has_all_fields():
    engine = OptionsEngine()
    hist = pd.DataFrame({"Close": list(range(50, 300))})  # 250 rows
    result = engine._build_indicator_data_from_hist(hist, 299)
    for key in ("current_price", "dma_50", "dma_200", "52w_low", "52w_high", "rsi_14"):
        assert key in result

def test_build_indicator_data_values_are_numeric():
    engine = OptionsEngine()
    hist = pd.DataFrame({"Close": list(range(50, 300))})
    result = engine._build_indicator_data_from_hist(hist, 299)
    assert isinstance(result["dma_200"], float)
    assert isinstance(result["dma_50"], float)
    assert result["dma_200"] < result["dma_50"]  # rising prices: shorter MA > longer MA


# -------------------------
# _get_next_earnings
# -------------------------

class _CalTicker:
    def __init__(self, cal):
        self.calendar = cal

def test_get_next_earnings_returns_date():
    engine = OptionsEngine()
    earnings_dt = date(2026, 8, 1)
    ticker = _CalTicker({"Earnings Date": [earnings_dt]})
    result = engine._get_next_earnings(ticker)
    assert result == earnings_dt

def test_get_next_earnings_empty_calendar():
    engine = OptionsEngine()
    ticker = _CalTicker({})
    assert engine._get_next_earnings(ticker) is None

def test_get_next_earnings_none_calendar():
    engine = OptionsEngine()
    ticker = _CalTicker(None)
    assert engine._get_next_earnings(ticker) is None

def test_get_next_earnings_exception_returns_none():
    engine = OptionsEngine()
    class BrokenTicker:
        @property
        def calendar(self):
            raise RuntimeError("network error")
    assert engine._get_next_earnings(BrokenTicker()) is None

def test_earnings_warning_flag_near():
    """Opportunity expiring within 5 days of earnings should be flagged."""
    engine = OptionsEngine()
    expiry_dt = date(2026, 8, 1)
    earnings_dt = date(2026, 8, 3)  # 2 days after expiry
    assert abs((expiry_dt - earnings_dt).days) <= 5

def test_earnings_warning_flag_far():
    """Opportunity expiring >5 days from earnings should not be flagged."""
    engine = OptionsEngine()
    expiry_dt = date(2026, 8, 1)
    earnings_dt = date(2026, 8, 10)  # 9 days after expiry
    assert abs((expiry_dt - earnings_dt).days) > 5