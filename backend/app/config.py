"""Application settings, read from environment variables (or backend/.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# PostgreSQL from docker-compose.yml by default; any SQLAlchemy URL works (e.g. sqlite:///./dev.db)
def _database_url(url: str) -> str:
    # Hosted PostgreSQL (Neon, Render) gives postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg driver name
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _database_url(
    os.getenv("DATABASE_URL", "postgresql+psycopg://pelargonium:pelargonium@localhost:5433/pelargonium"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "pelargonium2026")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "12"))
CORS_ORIGINS = _list(os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8010"))
# Tilda pages live on *.tilda.ws (and the editor preview on tilda.cc); custom domains go to CORS_ORIGINS
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"https://([a-z0-9-]+\.)*tilda\.(ws|cc)")
TILDA_WEBHOOK_TOKEN = os.getenv("TILDA_WEBHOOK_TOKEN", "dev-tilda-token")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "8"))
# Commit the running build was made from (set by the Docker image build in CI)
# Render passes the deployed commit as RENDER_GIT_COMMIT
# Smart search: the shopper describes a plant in their own words and a local model picks varieties.
# Off by default (the hosted site has no model); with it off, or the model down, the regular search answers.
AI_SEARCH_ENABLED = os.getenv("AI_SEARCH_ENABLED", "false").lower() == "true"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "qwen2.5:3b")
AI_TIMEOUT_S = float(os.getenv("AI_TIMEOUT_S", "60"))
VERSION = os.getenv("APP_VERSION") or os.getenv("RENDER_GIT_COMMIT") or "dev"
IS_PRODUCTION = os.getenv("APP_ENV") == "production"

# Never run production with the demo secrets from this file.
if IS_PRODUCTION:
    _defaults = {"ADMIN_PASSWORD": "pelargonium2026", "SECRET_KEY": "dev-secret-change-me",
                 "TILDA_WEBHOOK_TOKEN": "dev-tilda-token"}
    _unsafe = [name for name, value in _defaults.items() if globals()[name] == value]
    if _unsafe:
        raise RuntimeError(f"Set these environment variables for production: {', '.join(_unsafe)}")
