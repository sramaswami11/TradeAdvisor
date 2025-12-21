# =========================
# Step 3: 200 DMA–aware logic
# =========================

from trade_advisor import get_trade_advisor_data, get_trade_recommendation


def test_buy_near_low_above_200_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88
    }
    assert get_trade_recommendation(data) == "BUY"


def test_hold_near_low_below_200_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 95
    }
    assert get_trade_recommendation(data) == "HOLD"


def test_sell_near_high_below_200_dma():
    data = {
        "current_price": 145,
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 155
    }
    assert get_trade_recommendation(data) == "SELL"


def test_hold_near_high_above_200_dma():
    data = {
        "current_price": 145,
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 130
    }
    assert get_trade_recommendation(data) == "HOLD"


def test_hold_when_dma_missing():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        # dma_200 intentionally missing
    }
    assert get_trade_recommendation(data) == "HOLD"
