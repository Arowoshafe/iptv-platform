"""Local subscriber authentication."""
import hashlib
import hmac
import os
import secrets
from threading import BoundedSemaphore
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, StringConstraints

router = APIRouter()
SESSION_SECONDS = 900
LOGIN_WINDOW_SECONDS = 300
LOGIN_CLIENT_LIMIT = 60
LOGIN_EMAIL_LIMIT = 5
login_slots = BoundedSemaphore(2)
bearer = HTTPBearer(auto_error=False)


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


def connect_db():
    return psycopg.connect(
    host=os.environ["DB_HOST"],
    port=os.environ.get("DB_PORT", "5432"),
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    connect_timeout=3,
)


def reserve_login_attempt(client_host: str, email: str) -> None:
    key_specs = (
        ("client", client_host, LOGIN_CLIENT_LIMIT),
        ("email", client_host + "\0" + email, LOGIN_EMAIL_LIMIT),
    )
    allowed = True
    with connect_db() as conn:
        # Always lock buckets in the same order. Commit the reservation before
        # computing the password hash so failed logins count too.
        conn.execute(
            "DELETE FROM login_rate_limits WHERE limit_key IN ("
            "SELECT limit_key FROM login_rate_limits WHERE expires_at <= statement_timestamp() "
            "ORDER BY expires_at LIMIT 32 FOR UPDATE SKIP LOCKED)"
        )
        for scope, value, limit in key_specs:
            key = scope + ":" + hashlib.sha256(value.encode("utf-8")).hexdigest()
            bucket = conn.execute(
                """
                INSERT INTO login_rate_limits (limit_key, attempts, expires_at)
                VALUES (%s, 1, statement_timestamp() + make_interval(secs => %s))
                ON CONFLICT (limit_key) DO UPDATE SET
                    attempts = CASE
                        WHEN login_rate_limits.expires_at <= statement_timestamp() THEN 1
                        ELSE login_rate_limits.attempts + 1
                    END,
                    expires_at = CASE
                        WHEN login_rate_limits.expires_at <= statement_timestamp() THEN EXCLUDED.expires_at
                        ELSE login_rate_limits.expires_at
                    END
                WHERE login_rate_limits.expires_at <= statement_timestamp()
                   OR login_rate_limits.attempts < %s
                RETURNING attempts
                """,
                (key, LOGIN_WINDOW_SECONDS, limit),
            ).fetchone()
            if bucket is None:
                allowed = False
                break

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts. Try again in five minutes.",
            headers={"Retry-After": str(LOGIN_WINDOW_SECONDS), "Cache-Control": "no-store"},
        )


@router.post("/api/v1/auth/login")
def login(body: LoginRequest, request: Request, response: Response):
    if not login_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Sign-in is busy. Try again shortly.",
            headers={"Retry-After": "1", "Cache-Control": "no-store"},
        )

    try:
        host = request.client.host if request.client else "unknown"
        email = body.email.lower()
        reserve_login_attempt(host, email)
        with connect_db() as conn:
            row = conn.execute(
                "SELECT s.id, c.password_hash FROM subscribers s "
                "JOIN subscriber_credentials c ON c.subscriber_id = s.id "
                "WHERE s.email = %s",
                (email,),
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
    finally:
        login_slots.release()

    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token, "token_type": "bearer", "expires_in": SESSION_SECONDS}


def session_required() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="A valid subscriber session is required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def session_token_hash(credentials: HTTPAuthorizationCredentials | None) -> bytes:
    if credentials is None or len(credentials.credentials) != 43:
        raise session_required()

    return hashlib.sha256(credentials.credentials.encode("utf-8")).digest()


@router.post("/api/v1/auth/logout", status_code=204)
def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Response:
    token_hash = session_token_hash(credentials)
    try:
        with connect_db() as conn:
            conn.execute(
                "DELETE FROM subscriber_sessions WHERE token_hash = %s",
                (token_hash,),
            )
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Sign-out is temporarily unavailable") from None

    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/api/v1/subscriber/me")
def subscriber_profile(
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    token_hash = session_token_hash(credentials)
    try:
        with connect_db() as conn:
            rows = conn.execute(
                """
                SELECT s.email, eligible.code
                FROM subscriber_sessions AS session
                JOIN subscribers AS s ON s.id = session.subscriber_id
                LEFT JOIN LATERAL (
                    SELECT DISTINCT p.code
                    FROM subscriptions AS sub
                    JOIN plans AS p ON p.id = sub.plan_id
                    WHERE sub.subscriber_id = s.id
                      AND sub.status = 'active'
                      AND p.is_active
                      AND (sub.start_at IS NULL OR sub.start_at <= now())
                      AND (sub.end_at IS NULL OR sub.end_at > now())
                ) AS eligible ON TRUE
                WHERE session.token_hash = %s AND session.expires_at > now()
                ORDER BY eligible.code
                """,
                (token_hash,),
            ).fetchall()
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Subscriber profile is temporarily unavailable") from None

    if not rows:
        raise session_required()

    response.headers["Cache-Control"] = "no-store"
    return {"email": rows[0][0], "active_plans": [code for _, code in rows if code is not None]}
