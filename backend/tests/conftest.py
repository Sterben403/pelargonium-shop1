import os
import tempfile
from pathlib import Path

import pytest

# Configure an isolated database and upload folder before the app is imported.
# Default: the separate pelargonium_test database from docker-compose (created by backend/db/init.sql).
# Override with TEST_DATABASE_URL, e.g. sqlite:///./test.db to run without Docker.
_tmp = Path(tempfile.mkdtemp(prefix="pelargonium-test-"))
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://pelargonium:pelargonium@localhost:5433/pelargonium_test")
os.environ["UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["TILDA_WEBHOOK_TOKEN"] = "dev-tilda-token"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_if_empty(db)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin(client):
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
