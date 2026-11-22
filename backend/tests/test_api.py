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
