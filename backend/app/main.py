import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from . import config
from .db import Base, SessionLocal, engine
from .routers import admin, public, search, tilda
from .seed import seed_if_empty

log = logging.getLogger("pelargonium")


def wait_for_database(attempts: int = 30, delay: float = 1.0) -> None:
    """A database container may still be starting when the app starts: retry instead of crashing."""
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == attempts:
                raise
            log.warning("Database is not ready (attempt %s/%s), retrying in %ss", attempt, attempts, delay)
            time.sleep(delay)


@asynccontextmanager
async def lifespan(_: FastAPI):
    wait_for_database()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_if_empty(db)
    yield


app = FastAPI(title="Pelargonium Shop API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=config.CORS_ORIGIN_REGEX or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(search.router)
app.include_router(admin.router)
app.include_router(admin.protected)
app.include_router(tilda.router)

config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
# widget for Tilda (static/widget), owner workspace (static/admin), shared texts (static/i18n.json)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(STATIC_DIR / "admin" / "index.html")


@app.get("/demo", include_in_schema=False)
def demo_page():
    """A page that looks like the future Tilda site, with the widget embedded the same way."""
    return FileResponse(STATIC_DIR / "widget" / "demo.html")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/demo")


@app.get("/api/health", tags=["meta"])
def health(response: Response):
    """Used by the release job: the right commit is running and the database answers."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database, response.status_code = "unavailable", 503
    return {"status": "ok" if database == "ok" else "degraded", "database": database, "version": config.VERSION}
