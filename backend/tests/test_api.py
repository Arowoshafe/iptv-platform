from datetime import datetime, timezone

from fastapi.testclient import TestClient
from app.main import app, programme_guide

client = TestClient(app)

def test_health():
    assert client.get('/health').json()['status'] == 'ok'

def test_us_territory_catalog():
    ids = [c['id'] for c in client.get('/api/v1/channels?country=US').json()['channels']]
    assert 'demo-lifestyle' in ids
    assert 'demo-culture' not in ids

def test_ng_territory_catalog():
    ids = [c['id'] for c in client.get('/api/v1/channels?country=NG').json()['channels']]
    assert 'demo-culture' in ids
    assert 'demo-lifestyle' not in ids

def test_unknown_country_rejected():
    assert client.get('/api/v1/channels?country=GB').status_code == 422

def test_no_unlicensed_playback():
    res = client.post('/api/v1/playback/session', json={'channel_id': 'demo-sports'})
    assert res.status_code == 403


def test_demo_guide_rolls_over_at_midnight():
    titles = ("First programme", "Second programme")
    before = programme_guide(titles, datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc))
    after = programme_guide(titles, datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc))
    assert before["next"] == after["now"]
    assert before["now"]["ends_at"] == before["next"]["starts_at"]

    response = client.get("/api/v1/channels?country=NG")
    assert response.status_code == 200
    channels = response.json()["channels"]
    assert channels
    for channel in channels:
        assert channel["guide"]["now"]["title"] == channel["epg_now"]
        assert "programmes" not in channel


def test_playback_tester_is_available_only_when_enabled(monkeypatch):
    monkeypatch.delenv("ENABLE_LOCAL_PLAYLIST_TESTER", raising=False)
    assert client.get("/playlist-tester").status_code == 404

    monkeypatch.setenv("ENABLE_LOCAL_PLAYLIST_TESTER", "1")
    response = client.get("/playlist-tester")
    assert response.status_code == 200
    assert "Play Apple HLS sample" in response.text
    assert "Play test URL" in response.text


def test_channel_schedule_has_24_contiguous_slots():
    response = client.get("/api/v1/channels/demo-culture/schedule", params={"country": "NG"})
    assert response.status_code == 200
    data = response.json()
    assert data["country"] == "NG"
    assert data["name"] == "Demo Culture"
    shows = data["programmes"]
    assert len(shows) == 24
    assert len({show["title"] for show in shows}) == 4
    assert all(a["ends_at"] == b["starts_at"] for a, b in zip(shows, shows[1:]))


def test_channel_schedule_respects_territory():
    url = "/api/v1/channels/demo-culture/schedule"
    assert client.get(url, params={"country": "US"}).status_code == 404
    assert client.get(url, params={"country": "GB"}).status_code == 422
    assert client.get("/api/v1/channels/missing/schedule").status_code == 404


def test_subscriber_catalog_exposes_browse_and_account_controls():
    response = client.get("/catalog")
    assert response.status_code == 200
    for control in ("account-panel", "country", "channel-search", "favorites-only", "retry-catalog"):
        assert f'id="{control}"' in response.text
    assert 'href="/catalog"' in client.get("/").text
