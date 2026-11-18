"""Application settings, read from environment variables (or backend/.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# PostgreSQL from docker-compose.yml by default; any SQLAlchemy URL works (e.g. sqlite:///./dev.db)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://pelargonium:pelargonium@localhost:5433/pelargonium")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "pelargonium2026")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "12"))
CORS_ORIGINS = _list(os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8010"))
# Tilda pages live on *.tilda.ws (and the editor preview on tilda.cc); custom domains go to CORS_ORIGINS
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"https://([a-z0-9-]+\.)*tilda\.(ws|cc)")
TILDA_WEBHOOK_TOKEN = os.getenv("TILDA_WEBHOOK_TOKEN", "dev-tilda-token")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "8"))
