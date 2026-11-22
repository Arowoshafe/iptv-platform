"""Integration test for the subscriber flow against local PostgreSQL."""
import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import connect_db
from app.main import app


@pytest.fixture
def test_subscriber():
    email = f"subscriber-{secrets.token_hex(8)}@example.test"
    password = secrets.token_urlsafe(24)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=2**17, r=8, p=1,
        maxmem=256 * 1024 * 1024,
    )

    with connect_db() as conn:
        plan = conn.execute(
            "SELECT id FROM plans WHERE code = 'demo-us' AND is_active"
        ).fetchone()
        assert plan is not None, "Seed the active demo-us plan before running this test."
        subscriber_id = conn.execute(
            "INSERT INTO subscribers (email) VALUES (%s) RETURNING id", (email,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO subscriber_credentials (subscriber_id, password_hash) VALUES (%s, %s)",
            (subscriber_id, f"scrypt$131072$8$1${salt.hex()}${digest.hex()}"),
        )
        conn.execute(
            "INSERT INTO subscriptions (subscriber_id, plan_id, status, start_at) "
            "VALUES (%s, %s, 'active', now())",
            (subscriber_id, plan[0]),
        )

    try:
        yield email, password
    finally:
        with connect_db() as conn:
            conn.execute("DELETE FROM subscriptions WHERE subscriber_id = %s", (subscriber_id,))
            conn.execute("DELETE FROM subscribers WHERE id = %s", (subscriber_id,))


def test_subscriber_sign_in_eligibility_and_sign_out(test_subscriber):
    email, password = test_subscriber
    with TestClient(app) as client:
        login = "/api/v1/auth/login"
        profile = "/api/v1/subscriber/me"
        news = "/api/v1/channels/demo-news/eligibility"

        assert client.get(profile).status_code == 401
        assert client.post(login, json={"email": email, "password": "wrong"}).status_code == 401

        response = client.post(login, json={"email": email, "password": password})
        assert response.status_code == 200
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]

        response = client.get(profile)
        assert response.status_code == 200
        assert response.json() == {"email": email, "active_plans": ["demo-us"]}

        response = client.get(news, params={"country": "US"})
        assert response.status_code == 200
        assert response.json()["eligible"] is True
        assert client.get(news, params={"country": "NG"}).status_code == 403
        assert client.get(
            "/api/v1/channels/demo-culture/eligibility", params={"country": "US"}
        ).status_code == 403

        assert client.post("/api/v1/auth/logout").status_code == 204
        assert client.get(profile).status_code == 401
        assert client.get(news, params={"country": "US"}).status_code == 401


def test_favorites_follow_the_subscriber_across_sessions(test_subscriber):
    email, password = test_subscriber
    login = "/api/v1/auth/login"
    favorites = "/api/v1/subscriber/favorites"
    channel = favorites + "/demo-news"

    def session_headers(client):
        response = client.post(login, json={"email": email, "password": password})
        assert response.status_code == 200
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    with TestClient(app) as first, TestClient(app) as second:
        assert first.get(favorites).status_code == 401
        assert first.put(channel).status_code == 401
        first.headers.update(session_headers(first))
        assert first.get(favorites).json() == {"channel_ids": []}
        assert first.put(favorites + "/missing").status_code == 404
        assert first.put(channel).status_code == 204
        assert first.put(channel).status_code == 204

        second.headers.update(session_headers(second))
        assert second.get(favorites).json() == {"channel_ids": ["demo-news"]}
        assert second.delete(channel).status_code == 204
        assert second.delete(channel).status_code == 204
        assert first.get(favorites).json() == {"channel_ids": []}
