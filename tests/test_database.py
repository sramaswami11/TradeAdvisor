import pytest
import database


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
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