import importlib

import pytest

from app import config


def test_health_reports_database_and_version(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "database": "ok", "version": "dev"}


def test_production_refuses_demo_secrets(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", "pelargonium2026")
    try:
        with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
            importlib.reload(config)
    finally:
        monkeypatch.undo()  # restore the test environment before re-reading settings
        importlib.reload(config)
    assert config.ADMIN_PASSWORD == "test-password"
