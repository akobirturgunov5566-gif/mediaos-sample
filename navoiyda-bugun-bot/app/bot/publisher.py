"""Telegram'ga chiqarish — faqat shu fayl kanalga yozadi."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Listing
from ..services import listings as svc
from ..services import users as users_svc
from . import texts

log = logging.getLogger(__name__)


def channel_url(message_id: int | None) -> str:
    if not message_id or not settings.channel_id:
        return ""
    cid = str(settings.channel_id)
    internal = cid[4:] if cid.startswith("-100") else cid.lstrip("-")
    return f"https://t.me/c/{internal}/{message_id}"


async def safe_dm(bot: Bot, session: AsyncSession, user_id: int, text: str, **kw) -> bool:
    """Shaxsiy xabar. Blok qilgan bo'lsa belgilab qo'yamiz, xato tashlamaymiz."""
    try:
        await bot.send_message(user_id, text, **kw)
        return True
    except TelegramForbiddenError:
        await users_svc.mark_blocked(session, user_id)
        return False
    except Exception as e:  # noqa: BLE001
        log.warning("DM failed to %s: %s", user_id, e)
        return False


async def publish(bot: Bot, session: AsyncSession, listing: Listing, bot_username: str) -> None:
    text = texts.render_post(listing, bot_username)
    msg_id = None
    if settings.channel_id:
        try:
            if listing.photo_file_id:
                m = await bot.send_photo(settings.channel_id, listing.photo_file_id, caption=text)
            else:
                m = await bot.send_message(settings.channel_id, text, disable_web_page_preview=True)
            msg_id = m.message_id
        except Exception as e:  # noqa: BLE001
            log.error("channel publish failed for #%s: %s", listing.id, e)
            return  # keyingi aylanishda yana uriniladi
    await svc.mark_published(session, listing, msg_id)
    await safe_dm(bot, session, listing.user_id, texts.PUBLISHED_DM.format(url=channel_url(msg_id) or "(kanal)"))


async def mark_resolved_in_channel(bot: Bot, listing: Listing, bot_username: str) -> None:
    if not (settings.channel_id and listing.channel_message_id):
        return
    text = texts.render_post(listing, bot_username, resolved=True)
    try:
        if listing.photo_file_id:
            await bot.edit_message_caption(chat_id=settings.channel_id, message_id=listing.channel_message_id, caption=text)
        else:
            await bot.edit_message_text(text, chat_id=settings.channel_id, message_id=listing.channel_message_id, disable_web_page_preview=True)
    except Exception as e:  # noqa: BLE001
        log.warning("edit channel post failed #%s: %s", listing.id, e)
