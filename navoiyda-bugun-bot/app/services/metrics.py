"""3 ta raqam: start bosganlar, 7 kundan keyin tirik qolganlar, blok qilganlar."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..util import utcnow

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Event, Kind, Listing, Status, User


async def summary(session: AsyncSession, now: datetime | None = None) -> dict:
    now = now or utcnow()
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    total = await session.scalar(select(func.count(User.id))) or 0
    blocked = await session.scalar(select(func.count(User.id)).where(User.blocked.is_(True))) or 0
    muted = await session.scalar(select(func.count(User.id)).where(User.notify.is_(False), User.blocked.is_(False))) or 0
    new_7d = await session.scalar(select(func.count(User.id)).where(User.created_at >= week_ago)) or 0
    new_24h = await session.scalar(select(func.count(User.id)).where(User.created_at >= day_ago)) or 0
    # 7 kun oldin kelganlardan oxirgi 7 kunda qaytganlar
    cohort_total = await session.scalar(
        select(func.count(User.id)).where(User.created_at <= week_ago)
    ) or 0
    cohort_alive = await session.scalar(
        select(func.count(User.id)).where(User.created_at <= week_ago, User.last_seen_at >= week_ago, User.blocked.is_(False))
    ) or 0
    blocked_24h = await session.scalar(
        select(func.count(Event.id)).where(Event.type == "blocked", Event.created_at >= day_ago)
    ) or 0

    by_kind: dict[str, dict[str, int]] = {}
    for kind in Kind:
        pending = await session.scalar(
            select(func.count(Listing.id)).where(Listing.kind == kind, Listing.status == Status.PENDING)
        ) or 0
        published = await session.scalar(
            select(func.count(Listing.id)).where(Listing.kind == kind, Listing.status == Status.PUBLISHED)
        ) or 0
        today = await session.scalar(
            select(func.count(Listing.id)).where(Listing.kind == kind, Listing.created_at >= day_ago)
        ) or 0
        by_kind[kind.value] = {"pending": pending, "published": published, "new_24h": today}

    block_rate = round(100 * blocked / total, 1) if total else 0.0
    retention_7d = round(100 * cohort_alive / cohort_total, 1) if cohort_total else 0.0
    return {
        "users_total": total,
        "users_new_24h": new_24h,
        "users_new_7d": new_7d,
        "blocked_total": blocked,
        "blocked_24h": blocked_24h,
        "block_rate_pct": block_rate,
        "muted": muted,
        "retention_7d_pct": retention_7d,
        "alert_block_rate": block_rate > 5.0,
        "listings": by_kind,
    }
