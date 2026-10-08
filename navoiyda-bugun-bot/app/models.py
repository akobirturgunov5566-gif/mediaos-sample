"""Baza jadvallari. Bot ham, kelajakdagi ilova API'si ham shu jadvallarni ishlatadi."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Kind(str, enum.Enum):
    ISH = "ish"            # Vohada Ish — ish e'lonlari
    TOPILDI = "topildi"    # Topildi / Yo'qoldi
    IJARA = "ijara"        # Uy ijara
    SHIKOYAT = "shikoyat"  # Muammo / shikoyat (kontent manbai)


class Status(str, enum.Enum):
    PENDING = "pending"        # moderator kutilmoqda
    SCHEDULED = "scheduled"    # tasdiqlandi, FREE_DELAY dan keyin chiqadi
    PUBLISHED = "published"
    REJECTED = "rejected"
    SPAM = "spam"
    CLOSED = "closed"          # egasi yopdi (odam topildi / buyum topildi)
    EXPIRED = "expired"


# Ish kategoriyalari — 6 ta, ko'p emas
ISH_CATEGORIES: dict[str, str] = {
    "savdo": "🛒 Savdo",
    "ishlab_chiqarish": "🏭 Ishlab chiqarish / zavod",
    "xizmat": "🍽 Xizmat (oshpaz, ofitsiant...)",
    "haydovchi": "🚗 Haydovchi",
    "ofis": "💼 Ofis",
    "kunlik": "⚡ Kunlik ish",
}

TOPILDI_SUBTYPES: dict[str, str] = {
    "yoqoldi": "😟 Yo'qotdim",
    "topildi": "🙌 Topib oldim",
}

TOPILDI_CATEGORIES: dict[str, str] = {
    "hujjat": "📄 Hujjat (pasport, guvohnoma, raqam)",
    "telefon": "📱 Telefon",
    "kalit": "🔑 Kalit / sumka / hamyon",
    "hayvon": "🐈 Uy hayvoni",
    "boshqa": "📦 Boshqa",
}

IJARA_SUBTYPES: dict[str, str] = {
    "beraman": "🏠 Ijaraga beraman",
    "olaman": "🔍 Ijara qidiryapman",
}

SHIKOYAT_CATEGORIES: dict[str, str] = {
    "svet": "💡 Svet",
    "gaz": "🔥 Gaz",
    "suv": "🚰 Suv",
    "yol": "🛣 Yo'l",
    "chiqindi": "🗑 Chiqindi",
    "boshqa": "❗ Boshqa",
}

# E'lon necha kundan keyin o'z-o'zidan yopiladi
EXPIRE_DAYS: dict[Kind, int] = {
    Kind.ISH: 14,
    Kind.IJARA: 14,
    Kind.TOPILDI: 30,
    Kind.SHIKOYAT: 7,
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Telegram user id
    name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    referred_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ref_points: Mapped[int] = mapped_column(Integer, default=0)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)       # 🔕 tugmasi
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)     # botni blok qilgan
    subscriptions: Mapped[list] = mapped_column(JSON, default=list)   # ["ish:haydovchi", "ijara:*"]
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    listings: Mapped[list["Listing"]] = relationship(back_populates="user")


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[Kind] = mapped_column(Enum(Kind), index=True)
    subtype: Mapped[str | None] = mapped_column(String(32), nullable=True)   # yoqoldi/topildi, beraman/olaman
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ish/topildi/shikoyat kategoriyasi
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    salary: Mapped[str | None] = mapped_column(String(64), nullable=True)    # ish: majburiy
    price: Mapped[str | None] = mapped_column(String(64), nullable=True)     # ijara
    location: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    hide_phone: Mapped[bool] = mapped_column(Boolean, default=False)  # topildi: telefon yashirin, bot orqali bog'lanadi
    photo_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.PENDING, index=True)
    fast_track: Mapped[bool] = mapped_column(Boolean, default=False)
    publish_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    followup_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    channel_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moderator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    contacts: Mapped[int] = mapped_column(Integer, default=0)  # "Xabar ber" bosilgan soni

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user: Mapped["User"] = relationship(back_populates="listings")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invited_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Event(Base):
    """Metrika: start, blocked, unblocked, listing_created, listing_published, contact, mute."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
