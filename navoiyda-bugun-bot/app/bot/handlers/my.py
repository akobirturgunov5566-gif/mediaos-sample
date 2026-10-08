from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Status
from ...services import listings as svc
from .. import keyboards as kb, texts
from ..publisher import mark_resolved_in_channel

router = Router(name="my")


def build() -> Router:
    """Shu moduldagi handlerlarning yangi, hali ulanmagan nusxasi."""
    from ._clone import clone_router

    return clone_router(router)

STATUS_UZ = {
    Status.PENDING: "⏳ moderatsiyada",
    Status.SCHEDULED: "🕒 navbatda",
    Status.PUBLISHED: "✅ chiqqan",
    Status.REJECTED: "❌ rad etilgan",
    Status.SPAM: "🚫 spam",
    Status.CLOSED: "🔒 yopilgan",
    Status.EXPIRED: "📁 muddati o'tgan",
}


@router.message(F.text == kb.BTN_MY)
async def my_listings(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    rows = await svc.user_listings(session, message.from_user.id)
    if not rows:
        await message.answer("Sizda hali e'lon yo'q. Bo'limni tanlab «➕ E'lon berish» bosing.", reply_markup=kb.main_menu())
        return
    for l in rows:
        text = f"{texts.render_card(l)}\n{STATUS_UZ[l.status]} · 👁 {l.views} · 📩 {l.contacts}"
        if l.reject_reason:
            text += f"\nSabab: {l.reject_reason}"
        markup = kb.my_listing_kb(l.id) if l.status in (Status.PUBLISHED, Status.SCHEDULED, Status.PENDING) else None
        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("close:"))
async def close_cb(cq: CallbackQuery, session: AsyncSession, bot_username: str) -> None:
    _, answer, lid = cq.data.split(":")
    resolved = answer == "yes"
    try:
        listing = await svc.close(session, int(lid), cq.from_user.id, resolved=resolved)
    except svc.ListingError as e:
        await cq.answer(str(e), show_alert=True)
        return
    if resolved:
        await mark_resolved_in_channel(cq.bot, listing, bot_username)
    await cq.answer()
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await cq.message.answer(texts.CLOSED_RESOLVED if resolved else texts.CLOSED_UNRESOLVED, reply_markup=kb.main_menu())
