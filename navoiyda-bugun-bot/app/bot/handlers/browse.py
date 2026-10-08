"""E'lonlarni ko'rish — ro'yxatdan o'tmasdan, telefon so'ramasdan."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Kind
from ...services import listings as svc
from .. import keyboards as kb, texts
from ..states import Contact

router = Router(name="browse")


def build() -> Router:
    """Shu moduldagi handlerlarning yangi, hali ulanmagan nusxasi."""
    from ._clone import clone_router

    return clone_router(router)
PAGE = 5


@router.callback_query(F.data.startswith("browse:"))
async def browse(cq: CallbackQuery, session: AsyncSession) -> None:
    _, kind_s, filt, offset_s = cq.data.split(":")
    kind = Kind(kind_s)
    offset = int(offset_s)
    category = subtype = None
    if filt != "*":
        if kind == Kind.IJARA:
            subtype = filt
        else:
            category = filt
    rows = await svc.browse(session, kind, category=category, subtype=subtype, limit=PAGE + 1, offset=offset)
    has_more = len(rows) > PAGE
    rows = rows[:PAGE]
    await cq.answer()
    if not rows:
        await cq.message.answer(texts.NO_LISTINGS + "\n\nFiltr:", reply_markup=kb.browse_filter_kb(kind))
        return
    if offset == 0:
        await cq.message.answer(f"<b>{texts.KIND_NAMES[kind]}</b> — filtr:", reply_markup=kb.browse_filter_kb(kind))
    for i, l in enumerate(rows):
        l.views += 1
        last = i == len(rows) - 1
        body = texts.render_card(l)
        if l.description and l.description != "-":
            body += f"\n{l.description[:300]}"
        if not l.hide_phone:
            body += f"\n📞 {l.phone}"
        markup = kb.listing_actions(l.id, hide_phone=l.hide_phone, offset=offset, kind=kind.value, filt=filt, has_more=has_more) if (last or l.hide_phone) else None
        if l.photo_file_id:
            await cq.message.answer_photo(l.photo_file_id, caption=body[:1000], reply_markup=markup)
        else:
            await cq.message.answer(body, reply_markup=markup)


@router.callback_query(F.data.startswith("contact:"))
async def contact(cq: CallbackQuery, state: FSMContext) -> None:
    listing_id = int(cq.data.split(":")[1])
    await state.set_state(Contact.text)
    await state.update_data(listing_id=listing_id)
    await cq.answer()
    await cq.message.answer("E'lon egasiga qisqa xabar yozing:", reply_markup=kb.cancel_kb())
