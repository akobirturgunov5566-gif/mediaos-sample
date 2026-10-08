from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal, init_db
from ..services import users as users_svc
from .handlers import make_routers
from .jobs import scheduler
from .middleware import DbSessionMiddleware

log = logging.getLogger(__name__)
def lifecycle_router() -> Router:
    r = Router(name="lifecycle")
    r.my_chat_member(F.chat.type == "private")(on_block)
    return r


async def on_block(event: ChatMemberUpdated, session: AsyncSession) -> None:
    """Odam botni blok qilsa / qaytarsa — metrika uchun."""
    status = event.new_chat_member.status
    if status in ("kicked", "left"):
        await users_svc.mark_blocked(session, event.from_user.id)
    elif status == "member":
        await users_svc.get_or_create_user(session, event.from_user.id, event.from_user.full_name, event.from_user.username)


def build_dispatcher(bot_username: str) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["bot_username"] = bot_username
    dp.update.middleware(DbSessionMiddleware(SessionLocal))
    # Tartib muhim: aniq-matnli tugmalar (start, my, browse) FSM matn handlerlaridan (create) OLDIN turadi
    dp.include_routers(lifecycle_router(), *make_routers())
    return dp


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN yo'q. .env faylini to'ldiring (.env.example ga qarang).")
    await init_db()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    dp = build_dispatcher(me.username)
    asyncio.create_task(scheduler(bot, SessionLocal, me.username))
    log.info("@%s ishga tushdi", me.username)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "my_chat_member"])


if __name__ == "__main__":
    asyncio.run(run())
