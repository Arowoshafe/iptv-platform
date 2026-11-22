"""Local subscriber authentication."""
import hashlib
import hmac
import os
import secrets
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, StringConstraints

router = APIRouter()
SESSION_SECONDS = 900
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class ChangePasswordRequest(BaseModel):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    new_password: Annotated[str, StringConstraints(min_length=12, max_length=256)]


def password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=2**17, r=8, p=1, maxmem=256 * 1024 * 1024,
    )


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

    digest = password_digest(password, salt)
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


@router.post("/api/v1/auth/login")
def login(body: LoginRequest, response: Response):
    try:
        with connect_db() as conn:
            row = conn.execute(
                "SELECT s.id, c.password_hash FROM subscribers s "
                "JOIN subscriber_credentials c ON c.subscriber_id = s.id "
                "WHERE s.email = %s FOR SHARE OF c",
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


@router.post("/api/v1/auth/change-password", status_code=204)
def change_password(
    body: ChangePasswordRequest,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Response:
    token_hash = session_token_hash(credentials)
    try:
        with connect_db() as conn:
            row = conn.execute(
                "SELECT c.subscriber_id, c.password_hash "
                "FROM subscriber_credentials AS c JOIN subscriber_sessions AS s "
                "ON s.subscriber_id = c.subscriber_id "
                "WHERE s.token_hash = %s AND s.expires_at > clock_timestamp() "
                "FOR UPDATE OF c",
                (token_hash,),
            ).fetchone()
            # The credentials lock may have waited for another password change.
            if row is None or conn.execute(
                "SELECT 1 FROM subscriber_sessions "
                "WHERE token_hash = %s AND expires_at > clock_timestamp()",
                (token_hash,),
            ).fetchone() is None:
                raise session_required()

            subscriber_id, stored_hash = row
            if not password_matches(body.current_password, stored_hash):
                raise HTTPException(status_code=403, detail="Current password is incorrect")
            if body.current_password == body.new_password:
                raise HTTPException(status_code=422, detail="Choose a different new password")

            salt = secrets.token_bytes(16)
            digest = password_digest(body.new_password, salt)
            password_hash = f"scrypt$131072$8$1${salt.hex()}${digest.hex()}"
            conn.execute(
                "UPDATE subscriber_credentials SET password_hash = %s WHERE subscriber_id = %s",
                (password_hash, subscriber_id),
            )
            conn.execute(
                "DELETE FROM subscriber_sessions WHERE subscriber_id = %s",
                (subscriber_id,),
            )
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Password change is temporarily unavailable") from None

    return Response(status_code=204, headers={"Cache-Control": "no-store"})


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
