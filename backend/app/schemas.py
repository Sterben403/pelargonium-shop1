import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FlowerType = Literal["zonal", "rosebud", "ivy", "star", "regal", "angel"]
Color = Literal["pink", "red", "white", "purple", "salmon"]
Status = Literal["new", "confirmed", "ready", "done", "cancelled"]
Delivery = Literal["pickup", "courier"]
Lang = Literal["ru", "kk", "en"]


def normalize_phone(raw: str) -> str | None:
    """Accepts +7 7XX XXX XX XX, 8 7XX..., 7XX... in any formatting; returns +7XXXXXXXXXX."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    return "+7" + digits if len(digits) == 10 else None


# ---------- varieties ----------

class Description(BaseModel):
    ru: str
    kk: str
    en: str


class PhotoCredit(BaseModel):
    author: str
    license: str
    source_url: str | None = None


class VarietyOut(BaseModel):
    id: int
    name: str
    type: FlowerType
    color: Color
    price: int
    stock: int
    description: Description
    photo_url: str | None
    photo_credit: PhotoCredit | None
    is_active: bool

    @classmethod
    def from_model(cls, v) -> "VarietyOut":
        credit = None
        if v.photo_author:
            credit = PhotoCredit(author=v.photo_author, license=v.photo_license or "", source_url=v.photo_source)
        # empty translations fall back to whatever text exists
        ru = v.desc_ru or v.desc_en or v.desc_kk
        return cls(
            id=v.id, name=v.name, type=v.type, color=v.color, price=v.price, stock=v.stock,
            description=Description(ru=ru, kk=v.desc_kk or ru, en=v.desc_en or ru),
            photo_url=v.photo_url, photo_credit=credit, is_active=v.is_active,
        )


class VarietyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    type: FlowerType
    color: Color
    price: int = Field(gt=0, le=1_000_000)
    stock: int = Field(ge=0, le=10_000)
    desc_ru: str = Field(default="", max_length=2000)
    desc_kk: str = Field(default="", max_length=2000)
    desc_en: str = Field(default="", max_length=2000)
    photo_url: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("name too short")
        return v

    @field_validator("photo_url")
    @classmethod
    def check_url(cls, v: str | None) -> str | None:
        if v and not re.match(r"^(https?://|/uploads/)", v):
            raise ValueError("photo_url must be http(s) or /uploads/")
        return v or None


class VarietyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    type: FlowerType | None = None
    color: Color | None = None
    price: int | None = Field(default=None, gt=0, le=1_000_000)
    stock: int | None = Field(default=None, ge=0, le=10_000)
    desc_ru: str | None = Field(default=None, max_length=2000)
    desc_kk: str | None = Field(default=None, max_length=2000)
    desc_en: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


# ---------- orders ----------

class OrderItemIn(BaseModel):
    variety_id: int
    qty: int = Field(ge=1, le=100)


class OrderCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str
    delivery: Delivery
    address: str = Field(default="", max_length=200)
    comment: str = Field(default="", max_length=500)
    lang: Lang = "ru"
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("name too short")
        return v

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        phone = normalize_phone(v)
        if not phone:
            raise ValueError("invalid phone")
        return phone

    @model_validator(mode="after")
    def address_for_courier(self) -> "OrderCreate":
        self.address = self.address.strip()
        if self.delivery == "courier" and len(self.address) < 5:
            raise ValueError("address required for courier")
        if self.delivery == "pickup":
            self.address = ""
        return self


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    variety_id: int
    name: str
    price: int
    qty: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    created_at: datetime
    customer_name: str
    phone: str
    delivery: Delivery
    address: str
    comment: str
    lang: Lang
    status: Status
    total: int
    items: list[OrderItemOut]


class OrderCreated(BaseModel):
    number: str
    total: int


class StatusUpdate(BaseModel):
    status: Status


# ---------- admin ----------

class LoginIn(BaseModel):
    password: str


class TokenOut(BaseModel):
    token: str
    expires_at: datetime


class Stats(BaseModel):
    new_orders: int
    in_progress: int
    revenue_done: int
    out_of_stock: int
