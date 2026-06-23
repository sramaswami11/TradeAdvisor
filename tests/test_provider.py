import pandas as pd
import pytest

from market_data.provider import calculate_rsi, safe_float


# -------------------------
# calculate_rsi
# -------------------------

def test_rsi_too_short_returns_none():
    series = pd.Series([100.0, 101.0, 102.0])
    assert calculate_rsi(series, period=14) is None

def test_rsi_monotonic_up_near_100():
    series = pd.Series(list(range(50, 100), ), dtype=float)
    result = calculate_rsi(series)
    assert result is not None
    assert result > 90

def test_rsi_monotonic_down_near_zero():
    series = pd.Series(list(range(100, 50, -1)), dtype=float)
    result = calculate_rsi(series)
    assert result is not None
    assert result < 10

def test_rsi_mixed_stays_in_range():
    import random
    random.seed(42)
    prices = [100 + (random.random() - 0.5) * 5 for _ in range(50)]
    result = calculate_rsi(pd.Series(prices))
    assert result is not None
    assert 0 <= result <= 100

def test_rsi_exactly_period_plus_one():
    series = pd.Series([float(i) for i in range(16)])  # period+1 = 15 rows needed
    result = calculate_rsi(series, period=14)
    assert result is not None


# -------------------------
# safe_float
# -------------------------

def test_safe_float_numeric():
    assert safe_float(3.14159) == 3.14

def test_safe_float_string_number():
    assert safe_float("42.5") == 42.5

def test_safe_float_none_returns_none():
    assert safe_float(None) is None

def test_safe_float_invalid_string_returns_none():
    assert safe_float("abc") is None

def test_safe_float_integer():
    assert safe_float(100) == 100.0
