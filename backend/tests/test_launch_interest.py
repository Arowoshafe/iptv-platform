"""Integration checks for the local launch waitlist."""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import connect_db
from app.main import app

ENDPOINT = "/api/v1/launch-interest"


@pytest.fixture
def signup_email():
    email = f"waitlist-{secrets.token_hex(8)}@example.test"
    try:
        yield email
    finally:
        with connect_db() as conn:
            conn.execute("DELETE FROM launch_interest WHERE email = %s", (email,))


def test_signup_is_saved_once_per_email_and_country(signup_email):
    with TestClient(app) as client:
        for email, country in [
            (signup_email, "US"),
            (signup_email.upper(), "US"),
            (signup_email, "NG"),
        ]:
            response = client.post(ENDPOINT, json={"email": email, "country": country})
            assert response.status_code == 201
            assert response.json() == {"status": "registered"}

    with connect_db() as conn:
        rows = conn.execute(
            "SELECT country FROM launch_interest WHERE email = %s ORDER BY country",
            (signup_email,),
        ).fetchall()
    assert rows == [("NG",), ("US",)]


def test_signup_rejects_invalid_email_and_country(signup_email):
    with TestClient(app) as client:
        for payload in [
            {"email": "invalid-address", "country": "US"},
            {"email": signup_email, "country": "GB"},
        ]:
            assert client.post(ENDPOINT, json=payload).status_code == 422

    with connect_db() as conn:
        assert conn.execute(
            "SELECT count(*) FROM launch_interest WHERE email = %s", (signup_email,)
        ).fetchone() == (0,)
