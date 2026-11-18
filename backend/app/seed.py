"""Initial catalog: 15 varieties with Wikimedia Commons photos.

Runs automatically on first start (empty database). Manual reset:
    python -m app.seed --reset
"""
import json
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import Base, SessionLocal, engine
from .models import Variety

SEED_FILE = Path(__file__).with_name("seed_data.json")
FIELDS = ("name", "type", "color", "price", "stock", "desc_ru", "desc_kk", "desc_en",
          "photo_url", "photo_author", "photo_license", "photo_source")


def seed_if_empty(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(Variety)):
        return 0
    rows = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    db.add_all(Variety(**{k: row[k] for k in FIELDS}) for row in rows)
    db.commit()
    return len(rows)


if __name__ == "__main__":
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        print(f"seeded {seed_if_empty(session)} varieties")
