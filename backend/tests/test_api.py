from fastapi.testclient import TestClient
from app.main import app

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
