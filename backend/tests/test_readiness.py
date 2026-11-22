from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_database_not_configured_is_not_ready(monkeypatch):
    monkeypatch.delenv('DB_HOST', raising=False)
    r = client.get('/ready')
    assert r.status_code == 503
    assert r.json()['database'] == 'not-configured'
