"""Development-only catalog and rights model. No real channels or payments."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

APP_NAME = os.getenv("APP_NAME", "YOUR IPTV BRAND")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app = FastAPI(title=f"{APP_NAME} API", version="0.1.0")
Country = Literal["US", "NG"]

# Fictional stations for interface and rights-filtering tests ONLY.
# Do NOT add third-party streams without documentary redistribution rights.
CHANNELS = [
    {"id": "demo-news", "name": "Demo News", "category": "News", "countries": ["US", "NG"], "epg_now": "World Update", "icon": "📰", "playable": False},
    {"id": "demo-culture", "name": "Demo Culture", "category": "Culture", "countries": ["NG"], "epg_now": "Across Cultures", "icon": "🎭", "playable": False},
    {"id": "demo-lifestyle", "name": "Demo Lifestyle", "category": "Lifestyle", "countries": ["US"], "epg_now": "Everyday Living", "icon": "🌿", "playable": False},
    {"id": "demo-sports", "name": "Demo Sports", "category": "Sports", "countries": ["US", "NG"], "epg_now": "Sports Desk", "icon": "⚽", "playable": False},
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

@app.get("/api/v1/channels")
def channels(country: Country = Query(default="US")):
    return {"country": country, "channels": [{k: v for k, v in c.items() if k != "countries"} for c in CHANNELS if country in c["countries"]]}

@app.post("/api/v1/playback/session")
def playback_session(_: PlaybackRequest):
    # In production, require authentication, active subscription, geo-licensed rights,
    # device/session limits and a provider-approved token or signed CDN URL.
    raise HTTPException(status_code=403, detail="Playback unavailable: demo only. Connect a licensed provider and server-side entitlements first.")

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB_DIR / "index.html")
