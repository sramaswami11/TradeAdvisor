import json
from io import BytesIO
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


def login_as(client, name, email):
    return client.post(
        "/login",
        data={"name": name, "email": email},
        follow_redirects=True
    )


def test_admin_upload_requires_admin(client):
    login_as(client, "User", "user@test.com")
    response = client.get("/admin/upload-users")
    assert response.status_code == 403


def test_admin_upload_success(client):
    login_as(client, "Admin", "admin@test.com")

    payload = {
        "users": [
            {
                "name": "Alice",
                "email": "alice@test.com",
                "tickers": ["AAPL", "MSFT"]
            }
        ]
    }

    response = client.post(
        "/admin/upload-users",
        data={
            "file": (BytesIO(json.dumps(payload).encode()), "users.json")
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"