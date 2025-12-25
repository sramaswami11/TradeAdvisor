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
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "HOLD"


# -------------------------
# RSI-aware BUY zone tests
# -------------------------

def test_buy_only_if_rsi_between_30_and_35():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
    }

    data["rsi_14"] = 32
    assert get_trade_recommendation(data) == "BUY"

    data["rsi_14"] = 29
    assert get_trade_recommendation(data) == "HOLD"

    data["rsi_14"] = 36
    assert get_trade_recommendation(data) == "HOLD"


def test_rsi_exact_boundaries():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
    }

    data["rsi_14"] = 30
    assert get_trade_recommendation(data) == "BUY"

    data["rsi_14"] = 35
    assert get_trade_recommendation(data) == "BUY"


def test_hold_if_rsi_overbought():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "dma_50": 87,
        "rsi_14": 75
    }
    assert get_trade_recommendation(data) == "HOLD"


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
    assert get_trade_recommendation(data) == "HOLD"


def test_hold_if_price_equals_50_dma():
    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 85,
        "dma_50": 90,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "HOLD"


# -------------------------
# Near-low / near-high boundary tests
# -------------------------

def test_near_low_exact_10_percent_boundary():
    data = {
        "current_price": 93.5,  # 85 * 1.10
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 90,
        "dma_50": 89,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "BUY"


def test_near_high_exact_90_percent_boundary():
    data = {
        "current_price": 135,  # 150 * 0.90
        "52w_low": 80,
        "52w_high": 150,
        "dma_200": 160,
        "dma_50": 155,
        "rsi_14": 55
    }
    assert get_trade_recommendation(data) == "SELL"


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
    assert get_trade_recommendation(data) == "HOLD"


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
    assert get_trade_recommendation(data) == "HOLD"

    data = {
        "current_price": 90,
        "52w_low": 85,
        "52w_high": 150,
        "dma_200": 88,
        "rsi_14": 32
    }
    assert get_trade_recommendation(data) == "HOLD"
