# =========================
# TradeAdvisor Tests
# =========================

from trade_advisor import (
    get_trade_recommendation,
    explain_trade_recommendation
)

# -------------------------
# 200 DMA / basic BUY/HOLD/SELL
# -------------------------

def test_buy_near_low_above_200_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 32
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "BUY"


def test_hold_near_low_below_200_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 95,
        "dma_50": 90,
        "rsi_14": 32
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"


def test_sell_near_high_below_200_dma():
    data = {
        "current_price": 145,
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 155,
        "dma_50": 150,
        "rsi_14": 50
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "SELL"


def test_hold_near_high_above_200_dma():
    data = {
        "current_price": 145,
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 130,
        "dma_50": 135,
        "rsi_14": 50
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"


def test_hold_when_dma_missing():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "rsi_14": 32
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"


# -------------------------
# RSI-aware BUY zone tests
# -------------------------

def test_buy_only_if_rsi_between_30_and_35():
    base_data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
    }

    data = dict(base_data, rsi_14=32)
    assert get_trade_recommendation(data)["action"] == "BUY"

    data = dict(base_data, rsi_14=29)
    assert get_trade_recommendation(data)["action"] == "HOLD"

    data = dict(base_data, rsi_14=36)
    assert get_trade_recommendation(data)["action"] == "HOLD"


def test_rsi_exact_boundaries():
    base_data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
    }

    data = dict(base_data, rsi_14=30)
    assert get_trade_recommendation(data)["action"] == "BUY"

    data = dict(base_data, rsi_14=35)
    assert get_trade_recommendation(data)["action"] == "BUY"


def test_hold_if_rsi_overbought():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 75
    }
    assert get_trade_recommendation(data)["action"] == "HOLD"


# -------------------------
# 50 DMA-aware tests
# -------------------------

def test_hold_if_below_50_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 92,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data)["action"] == "HOLD"


def test_hold_if_price_equals_50_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 85,
        "dma_50": 90,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data)["action"] == "HOLD"


# -------------------------
# Near-low / near-high boundary tests
# -------------------------

def test_near_low_exact_10_percent_boundary():
    data = {
        "current_price": 93.5,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 90,
        "dma_50": 89,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data)["action"] == "BUY"


def test_near_high_exact_90_percent_boundary():
    data = {
        "current_price": 135,
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 160,
        "dma_50": 155,
        "rsi_14": 55
    }
    assert get_trade_recommendation(data)["action"] == "SELL"


# -------------------------
# Neutral / mid-range cases
# -------------------------

def test_hold_mid_range_price():
    data = {
        "current_price": 110,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 100,
        "dma_50": 105,
        "rsi_14": 45
    }
    assert get_trade_recommendation(data)["action"] == "HOLD"


# -------------------------
# Missing / invalid data safety
# -------------------------

def test_hold_if_missing_rsi_or_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
    }
    assert get_trade_recommendation(data)["action"] == "HOLD"

    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data)["action"] == "HOLD"


# ============================================================
# Explainability Tests
# ============================================================

def test_explanation_for_buy():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 32
    }

    explanation = explain_trade_recommendation(data)

    assert isinstance(explanation, list)
    assert any("52-week low" in e.lower() for e in explanation)
    assert any("200-day" in e.lower() for e in explanation)
    assert any("rsi" in e.lower() for e in explanation)


def test_explanation_for_sell():
    data = {
        "current_price": 145,
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 155,
        "dma_50": 150,
        "rsi_14": 55
    }

    explanation = explain_trade_recommendation(data)

    assert any("52-week high" in e.lower() for e in explanation)
    assert any("200-day" in e.lower() for e in explanation)


def test_explanation_for_hold_due_to_missing_data():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150
    }

    explanation = explain_trade_recommendation(data)

    assert any("insufficient data" in e.lower() for e in explanation)
