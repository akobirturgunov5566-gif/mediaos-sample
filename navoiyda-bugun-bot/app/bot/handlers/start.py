from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Kind, User
from ...services import listings as svc
from ...services import referrals, users as users_svc
from .. import keyboards as kb, texts
from ..states import Contact

router = Router(name="start")


def build() -> Router:
    """Shu moduldagi handlerlarning yangi, hali ulanmagan nusxasi."""
    from ._clone import clone_router

    return clone_router(router)

KIND_BY_BTN = {
    kb.BTN_ISH: Kind.ISH,
    kb.BTN_TOPILDI: Kind.TOPILDI,
    kb.BTN_IJARA: Kind.IJARA,
    kb.BTN_SHIKOYAT: Kind.SHIKOYAT,
}


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    tg = message.from_user
    user, created = await users_svc.get_or_create_user(session, tg.id, tg.full_name, tg.username)
    payload = command.args or ""

    # Referal: faqat yangi foydalanuvchi uchun hisoblanadi
    inviter = referrals.parse_ref(payload)
    if inviter and created:
        await referrals.register_referral(session, inviter, tg.id)

    # Kanal postidagi "Bog'lanish" havolasi: start=c<listing_id>
    if payload.startswith("c") and payload[1:].isdigit():
        await state.set_state(Contact.text)
        await state.update_data(listing_id=int(payload[1:]))
        await message.answer("E'lon egasiga qisqa xabar yozing (nima topdingiz / qayerdasiz):", reply_markup=kb.cancel_kb())
        return

    await message.answer(texts.WELCOME, reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_CANCEL)
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=kb.main_menu())


@router.message(F.text.in_(set(KIND_BY_BTN)))
async def open_section(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    kind = KIND_BY_BTN[message.text]
    tg = message.from_user
    await users_svc.get_or_create_user(session, tg.id, tg.full_name, tg.username)
    await message.answer(f"<b>{texts.KIND_NAMES[kind]}</b>", reply_markup=kb.section_kb(kind))


# ---------- Sozlamalar / 🔕 ----------

async def _settings_view(user: User) -> tuple[str, object]:
    status = "🔔 yoqilgan" if user.notify else "🔕 o'chirilgan"
    return f"<b>Sozlamalar</b>\nBildirishnoma: {status}\nReferal ball: {user.ref_points}", kb.settings_kb(user.notify, user.subscriptions or [])


@router.message(Command("sozlamalar", "settings"))
@router.message(F.text == kb.BTN_SETTINGS)
async def settings_cmd(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    user, _ = await users_svc.get_or_create_user(session, message.from_user.id, message.from_user.full_name, message.from_user.username)
    text, markup = await _settings_view(user)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "settings")
async def settings_cb(cq: CallbackQuery, session: AsyncSession) -> None:
    user, _ = await users_svc.get_or_create_user(session, cq.from_user.id)
    text, markup = await _settings_view(user)
    await cq.message.edit_text(text, reply_markup=markup)
    await cq.answer()


@router.callback_query(F.data.in_({"mute", "unmute"}))
async def mute_cb(cq: CallbackQuery, session: AsyncSession) -> None:
    on = cq.data == "unmute"
    await users_svc.get_or_create_user(session, cq.from_user.id)
    await users_svc.set_notify(session, cq.from_user.id, on)
    await cq.answer(texts.UNMUTED if on else texts.MUTED, show_alert=True)
    user = await session.get(User, cq.from_user.id)
    text, markup = await _settings_view(user)
    try:
        await cq.message.edit_text(text, reply_markup=markup)
    except Exception:  # noqa: BLE001  (digest xabaridan bosilgan bo'lsa matn boshqa)
        await cq.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("subs:"))
async def subs_cb(cq: CallbackQuery, session: AsyncSession) -> None:
    kind = Kind(cq.data.split(":")[1])
    user, _ = await users_svc.get_or_create_user(session, cq.from_user.id)
    await cq.message.edit_text(
        f"<b>{texts.KIND_NAMES[kind]} — obuna</b>\nTanlangan kategoriyalar bo'yicha har kuni 18:00 da bitta xabar keladi.",
        reply_markup=kb.subs_kb(kind, user.subscriptions or []),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("sub_toggle:"))
async def sub_toggle_cb(cq: CallbackQuery, session: AsyncSession) -> None:
    key = cq.data.split(":", 1)[1]
    kind = Kind(key.split(":")[0])
    await users_svc.get_or_create_user(session, cq.from_user.id)
    on = await users_svc.toggle_subscription(session, cq.from_user.id, key)
    user = await session.get(User, cq.from_user.id)
    if on and not user.notify:
        await users_svc.set_notify(session, cq.from_user.id, True)
    await cq.message.edit_reply_markup(reply_markup=kb.subs_kb(kind, user.subscriptions or []))
    await cq.answer("Obuna qo'shildi ✅" if on else "Obuna olindi")


@router.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery) -> None:
    await cq.answer()


# ---------- Bog'lanish (topildi: telefon yashirin) ----------

@router.message(Contact.text, F.text)
async def contact_text(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    listing = await svc.record_contact(session, data["listing_id"], message.from_user.id)
    if listing is None:
        await message.answer(texts.NO_LISTINGS, reply_markup=kb.main_menu())
        return
    from ..publisher import safe_dm  # lokal import: aylanma bog'liqlikdan qochish

    text = texts.CONTACT_INCOMING.format(title=listing.title, name=message.from_user.full_name, uid=message.from_user.id)
    text += f"\n\n💬 {message.text[:500]}"
    await safe_dm(message.bot, session, listing.user_id, text)
    await message.answer(texts.CONTACT_SENT, reply_markup=kb.main_menu())
