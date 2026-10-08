from __future__ import annotations

from ..util import utcnow

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Event, User


async def get_or_create_user(
    session: AsyncSession, tg_id: int, name: str = "", username: str | None = None
) -> tuple[User, bool]:
    """Foydalanuvchini qaytaradi; yangi bo'lsa yaratadi. (user, created)"""
    user = await session.get(User, tg_id)
    if user:
        user.last_seen_at = utcnow()
        if name and user.name != name:
            user.name = name
        if username != user.username:
            user.username = username
        if user.blocked:  # qaytib keldi
            user.blocked = False
            session.add(Event(user_id=tg_id, type="unblocked"))
        return user, False
    user = User(id=tg_id, name=name, username=username)
    session.add(user)
    session.add(Event(user_id=tg_id, type="start"))
    await session.flush()
    return user, True


async def set_phone(session: AsyncSession, tg_id: int, phone: str) -> None:
    await session.execute(update(User).where(User.id == tg_id).values(phone=phone))


async def set_notify(session: AsyncSession, tg_id: int, enabled: bool) -> None:
    await session.execute(update(User).where(User.id == tg_id).values(notify=enabled))
    session.add(Event(user_id=tg_id, type="notify_on" if enabled else "mute"))


async def mark_blocked(session: AsyncSession, tg_id: int) -> None:
    await session.execute(update(User).where(User.id == tg_id).values(blocked=True, notify=False))
    session.add(Event(user_id=tg_id, type="blocked"))


async def toggle_subscription(session: AsyncSession, tg_id: int, key: str) -> bool:
    """key: 'ish:haydovchi' yoki 'ijara:*'. Qaytaradi: endi obuna bormi."""
    user = await session.get(User, tg_id)
    subs = list(user.subscriptions or [])
    if key in subs:
        subs.remove(key)
        on = False
    else:
        subs.append(key)
        on = True
    user.subscriptions = subs
    session.add(Event(user_id=tg_id, type="sub_on" if on else "sub_off", payload={"key": key}))
    return on


async def subscribers_for(session: AsyncSession, kind: str, category: str | None) -> list[User]:
    """Shu kategoriya digestini olishga rozi bo'lganlar (notify=True, blocked=False)."""
    rows = (await session.execute(select(User).where(User.notify.is_(True), User.blocked.is_(False)))).scalars()
    out = []
    for u in rows:
        subs = set(u.subscriptions or [])
        if f"{kind}:*" in subs or (category and f"{kind}:{category}" in subs):
            out.append(u)
    return out
