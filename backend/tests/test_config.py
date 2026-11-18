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


@pytest.mark.parametrize("raw, expected", [
    ("postgresql://u:p@ep-x.neon.tech/neondb?sslmode=require", "postgresql+psycopg://u:p@ep-x.neon.tech/neondb?sslmode=require"),
    ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
])
def test_hosted_database_urls_get_psycopg_driver(raw, expected):
    assert config._database_url(raw) == expected
