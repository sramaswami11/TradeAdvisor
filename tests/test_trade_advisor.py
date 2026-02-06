import pytest

from trade_advisor import (
    get_trade_recommendation,
    explain_trade_recommendation
)

# =================================================
# BUY / HOLD / SELL core behavior
# =================================================

def test_buy_when_near_52w_low_above_200dma_and_low_rsi():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 30
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "BUY"
    assert 60 <= result["confidence"] <= 100


def test_hold_when_price_above_200_dma_but_rsi_high():
    data = {
        "current_price": 120,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 100,
        "dma_50": 110,
        "rsi_14": 72
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"


def test_sell_near_high_with_low_rsi():
    data = {
        "current_price": 148,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 120,
        "dma_50": 135,
        "rsi_14": 28
    }
    result = get_trade_recommendation(data)
    assert result["action"] in ("SELL", "HOLD")


# =================================================
# Boundary & invalid data handling
# =================================================

def test_no_crash_when_52w_high_equals_52w_low():
    data = {
        "current_price": 100,
        "52w_low": 100,
        "52w_high": 100,
        "dma_200": 95,
        "dma_50": 97,
        "rsi_14": 50
    }
    result = get_trade_recommendation(data)
    assert result["action"] in ("HOLD", "SELL")


def test_hold_when_price_is_zero():
    """
    Price = 0 is invalid market data.
    System should fail safe → HOLD with zero confidence.
    """
    data = {
        "current_price": 0,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 32
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"
    assert result["confidence"] == 0


def test_non_numeric_inputs_raise_typeerror():
    data = {
        "current_price": "abc",
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 32
    }
    with pytest.raises(TypeError):
        get_trade_recommendation(data)


# =================================================
# Missing data handling
# =================================================

def test_hold_and_zero_confidence_when_rsi_missing_but_dmas_present():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"
    assert result["confidence"] == 0


def test_hold_and_zero_confidence_when_dma50_missing_but_other_data_present():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "rsi_14": 30
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"
    assert result["confidence"] == 0


def test_hold_and_zero_confidence_when_dma200_missing_but_other_data_present():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_50": 87,
        "rsi_14": 30
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"
    assert result["confidence"] == 0


def test_hold_when_rsi_missing_even_if_near_low():
    data = {
        "current_price": 86,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 80,
        "dma_50": 82
    }
    result = get_trade_recommendation(data)
    assert result["action"] == "HOLD"
    assert result["confidence"] == 0


# =================================================
# Explainability guarantees
# =================================================

def test_explanation_mentions_below_50dma_when_applicable():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 92,
        "rsi_14": 55
    }
    explanation = explain_trade_recommendation(data)
    joined = " ".join(explanation).lower()
    assert "50" in joined or "short-term" in joined


def test_explanation_mentions_below_200dma_when_applicable():
    """
    If price is below 200 DMA, explanation MUST mention
    long-term trend weakness explicitly.
    """
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 95,
        "dma_50": 87,
        "rsi_14": 32
    }
    explanation = explain_trade_recommendation(data)
    joined = " ".join(explanation).lower()
    assert "200" in joined or "long-term" in joined


# =================================================
# Confidence sanity checks
# =================================================

def test_better_setup_has_higher_confidence():
    weak = {
        "current_price": 100,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 100,
        "dma_50": 110,
        "rsi_14": 55
    }

    strong = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 32
    }

    assert (
        get_trade_recommendation(strong)["confidence"]
        >= get_trade_recommendation(weak)["confidence"]
    )
