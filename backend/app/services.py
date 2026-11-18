"""Business rules that touch stock: placing orders and changing their status."""
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import Order, OrderItem, Variety
from .schemas import OrderCreate


def place_order(db: Session, data: OrderCreate) -> Order:
    # merge duplicate lines for the same variety
    wanted: dict[int, int] = defaultdict(int)
    for line in data.items:
        wanted[line.variety_id] += line.qty

    varieties = {v.id: v for v in db.scalars(
        select(Variety).where(Variety.id.in_(list(wanted)), Variety.is_active.is_(True)))}
    missing = [vid for vid in wanted if vid not in varieties]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "variety_not_found", "ids": missing})

    # Conditional UPDATE: decrements only if enough stock is left at this moment,
    # so two buyers can never take the last plant at the same time.
    short = []
    for vid, qty in wanted.items():
        res = db.execute(update(Variety).where(Variety.id == vid, Variety.stock >= qty)
                         .values(stock=Variety.stock - qty))
        if res.rowcount != 1:
            short.append({"variety_id": vid, "name": varieties[vid].name, "available": varieties[vid].stock})
    if short:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "out_of_stock", "items": short})

    order = Order(customer_name=data.name, phone=data.phone, delivery=data.delivery, address=data.address,
                  comment=data.comment.strip(), lang=data.lang, status="new",
                  total=sum(varieties[vid].price * qty for vid, qty in wanted.items()))
    order.items = [OrderItem(variety_id=vid, name=varieties[vid].name, price=varieties[vid].price, qty=qty)
                   for vid, qty in wanted.items()]
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def change_status(db: Session, order: Order, new_status: str) -> Order:
    """Cancelling returns plants to stock; un-cancelling takes them again (if still available)."""
    was_cancelled, now_cancelled = order.status == "cancelled", new_status == "cancelled"
    if was_cancelled and not now_cancelled:
        for item in order.items:
            res = db.execute(update(Variety).where(Variety.id == item.variety_id, Variety.stock >= item.qty)
                             .values(stock=Variety.stock - item.qty))
            if res.rowcount != 1:
                db.rollback()
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    detail={"code": "out_of_stock", "items": [{"variety_id": item.variety_id, "name": item.name}]})
    elif now_cancelled and not was_cancelled:
        for item in order.items:
            db.execute(update(Variety).where(Variety.id == item.variety_id).values(stock=Variety.stock + item.qty))
    order.status = new_status
    db.commit()
    db.refresh(order)
    return order
