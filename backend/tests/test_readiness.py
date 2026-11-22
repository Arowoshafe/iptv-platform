from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_database_not_configured_is_not_ready(monkeypatch):
    monkeypatch.delenv('DB_HOST', raising=False)
    r = client.get('/ready')
    assert r.status_code == 503
    assert r.json()['database'] == 'not-configured'


def test_migrated_database_is_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


def test_unapplied_schema_is_not_ready(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "REQUIRED_TABLES", ("public.table_that_is_not_migrated",))
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not-ready", "database": "schema-outdated"}
