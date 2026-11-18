from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Variety
from ..schemas import Color, FlowerType, OrderCreate, OrderCreated, VarietyOut
from ..services import place_order

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/varieties", response_model=list[VarietyOut])
def list_varieties(
    q: str = "",
    type: FlowerType | None = None,
    color: list[Color] = Query(default=[]),
    in_stock: bool = False,
    sort: Literal["default", "price_asc", "price_desc", "name"] = "default",
    db: Session = Depends(get_db),
):
    stmt = select(Variety).where(Variety.is_active.is_(True))
    if q.strip():
        stmt = stmt.where(func.lower(Variety.name).contains(q.strip().lower()))
    if type:
        stmt = stmt.where(Variety.type == type)
    if color:
        stmt = stmt.where(Variety.color.in_(color))
    if in_stock:
        stmt = stmt.where(Variety.stock > 0)
    order_by = {"price_asc": Variety.price.asc(), "price_desc": Variety.price.desc(),
                "name": func.lower(Variety.name)}.get(sort, Variety.id)
    return [VarietyOut.from_model(v) for v in db.scalars(stmt.order_by(order_by, Variety.id))]


@router.get("/varieties/{variety_id}", response_model=VarietyOut)
def get_variety(variety_id: int, db: Session = Depends(get_db)):
    v = db.get(Variety, variety_id)
    if not v or not v.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "variety_not_found"})
    return VarietyOut.from_model(v)


@router.post("/orders", response_model=OrderCreated, status_code=status.HTTP_201_CREATED)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    order = place_order(db, data)
    return OrderCreated(number=order.number, total=order.total)
