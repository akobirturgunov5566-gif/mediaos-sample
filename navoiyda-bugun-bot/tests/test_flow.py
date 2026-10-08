"""Handler darajasida to'liq oqim: /start → Ish → telefon → kategoriya → ... → moderatsiya → chiqarish.
Telegram'ga chiqmaydi: Bot sessiyasi mock qilingan, yuborilgan xabarlar ro'yxatga yoziladi.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import TelegramMethod
from aiogram.types import (
    CallbackQuery,
    Chat,
    Contact,
    Message,
    Update,
    User as TgUser,
)

from app.bot.handlers import make_routers
from app.bot.middleware import DbSessionMiddleware
from app.bot import jobs
from app.models import Kind, Listing, Status
from app.services import listings as svc

CHAT = Chat(id=1, type="private")
TG = TgUser(id=1, is_bot=False, first_name="Akobir")
BOT_USER = TgUser(id=999, is_bot=True, first_name="Bot", username="navoiydabugun_bot")
MOD_CHAT = -100500


class RecordingSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []
        self._id = 100

    async def close(self): ...

    async def stream_content(self, *a, **k):  # pragma: no cover
        yield b""

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None) -> Any:
        self.calls.append(method)
        name = type(method).__name__
        if name in ("SendMessage", "SendPhoto"):
            self._id += 1
            chat_id = getattr(method, "chat_id")
            return Message(message_id=self._id, date=datetime.now(), chat=Chat(id=chat_id, type="private" if chat_id > 0 else "supergroup"), from_user=BOT_USER, text=getattr(method, "text", None))
        if name == "GetMe":
            return BOT_USER
        return True

    def sent_texts(self, chat_id: int | None = None) -> list[str]:
        out = []
        for m in self.calls:
            if type(m).__name__ in ("SendMessage", "SendPhoto") and (chat_id is None or m.chat_id == chat_id):
                out.append(getattr(m, "text", None) or getattr(m, "caption", "") or "")
        return out


@pytest.fixture
async def env(session_factory, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "mod_chat_id", MOD_CHAT)
    monkeypatch.setattr(settings, "admin_ids", "42")
    monkeypatch.setattr(settings, "channel_id", -100777)
    monkeypatch.setattr(settings, "fast_track_referrals", 3)
    monkeypatch.setattr(settings, "free_delay_minutes", 120)

    rec = RecordingSession()
    bot = Bot("1:x", session=rec, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp["bot_username"] = "navoiydabugun_bot"
    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.include_routers(*make_routers())
    uid = {"n": 0}

    async def msg(text: str | None = None, *, contact: Contact | None = None, chat: Chat = CHAT, user: TgUser = TG):
        uid["n"] += 1
        m = Message(message_id=uid["n"], date=datetime.now(), chat=chat, from_user=user, text=text, contact=contact)
        await dp.feed_update(bot, Update(update_id=uid["n"], message=m))

    async def cb(data: str, *, chat: Chat = CHAT, user: TgUser = TG, msg_id: int = 1):
        uid["n"] += 1
        m = Message(message_id=msg_id, date=datetime.now(), chat=chat, from_user=BOT_USER, text="x")
        q = CallbackQuery(id=str(uid["n"]), from_user=user, chat_instance="ci", message=m, data=data)
        await dp.feed_update(bot, Update(update_id=uid["n"], callback_query=q))

    return bot, rec, msg, cb, session_factory


async def test_full_ish_flow_then_moderation_and_publish(env):
    bot, rec, msg, cb, sf = env

    await msg("/start")
    assert "Navoiyda Bugun" in rec.sent_texts(1)[-1]

    await msg("🔍 Ish")
    await cb("new:ish")
    assert "telefon" in rec.sent_texts(1)[-1].lower()  # telefon faqat e'lon berganda so'raladi

    await msg(contact=Contact(phone_number="+998901234567", first_name="A", user_id=1))
    await cb("cat:haydovchi")
    await msg("Haydovchi kerak")
    await msg("-")  # maosh "-" qabul qilinmaydi
    assert "majburiy" in rec.sent_texts(1)[-1].lower()
    await msg("4 mln")
    await msg("Navoiy, Karmana")
    await msg("Tajriba 2 yil")

    # foydalanuvchiga: kutadi + referal havola; moderatorga: karta + tugmalar
    assert "120 daqiqadan" in rec.sent_texts(1)[-1]
    assert "start=ref1" in rec.sent_texts(1)[-1]
    mod_msgs = rec.sent_texts(MOD_CHAT)
    assert len(mod_msgs) == 1 and "Haydovchi kerak" in mod_msgs[0] and "4 mln" in mod_msgs[0]

    async with sf() as s:
        l = (await s.execute(svc.select(Listing))).scalar_one()
        assert l.status == Status.PENDING and l.phone == "+998901234567"

    # begona odam moderatsiya tugmasini bosa olmaydi
    stranger = TgUser(id=7, is_bot=False, first_name="S")
    await cb(f"mod:ok:{l.id}", chat=Chat(id=7, type="private"), user=stranger)
    async with sf() as s:
        assert (await s.get(Listing, l.id)).status == Status.PENDING

    # moderator guruhidan tasdiqlash
    modr = TgUser(id=55, is_bot=False, first_name="Mod")
    await cb(f"mod:ok:{l.id}", chat=Chat(id=MOD_CHAT, type="supergroup"), user=modr)
    async with sf() as s:
        l = await s.get(Listing, l.id)
        assert l.status == Status.SCHEDULED and l.moderator_id == 55
        l.publish_after = datetime(2000, 1, 1)  # vaqt keldi deb hisoblaymiz
        await s.commit()

    n = await jobs.tick_publish(bot, sf, "navoiydabugun_bot")
    assert n == 1
    channel_posts = rec.sent_texts(-100777)
    assert len(channel_posts) == 1 and "#VohadaIsh" in channel_posts[0] and "+998901234567" in channel_posts[0]
    assert "chiqdi" in rec.sent_texts(1)[-1]
    async with sf() as s:
        l = await s.get(Listing, l.id)
        assert l.status == Status.PUBLISHED and l.channel_message_id is not None

    # Mening e'lonlarim → yopish
    await msg("📋 Mening e'lonlarim")
    assert "chiqqan" in rec.sent_texts(1)[-1]
    await cb(f"close:yes:{l.id}")
    async with sf() as s:
        assert (await s.get(Listing, l.id)).status == Status.CLOSED


async def test_topildi_flow_is_free_immediate_and_hides_phone(env):
    bot, rec, msg, cb, sf = env
    await msg("/start")
    await msg("📦 Topildi / Yo'qoldi")
    await cb("new:topildi")
    await msg(contact=Contact(phone_number="+998900000000", first_name="A", user_id=1))
    await cb("sub:topildi")
    await cb("cat:hujjat")
    await msg("Pasport topdim, Ergashev nomiga")
    await msg("Markaziy bozor, ertalab")
    await msg("-")
    assert "darhol" in rec.sent_texts(1)[-1].lower()
    assert "start=ref" not in rec.sent_texts(1)[-1]  # referal so'ralmaydi

    async with sf() as s:
        l = (await s.execute(svc.select(Listing))).scalar_one()
        assert l.fast_track and l.hide_phone
        await svc.approve(s, l.id, 55, free_delay_minutes=120)
        await s.commit()
    await jobs.tick_publish(bot, sf, "navoiydabugun_bot")
    post = rec.sent_texts(-100777)[0]
    assert "+998900000000" not in post and f"start=c{l.id}" in post

    # boshqa odam kanaldagi "Bog'lanish" orqali keladi
    other = TgUser(id=2, is_bot=False, first_name="Topuvchi")
    await msg(f"/start c{l.id}", chat=Chat(id=2, type="private"), user=other)
    await msg("Pasport mendami, qayerdasiz?", chat=Chat(id=2, type="private"), user=other)
    owner_dm = rec.sent_texts(1)[-1]
    assert "Topuvchi" in owner_dm and "tg://user?id=2" in owner_dm


async def test_cancel_and_mute(env):
    bot, rec, msg, cb, sf = env
    await msg("/start")
    await cb("new:ish")
    await msg("❌ Bekor")
    assert "Bekor" in rec.sent_texts(1)[-1]
    await msg("⚙️ Sozlamalar")
    await cb("mute")
    async with sf() as s:
        from app.models import User

        assert (await s.get(User, 1)).notify is False
