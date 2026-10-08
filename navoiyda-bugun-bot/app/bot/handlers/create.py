"""E'lon berish oqimi (FSM). Telefon faqat shu yerda so'raladi, ko'rishda emas."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models import Kind, User
from ...services import listings as svc
from ...services import referrals, users as users_svc
from .. import keyboards as kb, texts
from ..publisher import safe_dm
from ..states import NewListing

router = Router(name="create")


def build() -> Router:
    """Shu moduldagi handlerlarning yangi, hali ulanmagan nusxasi."""
    from ._clone import clone_router

    return clone_router(router)

# Har tur uchun qadamlar tartibi
FLOW: dict[Kind, list[str]] = {
    Kind.ISH: ["category", "title", "salary", "location", "description"],
    Kind.TOPILDI: ["subtype", "category", "title", "location", "photo"],
    Kind.IJARA: ["subtype", "title", "price", "location", "description"],
    Kind.SHIKOYAT: ["category", "title", "location", "photo"],
}
FORMS = {Kind.ISH: texts.FORM_ISH, Kind.TOPILDI: texts.FORM_TOPILDI, Kind.IJARA: texts.FORM_IJARA, Kind.SHIKOYAT: texts.FORM_SHIKOYAT}
STATE = {
    "subtype": NewListing.subtype, "category": NewListing.category, "title": NewListing.title,
    "salary": NewListing.salary, "price": NewListing.price, "location": NewListing.location,
    "description": NewListing.description, "photo": NewListing.photo,
}


def _choice_kb(kind: Kind, step: str):
    if step == "subtype":
        return kb.topildi_subtypes() if kind == Kind.TOPILDI else kb.ijara_subtypes()
    if step == "category":
        return {Kind.ISH: kb.ish_categories(), Kind.TOPILDI: kb.topildi_categories(), Kind.SHIKOYAT: kb.shikoyat_categories()}[kind]
    return None


async def _ask(message: Message, state: FSMContext, kind: Kind, idx: int) -> bool:
    """Keyingi savolni beradi. Savollar tugagan bo'lsa True qaytaradi (chaqiruvchi yakunlaydi)."""
    steps = FLOW[kind]
    if idx >= len(steps):
        return True
    step = steps[idx]
    await state.update_data(step=idx)
    await state.set_state(STATE[step])
    markup = _choice_kb(kind, step)
    await message.answer(FORMS[kind][step], reply_markup=markup or kb.cancel_kb())
    return False


@router.callback_query(F.data.startswith("new:"))
async def new_listing(cq: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    kind = Kind(cq.data.split(":")[1])
    user, _ = await users_svc.get_or_create_user(session, cq.from_user.id, cq.from_user.full_name, cq.from_user.username)
    await state.clear()
    await state.update_data(kind=kind.value)
    await cq.answer()
    if not user.phone:
        await state.set_state(NewListing.phone)
        await cq.message.answer(texts.ASK_PHONE, reply_markup=kb.phone_kb())
        return
    await _ask(cq.message, state, kind, 0)  # birinchi qadam hech qachon yakun emas


@router.message(NewListing.phone, F.contact)
async def got_phone(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if message.contact.user_id and message.contact.user_id != message.from_user.id:
        await message.answer("Faqat o'z raqamingizni yuboring 👇", reply_markup=kb.phone_kb())
        return
    await users_svc.set_phone(session, message.from_user.id, message.contact.phone_number)
    await message.answer(texts.PHONE_SAVED, reply_markup=kb.remove)
    data = await state.get_data()
    await _ask(message, state, Kind(data["kind"]), 0)


@router.message(NewListing.phone)
async def phone_text(message: Message) -> None:
    await message.answer("Tugmani bosing 👇 (qo'lda yozmang)", reply_markup=kb.phone_kb())


# ---- tanlovli qadamlar (inline) ----

@router.callback_query(NewListing.subtype, F.data.startswith("sub:"))
async def pick_subtype(cq: CallbackQuery, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    await state.update_data(subtype=cq.data.split(":")[1])
    data = await state.get_data()
    await cq.answer()
    await cq.message.edit_reply_markup(reply_markup=None)
    if await _ask(cq.message, state, Kind(data["kind"]), data["step"] + 1):
        await finish_with_session(cq.message, state, session, bot_username, user_id=cq.from_user.id)


@router.callback_query(NewListing.category, F.data.startswith("cat:"))
async def pick_category(cq: CallbackQuery, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    await state.update_data(category=cq.data.split(":")[1])
    data = await state.get_data()
    await cq.answer()
    await cq.message.edit_reply_markup(reply_markup=None)
    if await _ask(cq.message, state, Kind(data["kind"]), data["step"] + 1):
        await finish_with_session(cq.message, state, session, bot_username, user_id=cq.from_user.id)


# ---- matnli qadamlar ----

async def _text_step(message: Message, state: FSMContext, session: AsyncSession, bot_username: str, field: str, max_len: int) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Matn yozing yoki «-».")
        return
    if field == "salary" and text == "-":
        await message.answer("Maosh majburiy. Masalan: 3 mln, yoki kuniga 150 ming.")
        return
    await state.update_data(**{field: text[:max_len]})
    data = await state.get_data()
    if await _ask(message, state, Kind(data["kind"]), data["step"] + 1):
        await finish_with_session(message, state, session, bot_username, user_id=message.from_user.id)


@router.message(NewListing.title, F.text)
async def step_title(message: Message, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    await _text_step(message, state, session, bot_username, "title", 160)


@router.message(NewListing.salary, F.text)
async def step_salary(message: Message, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    await _text_step(message, state, session, bot_username, "salary", 64)


@router.message(NewListing.price, F.text)
async def step_price(message: Message, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    await _text_step(message, state, session, bot_username, "price", 64)


@router.message(NewListing.location, F.text)
async def step_location(message: Message, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    await _text_step(message, state, session, bot_username, "location", 160)


@router.message(NewListing.description, F.text)
async def step_description(message: Message, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    await _text_step(message, state, session, bot_username, "description", 1000)


@router.message(NewListing.photo, F.photo)
async def step_photo(message: Message, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id, description=(message.caption or "").strip())
    data = await state.get_data()
    if await _ask(message, state, Kind(data["kind"]), data["step"] + 1):
        await finish_with_session(message, state, session, bot_username, user_id=message.from_user.id)


@router.message(NewListing.photo, F.text)
async def step_photo_skip(message: Message, state: FSMContext, session: AsyncSession, bot_username: str) -> None:
    data = await state.get_data()
    if await _ask(message, state, Kind(data["kind"]), data["step"] + 1):
        await finish_with_session(message, state, session, bot_username, user_id=message.from_user.id)


# ---- yakun ----

async def finish_with_session(message: Message, state: FSMContext, session: AsyncSession, bot_username: str, *, user_id: int) -> None:
    data = await state.get_data()
    await state.clear()
    kind = Kind(data["kind"])
    user = await session.get(User, user_id)
    payload = {**data, "phone": user.phone or "", "hide_phone": kind == Kind.TOPILDI}
    try:
        listing = await svc.create_listing(
            session, user.id, kind, payload,
            fast_track_cost=settings.fast_track_referrals, free_delay_minutes=settings.free_delay_minutes,
        )
    except svc.ListingError as e:
        await message.answer(f"❌ {e}", reply_markup=kb.main_menu())
        return

    if listing.fast_track:
        await message.answer(texts.SUBMITTED_FAST, reply_markup=kb.main_menu())
    else:
        await message.answer(
            texts.SUBMITTED_DELAYED.format(
                delay=settings.free_delay_minutes, need=settings.fast_track_referrals,
                link=referrals.ref_link(bot_username, user.id),
            ),
            reply_markup=kb.main_menu(), disable_web_page_preview=True,
        )
    # Moderatorlarga
    if settings.mod_chat_id:
        text = texts.render_moderation(listing, user.name)
        try:
            if listing.photo_file_id:
                await message.bot.send_photo(settings.mod_chat_id, listing.photo_file_id, caption=text[:1000], reply_markup=kb.moderation_kb(listing.id))
            else:
                await message.bot.send_message(settings.mod_chat_id, text, reply_markup=kb.moderation_kb(listing.id))
        except Exception:  # noqa: BLE001
            pass
