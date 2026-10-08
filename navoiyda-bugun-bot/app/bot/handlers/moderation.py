"""Moderator guruhi: Tasdiqla / Rad / Spam. Adminlar: /stats, /broadcast."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import Listing, User
from ...services import listings as svc
from ...services import metrics
from .. import keyboards as kb, texts
from ..publisher import safe_dm
from ..states import RejectReason

router = Router(name="moderation")


def build() -> Router:
    """Shu moduldagi handlerlarning yangi, hali ulanmagan nusxasi."""
    from ._clone import clone_router

    return clone_router(router)


def _is_mod(cq_or_msg) -> bool:
    chat_id = cq_or_msg.message.chat.id if isinstance(cq_or_msg, CallbackQuery) else cq_or_msg.chat.id
    uid = cq_or_msg.from_user.id
    return chat_id == settings.mod_chat_id or uid in settings.admins


async def _strike(cq: CallbackQuery, suffix: str) -> None:
    try:
        if cq.message.photo:
            await cq.message.edit_caption(caption=(cq.message.caption or "") + f"\n\n{suffix}", reply_markup=None)
        else:
            await cq.message.edit_text((cq.message.text or "") + f"\n\n{suffix}", reply_markup=None)
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(F.data.startswith("mod:"))
async def moderate(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not _is_mod(cq):
        await cq.answer("Siz moderator emassiz", show_alert=True)
        return
    _, action, lid = cq.data.split(":")
    listing_id = int(lid)
    who = cq.from_user.full_name
    try:
        if action == "ok":
            listing = await svc.approve(session, listing_id, cq.from_user.id, free_delay_minutes=settings.free_delay_minutes)
            await _strike(cq, f"✅ Tasdiqladi: {who} · {'darhol' if listing.fast_track else str(settings.free_delay_minutes) + ' daqiqadan keyin'}")
            await cq.answer("Tasdiqlandi")
        elif action == "spam":
            listing = await svc.reject(session, listing_id, cq.from_user.id, "spam", spam=True)
            await _strike(cq, f"🚫 Spam: {who}")
            await safe_dm(cq.bot, session, listing.user_id, texts.REJECTED_DM.format(reason="e'lon qoidalarga mos emas"))
            await cq.answer("Spam deb belgilandi")
        else:  # no → sabab so'raymiz
            await state.set_state(RejectReason.text)
            await state.update_data(listing_id=listing_id, mod_msg_id=cq.message.message_id)
            await cq.answer()
            await cq.message.reply(f"#{listing_id} rad etish sababi? (bir qator, foydalanuvchiga boradi)")
    except svc.ListingError as e:
        await cq.answer(str(e), show_alert=True)


@router.message(RejectReason.text, F.text)
async def reject_reason(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not _is_mod(message):
        return
    data = await state.get_data()
    await state.clear()
    try:
        listing = await svc.reject(session, data["listing_id"], message.from_user.id, message.text)
    except svc.ListingError as e:
        await message.reply(str(e))
        return
    await safe_dm(message.bot, session, listing.user_id, texts.REJECTED_DM.format(reason=message.text[:160]))
    await message.reply(f"❌ #{listing.id} rad etildi. Egasiga sabab yuborildi.")


@router.message(Command("stats"))
async def stats(message: Message, session: AsyncSession) -> None:
    if message.from_user.id not in settings.admins and message.chat.id != settings.mod_chat_id:
        return
    s = await metrics.summary(session)
    await message.answer(texts.render_stats(s))


@router.message(Command("pending"))
async def pending(message: Message, session: AsyncSession) -> None:
    """Moderatsiya navbati — guruhdagi xabar yo'qolgan bo'lsa."""
    if not _is_mod(message):
        return
    from ...models import Status

    rows = (await session.execute(select(Listing).where(Listing.status == Status.PENDING).order_by(Listing.created_at).limit(10))).scalars().all()
    if not rows:
        await message.answer("Navbat bo'sh ✅")
        return
    for l in rows:
        user = await session.get(User, l.user_id)
        await message.answer(texts.render_moderation(l, user.name if user else "?"), reply_markup=kb.moderation_kb(l.id))


@router.message(Command("broadcast"))
async def broadcast(message: Message, session: AsyncSession) -> None:
    """Umumiy xabar — faqat admin, faqat notify=True bo'lganlarga, pastida 🔕 tugmasi.

    Qoida: haftada 1 martadan ko'p emas. Bu buyruq sanamaydi, lekin /stats dagi blok foizi ko'rsatadi.
    """
    if message.from_user.id not in settings.admins:
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Foydalanish: /broadcast <matn>")
        return
    users = (await session.execute(select(User).where(User.notify.is_(True), User.blocked.is_(False)))).scalars().all()
    sent = 0
    for u in users:
        if await safe_dm(message.bot, session, u.id, text, reply_markup=kb.digest_kb(), disable_web_page_preview=True):
            sent += 1
    await message.answer(f"Yuborildi: {sent}/{len(users)}")
