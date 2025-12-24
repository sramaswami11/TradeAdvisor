# =========================
# TradeAdvisor Tests
# =========================

from trade_advisor import get_trade_recommendation

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
    assert get_trade_recommendation(data) == "BUY"


def test_hold_near_low_below_200_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 95,
        "dma_50": 90,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "HOLD"


def test_sell_near_high_below_200_dma():
    data = {
        "current_price": 145,
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 155,
        "dma_50": 150,
        "rsi_14": 50
    }
    assert get_trade_recommendation(data) == "SELL"


def test_hold_near_high_above_200_dma():
    data = {
        "current_price": 145,
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 130,
        "dma_50": 135,
        "rsi_14": 50
    }
    assert get_trade_recommendation(data) == "HOLD"


def test_hold_when_dma_missing():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        # dma_200, dma_50 intentionally missing
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "HOLD"

# -------------------------
# RSI-aware BUY zone tests
# -------------------------

def test_buy_only_if_rsi_between_30_35():
    # RSI 32 -> BUY
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "BUY"

    # RSI 29 -> HOLD (too oversold)
    data["rsi_14"] = 29
    assert get_trade_recommendation(data) == "HOLD"

    # RSI 36 -> HOLD (weak but not buy)
    data["rsi_14"] = 36
    assert get_trade_recommendation(data) == "HOLD"

# -------------------------
# 50 DMA-aware tests
# -------------------------

def test_hold_if_below_50_dma():
    # Price above 200 DMA but below 50 DMA -> HOLD
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 92,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "HOLD"

def test_hold_if_missing_rsi_or_dma():
    # Missing RSI
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
    }
    assert get_trade_recommendation(data) == "HOLD"

    # Missing 50 DMA
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "HOLD"
