import pytest
import database


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(database, "_DB_PATH", db_file)
    database.init_db()
    yield


def test_create_and_fetch_user(temp_db):
    database.create_user("alice@test.com", "Alice")
    user = database.get_user_by_email("alice@test.com")

    assert user is not None
    assert user["email"] == "alice@test.com"
    assert user["name"] == "Alice"


def test_add_and_remove_ticker(temp_db):
    database.create_user("bob@test.com", "Bob")
    user = database.get_user_by_email("bob@test.com")

    database.add_ticker_to_user(user["id"], "AAPL")
    tickers = database.get_tickers_for_user(user["id"])
    assert "AAPL" in tickers

    database.remove_ticker_from_user(user["id"], "AAPL")
    tickers = database.get_tickers_for_user(user["id"])
    assert "AAPL" not in tickers


def test_update_user_name_if_missing(temp_db):
    database.create_user("charlie@test.com", None)
    user = database.get_user_by_email("charlie@test.com")

    database.update_user_name_if_missing(user["id"], "Charlie")
    updated = database.get_user_by_email("charlie@test.com")

    assert updated["name"] == "Charlie"


def test_get_user_by_id(temp_db):
    database.create_user("dave@test.com", "Dave")
    user = database.get_user_by_email("dave@test.com")
    fetched = database.get_user_by_id(user["id"])
    assert fetched is not None
    assert fetched["email"] == "dave@test.com"
    assert fetched["name"] == "Dave"


def test_add_ticker_idempotent(temp_db):
    database.create_user("eve@test.com", "Eve")
    user = database.get_user_by_email("eve@test.com")
    database.add_ticker_to_user(user["id"], "TSLA")
    database.add_ticker_to_user(user["id"], "TSLA")  # duplicate — must not error or duplicate
    tickers = database.get_tickers_for_user(user["id"])
    assert tickers.count("TSLA") == 1


def test_cache_set_and_get(temp_db):
    database.set_cache("test_key", "test_value", 1234567890.0)
    result = database.get_cache("test_key")
    assert result is not None
    assert result["value"] == "test_value"
    assert result["timestamp"] == 1234567890.0


def test_cache_miss_returns_none(temp_db):
    assert database.get_cache("nonexistent_key") is None


# -------------------------
# IV History
# -------------------------

def test_record_and_rank_iv(temp_db):
    # Seed 10 readings: low=0.10, high=0.50, current (last)=0.40
    import time
    base = time.time() - 9 * 3600
    ivs = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.38, 0.42, 0.45, 0.40]
    for i, iv in enumerate(ivs):
        database.record_iv("AAPL", iv)

    result = database.get_iv_rank("AAPL")
    assert result is not None
    # IV Rank = (0.40 - 0.10) / (0.45 - 0.10) * 100 ≈ 85.7
    assert 83 <= result["iv_rank"] <= 88
    assert result["sample_count"] == 10


def test_iv_rank_insufficient_data_returns_none(temp_db):
    # Fewer than _IV_RANK_MIN_SAMPLES readings
    database.record_iv("TSLA", 0.50)
    database.record_iv("TSLA", 0.55)
    assert database.get_iv_rank("TSLA") is None


def test_iv_rank_flat_iv_returns_none(temp_db):
    # All readings identical → range = 0 → undefined rank
    for _ in range(10):
        database.record_iv("SPY", 0.15)
    assert database.get_iv_rank("SPY") is None


def test_iv_rank_unknown_symbol_returns_none(temp_db):
    assert database.get_iv_rank("UNKNOWN") is None