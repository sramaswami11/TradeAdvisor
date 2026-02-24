import pytest
from app import app
from database import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("FLASK_SECRET_KEY", "testkey")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.com")

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    init_db()

    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_login_flow(client):
    response = client.post("/login", data={
        "name": "TestUser",
        "email": "test@test.com"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Tickers for" in response.data


def test_requires_login_for_dashboard(client):
    response = client.get("/dashboard")
    assert response.status_code == 302  # redirect