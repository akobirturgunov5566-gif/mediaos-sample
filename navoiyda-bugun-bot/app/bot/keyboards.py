from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from ..models import (
    IJARA_SUBTYPES,
    ISH_CATEGORIES,
    SHIKOYAT_CATEGORIES,
    TOPILDI_CATEGORIES,
    TOPILDI_SUBTYPES,
    Kind,
)

BTN_ISH = "🔍 Ish"
BTN_TOPILDI = "📦 Topildi / Yo'qoldi"
BTN_IJARA = "🏠 Ijara"
BTN_SHIKOYAT = "❗ Muammo"
BTN_MY = "📋 Mening e'lonlarim"
BTN_SETTINGS = "⚙️ Sozlamalar"
BTN_CANCEL = "❌ Bekor"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ISH), KeyboardButton(text=BTN_TOPILDI)],
            [KeyboardButton(text=BTN_IJARA), KeyboardButton(text=BTN_SHIKOYAT)],
            [KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)], [KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


remove = ReplyKeyboardRemove()


def section_kb(kind: Kind) -> InlineKeyboardMarkup:
    """Bo'limga kirganda: ko'rish yoki e'lon berish."""
    rows = [
        [InlineKeyboardButton(text="👀 E'lonlarni ko'rish", callback_data=f"browse:{kind.value}:*:0")],
        [InlineKeyboardButton(text="➕ E'lon berish", callback_data=f"new:{kind.value}")],
    ]
    if kind in (Kind.ISH, Kind.IJARA):
        rows.append([InlineKeyboardButton(text="🔔 Yangi e'lonlarga obuna", callback_data=f"subs:{kind.value}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _choices(options: dict[str, str], prefix: str, cols: int = 2) -> InlineKeyboardMarkup:
    btns = [InlineKeyboardButton(text=v, callback_data=f"{prefix}:{k}") for k, v in options.items()]
    rows = [btns[i : i + cols] for i in range(0, len(btns), cols)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ish_categories(prefix: str = "cat") -> InlineKeyboardMarkup:
    return _choices(ISH_CATEGORIES, prefix, cols=1)


def topildi_subtypes() -> InlineKeyboardMarkup:
    return _choices(TOPILDI_SUBTYPES, "sub")


def topildi_categories() -> InlineKeyboardMarkup:
    return _choices(TOPILDI_CATEGORIES, "cat", cols=1)


def ijara_subtypes() -> InlineKeyboardMarkup:
    return _choices(IJARA_SUBTYPES, "sub")


def shikoyat_categories() -> InlineKeyboardMarkup:
    return _choices(SHIKOYAT_CATEGORIES, "cat", cols=2)


def browse_filter_kb(kind: Kind) -> InlineKeyboardMarkup:
    if kind == Kind.ISH:
        opts = {"*": "Hammasi", **ISH_CATEGORIES}
        return _choices(opts, f"browse:{kind.value}", cols=1)
    if kind == Kind.TOPILDI:
        opts = {"*": "Hammasi", **TOPILDI_CATEGORIES}
        return _choices(opts, f"browse:{kind.value}", cols=1)
    if kind == Kind.IJARA:
        opts = {"*": "Hammasi", **IJARA_SUBTYPES}
        return _choices(opts, f"browse:{kind.value}", cols=1)
    opts = {"*": "Hammasi", **SHIKOYAT_CATEGORIES}
    return _choices(opts, f"browse:{kind.value}", cols=2)


def listing_actions(listing_id: int, *, hide_phone: bool, offset: int, kind: str, filt: str, has_more: bool) -> InlineKeyboardMarkup:
    rows = []
    if hide_phone:
        rows.append([InlineKeyboardButton(text="📩 Xabar ber", callback_data=f"contact:{listing_id}")])
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"browse:{kind}:{filt}:{max(0, offset - 5)}"))
    if has_more:
        nav.append(InlineKeyboardButton(text="▶️ Yana", callback_data=f"browse:{kind}:{filt}:{offset + 5}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else InlineKeyboardMarkup(inline_keyboard=[[]])


def moderation_kb(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqla", callback_data=f"mod:ok:{listing_id}"),
                InlineKeyboardButton(text="❌ Rad", callback_data=f"mod:no:{listing_id}"),
                InlineKeyboardButton(text="🚫 Spam", callback_data=f"mod:spam:{listing_id}"),
            ]
        ]
    )


def followup_kb(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, hal bo'ldi", callback_data=f"close:yes:{listing_id}"),
                InlineKeyboardButton(text="⏳ Hali yo'q", callback_data=f"close:no:{listing_id}"),
            ],
            [InlineKeyboardButton(text="🔕 O'chirish", callback_data="mute")],
        ]
    )


def my_listing_kb(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Yopish (hal bo'ldi)", callback_data=f"close:yes:{listing_id}")]]
    )


def settings_kb(notify: bool, subs: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔕 Bildirishnomani o'chirish" if notify else "🔔 Bildirishnomani yoqish", callback_data="mute" if notify else "unmute")],
        [InlineKeyboardButton(text="🔍 Ish obunalari", callback_data="subs:ish"), InlineKeyboardButton(text="🏠 Ijara obunalari", callback_data="subs:ijara")],
    ]
    if subs:
        rows.append([InlineKeyboardButton(text=f"Obunalar: {len(subs)} ta", callback_data="noop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subs_kb(kind: Kind, current: list[str]) -> InlineKeyboardMarkup:
    opts = {"*": "Hammasi"} | (ISH_CATEGORIES if kind == Kind.ISH else IJARA_SUBTYPES)
    rows = []
    for k, v in opts.items():
        key = f"{kind.value}:{k}"
        mark = "✅ " if key in current else "▫️ "
        rows.append([InlineKeyboardButton(text=mark + v, callback_data=f"sub_toggle:{key}")])
    rows.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def digest_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔕 Bu kategoriya kerak emas", callback_data="settings")],
        ]
    )
