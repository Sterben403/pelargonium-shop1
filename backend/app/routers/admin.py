import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Order, Variety
from ..schemas import LoginIn, OrderOut, Stats, Status, StatusUpdate, TokenOut, VarietyCreate, VarietyOut, VarietyUpdate
from ..security import check_password, issue_token, require_admin
from ..services import change_status

router = APIRouter(prefix="/api/admin", tags=["admin"])
protected = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn):
    if not check_password(data.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "wrong_password"})
    token, expires = issue_token()
    return TokenOut(token=token, expires_at=expires)


# ---------- orders ----------

@protected.get("/orders", response_model=list[OrderOut])
def list_orders(status_filter: Status | None = Query(default=None, alias="status"), db: Session = Depends(get_db)):
    stmt = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    return list(db.scalars(stmt))


@protected.patch("/orders/{order_id}", response_model=OrderOut)
def update_order_status(order_id: int, data: StatusUpdate, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "order_not_found"})
    return change_status(db, order, data.status)


@protected.get("/stats", response_model=Stats)
def stats(db: Session = Depends(get_db)):
    count = lambda *cond: db.scalar(select(func.count()).select_from(Order).where(*cond)) or 0  # noqa: E731
    return Stats(
        new_orders=count(Order.status == "new"),
        in_progress=count(Order.status.in_(["confirmed", "ready"])),
        revenue_done=db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.status == "done")),
        out_of_stock=db.scalar(select(func.count()).select_from(Variety)
                               .where(Variety.is_active.is_(True), Variety.stock <= 0)) or 0,
    )


# ---------- varieties ----------

def _get_variety(db: Session, variety_id: int) -> Variety:
    v = db.get(Variety, variety_id)
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "variety_not_found"})
    return v


def _name_taken(db: Session, name: str, exclude_id: int | None = None, active_only: bool = True) -> bool:
    stmt = select(Variety.id).where(func.lower(Variety.name) == name.lower())
    if active_only:
        stmt = stmt.where(Variety.is_active.is_(True))
    if exclude_id:
        stmt = stmt.where(Variety.id != exclude_id)
    return db.scalar(stmt) is not None


@protected.get("/varieties", response_model=list[VarietyOut])
def admin_list_varieties(include_inactive: bool = False, db: Session = Depends(get_db)):
    stmt = select(Variety).order_by(Variety.id)
    if not include_inactive:
        stmt = stmt.where(Variety.is_active.is_(True))
    return [VarietyOut.from_model(v) for v in db.scalars(stmt)]


@protected.post("/varieties", response_model=VarietyOut, status_code=status.HTTP_201_CREATED)
def create_variety(data: VarietyCreate, db: Session = Depends(get_db)):
    if _name_taken(db, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "duplicate_name"})
    # a previously deleted variety with the same name is revived instead of duplicated
    old = db.scalar(select(Variety).where(func.lower(Variety.name) == data.name.lower()))
    v = old or Variety()
    for field, value in data.model_dump().items():
        setattr(v, field, value)
    v.is_active = True
    v.photo_author = v.photo_license = v.photo_source = None
    db.add(v)
    db.commit()
    db.refresh(v)
    return VarietyOut.from_model(v)


@protected.patch("/varieties/{variety_id}", response_model=VarietyOut)
def update_variety(variety_id: int, data: VarietyUpdate, db: Session = Depends(get_db)):
    v = _get_variety(db, variety_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        # names are unique across deleted varieties too (DB constraint)
        if _name_taken(db, changes["name"], exclude_id=v.id, active_only=False):
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "duplicate_name"})
    for field, value in changes.items():
        setattr(v, field, value)
    db.commit()
    db.refresh(v)
    return VarietyOut.from_model(v)


@protected.delete("/varieties/{variety_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variety(variety_id: int, db: Session = Depends(get_db)):
    # soft delete: past orders keep pointing at the variety
    v = _get_variety(db, variety_id)
    v.is_active = False
    db.commit()


@protected.post("/varieties/{variety_id}/photo", response_model=VarietyOut)
async def upload_photo(variety_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    v = _get_variety(db, variety_id)
    raw = await file.read(config.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(raw) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail={"code": "file_too_large"})
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")  # phone photos come rotated via EXIF
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"code": "not_an_image"}) from None
    img.thumbnail((1200, 1200))

    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    img.save(config.UPLOAD_DIR / name, "JPEG", quality=85, optimize=True)

    _remove_uploaded(v.photo_url)
    v.photo_url = f"/uploads/{name}"
    v.photo_author = v.photo_license = v.photo_source = None
    db.commit()
    db.refresh(v)
    return VarietyOut.from_model(v)


def _remove_uploaded(url: str | None) -> None:
    if url and url.startswith("/uploads/"):
        path = config.UPLOAD_DIR / url.removeprefix("/uploads/")
        if path.parent == config.UPLOAD_DIR and path.exists():
            path.unlink()
