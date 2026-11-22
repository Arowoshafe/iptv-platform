"""Local subscriber authentication."""
import hashlib
import hmac
import os
import secrets
from typing import Annotated

import psycopg
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, StringConstraints

router = APIRouter()
SESSION_SECONDS = 900


class LoginRequest(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]


def password_matches(password: str, stored_hash: str | None) -> bool:
    salt = bytes(16)
    expected = bytes(64)
    if stored_hash is not None:
        try:
            scheme, n, r, p, salt_hex, digest_hex = stored_hash.split("$")
            if (scheme, n, r, p) != ("scrypt", "131072", "8", "1"):
                return False
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            if len(salt) != 16 or len(expected) != 64:
                return False
        except ValueError:
            return False

    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=2**17, r=8, p=1, maxmem=256 * 1024 * 1024,
    )
    return hmac.compare_digest(digest, expected) and stored_hash is not None


@router.post("/api/v1/auth/login")
def login(body: LoginRequest, response: Response):
    try:
        with psycopg.connect(
            host=os.environ["DB_HOST"],
            port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            connect_timeout=3,
        ) as conn:
            row = conn.execute(
                "SELECT s.id, c.password_hash FROM subscribers s "
                "JOIN subscriber_credentials c ON c.subscriber_id = s.id "
                "WHERE s.email = %s",
                (body.email.lower(),),
            ).fetchone()
            if not password_matches(body.password, row[1] if row else None):
                raise HTTPException(status_code=401, detail="Invalid email or password")

            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO subscriber_sessions (token_hash, subscriber_id, expires_at) "
                "VALUES (%s, %s, now() + make_interval(secs => %s))",
                (hashlib.sha256(token.encode("ascii")).digest(), row[0], SESSION_SECONDS),
            )
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Sign-in is temporarily unavailable") from None

    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token, "token_type": "bearer", "expires_in": SESSION_SECONDS}
