from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Event, Referral, User


def ref_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref{user_id}"


def parse_ref(payload: str | None) -> int | None:
    if payload and payload.startswith("ref") and payload[3:].isdigit():
        return int(payload[3:])
    return None


async def register_referral(session: AsyncSession, inviter_id: int, invited_id: int) -> bool:
    """Yangi odam referal havola bilan kirdi. O'ziga-o'zi yoki takror bo'lsa hisoblanmaydi."""
    if inviter_id == invited_id:
        return False
    inviter = await session.get(User, inviter_id)
    if inviter is None:
        return False
    exists = await session.scalar(select(Referral).where(Referral.invited_id == invited_id))
    if exists:
        return False
    session.add(Referral(inviter_id=inviter_id, invited_id=invited_id))
    inviter.ref_points += 1
    invited = await session.get(User, invited_id)
    if invited is not None:
        invited.referred_by = inviter_id
    session.add(Event(user_id=inviter_id, type="referral", payload={"invited": invited_id}))
    return True


async def spend_points(session: AsyncSession, user_id: int, amount: int) -> bool:
    user = await session.get(User, user_id)
    if user is None or user.ref_points < amount:
        return False
    user.ref_points -= amount
    return True
