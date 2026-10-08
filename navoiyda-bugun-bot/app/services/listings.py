"""E'lon hayot sikli: yaratish → moderatsiya → (kutish) → chiqarish → yopish/eskirish.

Bot ham, API ham faqat shu funksiyalarni chaqiradi. Telegram'ga yuborish bu yerda yo'q —
bu qatlam Telegram haqida bilmaydi, shuning uchun ilova ham bemalol ishlata oladi.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..util import utcnow

from sqlalchemy import func, select  # noqa: F401  (select testlarda ham ishlatiladi)
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import EXPIRE_DAYS, Event, Kind, Listing, Status, User
from . import referrals

FOLLOWUP_AFTER_DAYS = 3
MAX_PENDING_PER_USER = 3


class ListingError(Exception):
    pass


def _validate(kind: Kind, data: dict) -> None:
    if not data.get("title") or len(data["title"]) < 3:
        raise ListingError("Sarlavha juda qisqa.")
    if kind == Kind.ISH and not data.get("salary"):
        raise ListingError("Ish e'lonida maosh majburiy.")
    if kind in (Kind.ISH, Kind.IJARA, Kind.SHIKOYAT) and not data.get("phone"):
        raise ListingError("Telefon raqam kerak.")
    if kind == Kind.TOPILDI and not data.get("phone"):
        raise ListingError("Bog'lanish uchun telefon kerak (kanalda ko'rinmaydi).")


async def create_listing(
    session: AsyncSession, user_id: int, kind: Kind, data: dict, *, fast_track_cost: int, free_delay_minutes: int
) -> Listing:
    """E'lon yaratadi va moderatsiyaga qo'yadi.

    Qoidalar:
    - Topildi/Yo'qoldi va Shikoyat: bepul, shartsiz, tasdiqdan keyin darhol chiqadi.
    - Ish / Ijara: referal ballari yetsa darhol (fast_track), bo'lmasa FREE_DELAY dan keyin.
    """
    _validate(kind, data)
    pending = await session.scalar(
        select(func.count(Listing.id)).where(
            Listing.user_id == user_id, Listing.status.in_([Status.PENDING, Status.SCHEDULED])
        )
    )
    if (pending or 0) >= MAX_PENDING_PER_USER:
        raise ListingError("Sizda 3 ta e'lon navbatda turibdi. Avval ular chiqsin.")

    fast = kind in (Kind.TOPILDI, Kind.SHIKOYAT)
    if not fast and fast_track_cost > 0:
        fast = await referrals.spend_points(session, user_id, fast_track_cost)
    listing = Listing(
        user_id=user_id,
        kind=kind,
        subtype=data.get("subtype"),
        category=data.get("category"),
        title=data["title"].strip()[:160],
        description=(data.get("description") or "").strip(),
        salary=data.get("salary"),
        price=data.get("price"),
        location=(data.get("location") or "").strip()[:160],
        phone=data.get("phone", ""),
        hide_phone=bool(data.get("hide_phone", kind == Kind.TOPILDI)),
        photo_file_id=data.get("photo_file_id"),
        fast_track=fast,
        status=Status.PENDING,
    )
    session.add(listing)
    session.add(Event(user_id=user_id, type="listing_created", payload={"kind": kind.value, "fast": fast}))
    await session.flush()
    return listing


async def approve(session: AsyncSession, listing_id: int, moderator_id: int, *, free_delay_minutes: int) -> Listing:
    listing = await session.get(Listing, listing_id)
    if listing is None or listing.status != Status.PENDING:
        raise ListingError("E'lon topilmadi yoki allaqachon ko'rib chiqilgan.")
    listing.moderator_id = moderator_id
    now = utcnow()
    if listing.fast_track:
        listing.status = Status.SCHEDULED
        listing.publish_after = now
    else:
        listing.status = Status.SCHEDULED
        listing.publish_after = now + timedelta(minutes=free_delay_minutes)
    return listing


async def reject(session: AsyncSession, listing_id: int, moderator_id: int, reason: str, *, spam: bool = False) -> Listing:
    listing = await session.get(Listing, listing_id)
    if listing is None or listing.status != Status.PENDING:
        raise ListingError("E'lon topilmadi yoki allaqachon ko'rib chiqilgan.")
    listing.moderator_id = moderator_id
    listing.status = Status.SPAM if spam else Status.REJECTED
    listing.reject_reason = reason[:160]
    if spam:
        session.add(Event(user_id=listing.user_id, type="spam_marked", payload={"listing": listing.id}))
    return listing


async def due_for_publish(session: AsyncSession, now: datetime | None = None) -> list[Listing]:
    now = now or utcnow()
    rows = await session.execute(
        select(Listing).where(Listing.status == Status.SCHEDULED, Listing.publish_after <= now).order_by(Listing.publish_after)
    )
    return list(rows.scalars())


async def mark_published(session: AsyncSession, listing: Listing, channel_message_id: int | None) -> None:
    now = utcnow()
    listing.status = Status.PUBLISHED
    listing.published_at = now
    listing.channel_message_id = channel_message_id
    listing.expires_at = now + timedelta(days=EXPIRE_DAYS[listing.kind])
    session.add(Event(user_id=listing.user_id, type="listing_published", payload={"kind": listing.kind.value}))


async def close(session: AsyncSession, listing_id: int, user_id: int, *, resolved: bool) -> Listing:
    """Egasi yopdi. resolved=True → "Topildi ✅" / "Odam topildi ✅"."""
    listing = await session.get(Listing, listing_id)
    if listing is None or listing.user_id != user_id:
        raise ListingError("Bu e'lon sizniki emas.")
    if listing.status not in (Status.PUBLISHED, Status.SCHEDULED, Status.PENDING):
        return listing
    listing.status = Status.CLOSED
    session.add(Event(user_id=user_id, type="listing_closed", payload={"resolved": resolved, "kind": listing.kind.value}))
    return listing


async def expire_old(session: AsyncSession, now: datetime | None = None) -> list[Listing]:
    now = now or utcnow()
    rows = await session.execute(
        select(Listing).where(Listing.status == Status.PUBLISHED, Listing.expires_at <= now)
    )
    out = list(rows.scalars())
    for l in out:
        l.status = Status.EXPIRED
    return out


async def followups_due(session: AsyncSession, now: datetime | None = None) -> list[Listing]:
    """3 kundan keyin "Odam topildimi? / Buyum topildimi?" so'rash kerak bo'lganlar."""
    now = now or utcnow()
    cutoff = now - timedelta(days=FOLLOWUP_AFTER_DAYS)
    rows = await session.execute(
        select(Listing).where(
            Listing.status == Status.PUBLISHED,
            Listing.followup_sent.is_(False),
            Listing.published_at <= cutoff,
            Listing.kind.in_([Kind.ISH, Kind.TOPILDI, Kind.IJARA]),
        )
    )
    return list(rows.scalars())


async def record_contact(session: AsyncSession, listing_id: int, from_user: int) -> Listing | None:
    listing = await session.get(Listing, listing_id)
    if listing is None:
        return None
    listing.contacts += 1
    session.add(Event(user_id=from_user, type="contact", payload={"listing": listing_id}))
    return listing


async def user_listings(session: AsyncSession, user_id: int, limit: int = 10) -> list[Listing]:
    rows = await session.execute(
        select(Listing).where(Listing.user_id == user_id).order_by(Listing.created_at.desc()).limit(limit)
    )
    return list(rows.scalars())


async def browse(
    session: AsyncSession, kind: Kind, *, category: str | None = None, subtype: str | None = None, limit: int = 10, offset: int = 0
) -> list[Listing]:
    q = select(Listing).where(Listing.kind == kind, Listing.status == Status.PUBLISHED)
    if category:
        q = q.where(Listing.category == category)
    if subtype:
        q = q.where(Listing.subtype == subtype)
    q = q.order_by(Listing.published_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(q)).scalars())


async def published_since(session: AsyncSession, kind: Kind, since: datetime) -> list[Listing]:
    rows = await session.execute(
        select(Listing).where(Listing.kind == kind, Listing.status == Status.PUBLISHED, Listing.published_at >= since)
        .order_by(Listing.published_at.desc())
    )
    return list(rows.scalars())
