"""Development-only catalog and rights model. No real channels or payments."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
import psycopg
from pydantic import BaseModel, Field

from .auth import connect_db

from .auth import router as auth_router
from .auth import subscriber_profile

APP_NAME = os.getenv("APP_NAME", "YOUR IPTV BRAND")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app = FastAPI(title=f"{APP_NAME} API", version="0.1.0")
app.include_router(auth_router)
Country = Literal["US", "NG"]
DEMO_PLAN_TERRITORIES = {"demo-us": "US", "demo-ng": "NG"}

# Fictional stations for interface and rights-filtering tests ONLY.
# Do NOT add third-party streams without documentary redistribution rights.
CHANNELS = [
    {"id": "demo-news", "name": "Demo News", "category": "News", "countries": ["US", "NG"], "programmes": ("World Update", "Headlines in Review", "Market Brief", "The Week in Focus"), "icon": "📰", "playable": False},
    {"id": "demo-culture", "name": "Demo Culture", "category": "Culture", "countries": ["NG"], "programmes": ("Across Cultures", "Arts and Heritage", "City Stories", "Music and Memory"), "icon": "🎭", "playable": False},
    {"id": "demo-lifestyle", "name": "Demo Lifestyle", "category": "Lifestyle", "countries": ["US"], "programmes": ("Everyday Living", "At Home Today", "The Weekend Kitchen", "Garden Hour"), "icon": "🌿", "playable": False},
    {"id": "demo-sports", "name": "Demo Sports", "category": "Sports", "countries": ["US", "NG"], "programmes": ("Sports Desk", "Weekend Highlights", "Match Review", "Training Ground"), "icon": "⚽", "playable": False},
]

class PlaybackRequest(BaseModel):
    channel_id: str

@app.get("/health")
def health():
    return {"status": "ok", "mode": "development-demo", "version": "0.1.0"}

@app.get("/ready")
def ready():
    """Development readiness: confirm that the isolated PostgreSQL container is reachable."""
    if not os.getenv("DB_HOST"):
        return JSONResponse(status_code=503, content={"status": "not-ready", "database": "not-configured"})
    try:
        import psycopg
        with psycopg.connect(
            host=os.environ["DB_HOST"],
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "iptv_dev"),
            user=os.getenv("DB_USER", "iptv_app"),
            password=os.environ["DB_PASSWORD"],
            connect_timeout=3,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception:
        # Do not leak database credentials or internal errors to web clients.
        return JSONResponse(status_code=503, content={"status": "not-ready", "database": "unavailable"})
    return {"status": "ready", "database": "connected"}

@app.get("/api/v1/config")
def config():
    return {"brand": APP_NAME, "mode": "development-demo", "notice": "No live streams or payments are connected"}

@app.get("/api/v1/regions")
def regions():
    return [{"code": "US", "name": "United States"}, {"code": "NG", "name": "Nigeria"}]

def programme_slot(titles: tuple[str, ...], start: datetime):
    return {
        "title": titles[start.hour % len(titles)],
        "starts_at": start,
        "ends_at": start + timedelta(hours=1),
    }


def programme_guide(titles: tuple[str, ...], now: datetime):
    start = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return {
        "now": programme_slot(titles, start),
        "next": programme_slot(titles, start + timedelta(hours=1)),
    }


@app.get("/api/v1/channels")
def channels(country: Country = Query(default="US")):
    now = datetime.now(timezone.utc)
    catalog = []
    for channel in CHANNELS:
        if country not in channel["countries"]:
            continue
        guide = programme_guide(channel["programmes"], now)
        public_channel = {
            key: value for key, value in channel.items() if key not in {"countries", "programmes"}
        }
        catalog.append({**public_channel, "epg_now": guide["now"]["title"], "guide": guide})
    return {"country": country, "channels": catalog}

@app.get("/api/v1/channels/{channel_id}/schedule")
def channel_schedule(channel_id: str, country: Country = Query(default="US")):
    channel = next((item for item in CHANNELS if item["id"] == channel_id), None)
    if channel is None or country not in channel["countries"]:
        raise HTTPException(status_code=404, detail="Channel unavailable in this demo territory")

    titles = channel["programmes"]
    start = programme_guide(titles, datetime.now(timezone.utc))["now"]["starts_at"]
    return {
        "country": country,
        "name": channel["name"],
        "category": channel["category"],
        "programmes": [
            programme_slot(titles, start + timedelta(hours=offset))
            for offset in range(24)
        ],
    }


@app.get("/api/v1/channels/{channel_id}/eligibility")
def channel_eligibility(
    channel_id: str,
    country: Country,
    subscriber: Annotated[dict, Depends(subscriber_profile)],
):
    """Evaluate demo access for a requested catalog country."""
    channel = next((item for item in CHANNELS if item["id"] == channel_id), None)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    if country not in channel["countries"]:
        raise HTTPException(status_code=403, detail="Channel unavailable in this demo territory")
    if not any(
        DEMO_PLAN_TERRITORIES.get(plan) == country
        for plan in subscriber["active_plans"]
    ):
        raise HTTPException(status_code=403, detail="An active plan for this demo territory is required")
    return {"channel_id": channel_id, "country": country, "eligible": True}


@app.get("/api/v1/subscriber/favorites")
def subscriber_favorites(subscriber: Annotated[dict, Depends(subscriber_profile)]):
    try:
        with connect_db() as conn:
            rows = conn.execute(
                "SELECT f.channel_code FROM subscriber_favorites AS f "
                "JOIN subscribers AS s ON s.id = f.subscriber_id "
                "WHERE s.email = %s ORDER BY f.channel_code",
                (subscriber["email"],),
            ).fetchall()
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Favorites are temporarily unavailable") from None

    available = {channel["id"] for channel in CHANNELS}
    return {"channel_ids": [row[0] for row in rows if row[0] in available]}


@app.put("/api/v1/subscriber/favorites/{channel_id}", status_code=204)
def save_subscriber_favorite(
    channel_id: str,
    subscriber: Annotated[dict, Depends(subscriber_profile)],
):
    if not any(channel["id"] == channel_id for channel in CHANNELS):
        raise HTTPException(status_code=404, detail="Channel not found")

    try:
        with connect_db() as conn:
            conn.execute(
                "INSERT INTO subscriber_favorites (subscriber_id, channel_code) "
                "SELECT id, %s FROM subscribers WHERE email = %s "
                "ON CONFLICT (subscriber_id, channel_code) DO NOTHING",
                (channel_id, subscriber["email"]),
            )
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Favorites are temporarily unavailable") from None


@app.delete("/api/v1/subscriber/favorites/{channel_id}", status_code=204)
def remove_subscriber_favorite(
    channel_id: str,
    subscriber: Annotated[dict, Depends(subscriber_profile)],
):
    try:
        with connect_db() as conn:
            conn.execute(
                "DELETE FROM subscriber_favorites AS f USING subscribers AS s "
                "WHERE f.subscriber_id = s.id AND s.email = %s AND f.channel_code = %s",
                (subscriber["email"], channel_id),
            )
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Favorites are temporarily unavailable") from None


@app.post("/api/v1/playback/session")
def playback_session(_: PlaybackRequest):
    # In production, require authentication, active subscription, geo-licensed rights,
    # device/session limits and a provider-approved token or signed CDN URL.
    raise HTTPException(status_code=403, detail="Playback unavailable: demo only. Connect a licensed provider and server-side entitlements first.")

class LaunchInterestRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    country: Country


@app.post("/api/v1/launch-interest", status_code=201)
def register_launch_interest(body: LaunchInterestRequest):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")
    try:
        with connect_db() as conn:
            conn.execute(
                "INSERT INTO launch_interest (email, country) VALUES (%s, %s) "
                "ON CONFLICT (email, country) DO NOTHING",
                (email, body.country),
            )
    except (KeyError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Registration is temporarily unavailable") from None
    return {"status": "registered"}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB_DIR / "landing.html")


@app.get("/catalog", include_in_schema=False)
def catalog():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/playlist-tester", include_in_schema=False)
def playlist_tester():
    if os.getenv("ENABLE_LOCAL_PLAYLIST_TESTER") != "1":
        raise HTTPException(status_code=404)
    return FileResponse(WEB_DIR / "playlist-tester.html")


@app.get("/catalog/channel", include_in_schema=False)
def channel_guide_page():
    return FileResponse(WEB_DIR / "channel-guide.html")
