from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

FLOWER_TYPES = ("zonal", "rosebud", "ivy", "star", "regal", "angel")
COLORS = ("pink", "red", "white", "purple", "salmon")
ORDER_STATUSES = ("new", "confirmed", "ready", "done", "cancelled")
DELIVERY_METHODS = ("pickup", "courier")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Variety(Base):
    __tablename__ = "varieties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    color: Mapped[str] = mapped_column(String(20), index=True)
    price: Mapped[int] = mapped_column(Integer)  # tenge
    stock: Mapped[int] = mapped_column(Integer, default=0)  # rooted plants available
    desc_ru: Mapped[str] = mapped_column(Text, default="")
    desc_kk: Mapped[str] = mapped_column(Text, default="")
    desc_en: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str | None] = mapped_column(String(500))
    photo_author: Mapped[str | None] = mapped_column(String(120))
    photo_license: Mapped[str | None] = mapped_column(String(40))
    photo_source: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    customer_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(16))
    delivery: Mapped[str] = mapped_column(String(10))
    address: Mapped[str] = mapped_column(String(200), default="")
    comment: Mapped[str] = mapped_column(String(500), default="")
    lang: Mapped[str] = mapped_column(String(2), default="ru")
    status: Mapped[str] = mapped_column(String(12), default="new", index=True)
    total: Mapped[int] = mapped_column(Integer)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin")

    @property
    def number(self) -> str:
        return f"PS-{1000 + self.id}"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    variety_id: Mapped[int] = mapped_column(ForeignKey("varieties.id"))
    name: Mapped[str] = mapped_column(String(80))  # snapshot, survives renames
    price: Mapped[int] = mapped_column(Integer)  # snapshot at order time
    qty: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
