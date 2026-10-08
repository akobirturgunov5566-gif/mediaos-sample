"""Fon ishlari — bitta sikl, har 60 soniyada:
1) navbatdagi e'lonlarni chiqarish, 2) eskirganlarni yopish, 3) 3-kun so'rovi,
4) 18:00 da obunachilarga digest (kuniga 1 marta, faqat obuna bo'lgan kategoriya).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from ..util import utcnow
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..config import settings
from ..models import Kind, User
from ..services import listings as svc
from ..services import users as users_svc
from . import keyboards as kb, texts
from .publisher import publish, safe_dm

log = logging.getLogger(__name__)
FOLLOWUP_TEXT = {Kind.ISH: texts.FOLLOWUP_ISH, Kind.TOPILDI: texts.FOLLOWUP_TOPILDI, Kind.IJARA: texts.FOLLOWUP_IJARA}


async def tick_publish(bot: Bot, sf: async_sessionmaker, bot_username: str) -> int:
    async with sf() as session:
        due = await svc.due_for_publish(session)
        for l in due:
            await publish(bot, session, l, bot_username)
        await session.commit()
        return len(due)


async def tick_expire(sf: async_sessionmaker) -> int:
    async with sf() as session:
        rows = await svc.expire_old(session)
        await session.commit()
        return len(rows)


async def tick_followup(bot: Bot, sf: async_sessionmaker) -> int:
    async with sf() as session:
        rows = await svc.followups_due(session)
        n = 0
        for l in rows:
            l.followup_sent = True
            user = await session.get(User, l.user_id)
            if user and user.notify and not user.blocked:
                if await safe_dm(bot, session, l.user_id, FOLLOWUP_TEXT[l.kind].format(title=l.title), reply_markup=kb.followup_kb(l.id)):
                    n += 1
        await session.commit()
        return n


def build_digest(kind: Kind, rows: list, bot_username: str) -> str:
    head = "Bugungi ish e'lonlari" if kind == Kind.ISH else "Bugungi ijara e'lonlari"
    lines = [f"<b>{head}</b> ({len(rows)} ta)", ""]
    for l in rows[:10]:
        lines.append("• " + texts.render_card(l))
    if len(rows) > 10:
        lines.append(f"… yana {len(rows) - 10} ta botda")
    lines.append(f"\nTo'liq ro'yxat: @{bot_username}")
    return "\n".join(lines)


async def send_digest(bot: Bot, sf: async_sessionmaker, bot_username: str) -> int:
    """Har obunachiga bitta xabar: faqat o'zi tanlagan kategoriya, faqat bugun chiqqanlar."""
    since = utcnow() - timedelta(hours=24)
    sent = 0
    async with sf() as session:
        for kind in (Kind.ISH, Kind.IJARA):
            rows = await svc.published_since(session, kind, since)
            if not rows:
                continue
            subs = await users_svc.subscribers_for(session, kind.value, None)
            # umumiy obuna
            by_user: dict[int, list] = {}
            for u in subs:
                keys = set(u.subscriptions or [])
                if f"{kind.value}:*" in keys:
                    mine = rows
                else:
                    mine = [l for l in rows if f"{kind.value}:{l.category if kind == Kind.ISH else l.subtype}" in keys]
                if mine:
                    by_user[u.id] = mine
            for uid, mine in by_user.items():
                if await safe_dm(bot, session, uid, build_digest(kind, mine, bot_username), reply_markup=kb.digest_kb(), disable_web_page_preview=True):
                    sent += 1
        await session.commit()
    return sent


async def scheduler(bot: Bot, sf: async_sessionmaker, bot_username: str) -> None:
    tz = ZoneInfo(settings.timezone)
    hh, mm = (int(x) for x in settings.digest_time.split(":"))
    last_digest_day = None
    while True:
        try:
            n = await tick_publish(bot, sf, bot_username)
            if n:
                log.info("published %s", n)
            await tick_expire(sf)
            await tick_followup(bot, sf)
            now = datetime.now(tz)
            if now.hour == hh and now.minute >= mm and last_digest_day != now.date():
                last_digest_day = now.date()
                sent = await send_digest(bot, sf, bot_username)
                log.info("digest sent to %s users", sent)
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        await asyncio.sleep(60)
