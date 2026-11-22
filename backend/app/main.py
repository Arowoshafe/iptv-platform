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
    {"id": "demo-news", "name": "Demo News", "category": "News", "countries": ["US", "NG"], "programmes": ("World Update", "Headlines in Review"), "icon": "📰", "playable": False},
    {"id": "demo-culture", "name": "Demo Culture", "category": "Culture", "countries": ["NG"], "programmes": ("Across Cultures", "Arts and Heritage"), "icon": "🎭", "playable": False},
    {"id": "demo-lifestyle", "name": "Demo Lifestyle", "category": "Lifestyle", "countries": ["US"], "programmes": ("Everyday Living", "At Home Today"), "icon": "🌿", "playable": False},
    {"id": "demo-sports", "name": "Demo Sports", "category": "Sports", "countries": ["US", "NG"], "programmes": ("Sports Desk", "Weekend Highlights"), "icon": "⚽", "playable": False},
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

def programme_guide(titles: tuple[str, str], now: datetime):
    start = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    next_start = start + timedelta(hours=1)
    slot = start.hour % 2

    return {
        "now": {"title": titles[slot], "starts_at": start, "ends_at": next_start},
        "next": {
            "title": titles[1 - slot],
            "starts_at": next_start,
            "ends_at": next_start + timedelta(hours=1),
        },
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
