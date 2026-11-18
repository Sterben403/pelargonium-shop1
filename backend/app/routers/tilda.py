"""Receiver for Tilda form submissions ("Webhook" in Tilda: Site settings → Forms).

Webhook URL to paste into Tilda:  https://<api-host>/api/tilda/webhook?token=<TILDA_WEBHOOK_TOKEN>

Understands two kinds of Tilda forms:
  * a plain form with fields  name, phone, variety, qty, delivery, address, comment
  * a Tilda cart (ST100 / T706): the `payment` field with the list of products
Tilda sends application/x-www-form-urlencoded; JSON is accepted too.
"""
import hmac
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Variety
from ..schemas import OrderCreate, OrderCreated
from ..services import place_order

router = APIRouter(prefix="/api/tilda", tags=["tilda"])
log = logging.getLogger("tilda")


async def _read_payload(request: Request) -> dict:
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        return data if isinstance(data, dict) else {}
    form = await request.form()
    return {k: v for k, v in form.multi_items() if isinstance(v, str)}


def _field(data: dict, *names: str) -> str:
    lowered = {k.lower(): v for k, v in data.items()}
    for n in names:
        if lowered.get(n.lower()):
            return str(lowered[n.lower()]).strip()
    return ""


def _cart_products(data: dict) -> list[tuple[str, int]]:
    """Products from a Tilda cart: `payment` as JSON, or flattened payment[products][i][name] keys."""
    payment = data.get("payment")
    if isinstance(payment, str):
        try:
            payment = json.loads(payment)
        except ValueError:
            payment = None
    if isinstance(payment, dict) and isinstance(payment.get("products"), list):
        out = []
        for p in payment["products"]:
            if isinstance(p, dict):
                out.append((str(p.get("name", "")), int(p.get("quantity") or 1)))
            elif isinstance(p, str):  # "Lord Bute - 1x5000 = 5000"
                m = re.match(r"(.+?)\s*-\s*(\d+)x", p)
                out.append((m.group(1), int(m.group(2))) if m else (p, 1))
        return out
    rows: dict[str, dict] = {}
    for key, value in data.items():
        m = re.fullmatch(r"payment\[products\]\[(\d+)\]\[(name|quantity)\]", key)
        if m:
            rows.setdefault(m.group(1), {})[m.group(2)] = value
    return [(r.get("name", ""), int(r.get("quantity") or 1)) for _, r in sorted(rows.items())]


def _match_variety(varieties: list[Variety], title: str) -> Variety | None:
    t = title.strip().lower()
    exact = next((v for v in varieties if v.name.lower() == t), None)
    # Tilda adds options to product titles ("Lord Bute, горшок 9 см") — fall back to prefix match
    return exact or next((v for v in varieties if t.startswith(v.name.lower())), None)


@router.post("/webhook", response_model=OrderCreated, status_code=status.HTTP_201_CREATED,
             responses={200: {"description": "Tilda connection test"}})
async def tilda_webhook(request: Request, db: Session = Depends(get_db)):
    data = await _read_payload(request)

    # When the webhook is connected, Tilda sends test=test and expects a 200 response.
    if data.get("test") == "test":
        return PlainTextResponse("ok")

    token = request.query_params.get("token") or _field(data, "token")
    if not hmac.compare_digest(token.encode(), config.TILDA_WEBHOOK_TOKEN.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "bad_token"})

    varieties = list(db.scalars(select(Variety).where(Variety.is_active.is_(True))))
    products = _cart_products(data)
    if not products and _field(data, "variety", "sort", "сорт"):
        qty = _field(data, "qty", "quantity", "количество")
        products = [(_field(data, "variety", "sort", "сорт"), int(qty) if qty.isdigit() else 1)]

    items, unknown = [], []
    for title, qty in products:
        v = _match_variety(varieties, title)
        if v:
            items.append({"variety_id": v.id, "qty": max(1, qty)})
        else:
            unknown.append(title)
    if unknown or not items:
        log.warning("Tilda order with unknown varieties %s: %s", unknown, data)
        raise HTTPException(422,
                            detail={"code": "variety_not_found", "names": unknown})

    delivery_raw = _field(data, "delivery", "доставка", "способ получения").lower()
    delivery = "courier" if ("кур" in delivery_raw or "courier" in delivery_raw) else "pickup"
    lang = _field(data, "lang")[:2].lower()
    try:
        order_in = OrderCreate(
            name=_field(data, "name", "имя"), phone=_field(data, "phone", "телефон"), delivery=delivery,
            address=_field(data, "address", "адрес"), comment=_field(data, "comment", "комментарий"),
            lang=lang if lang in ("ru", "kk", "en") else "ru", items=items)
    except ValidationError as e:
        log.warning("Invalid Tilda order: %s", e.errors())
        raise HTTPException(422,
                            detail={"code": "invalid_order", "errors": [err["msg"] for err in e.errors()]}) from e

    order = place_order(db, order_in)
    order.comment = (order.comment + " [Tilda]").strip()
    db.commit()
    return OrderCreated(number=order.number, total=order.total)
