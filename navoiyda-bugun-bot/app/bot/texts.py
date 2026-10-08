"""Hamma matnlar bir joyda — o'zbek (lotin). Bot gapirmaydi, javob beradi."""
from __future__ import annotations

from ..models import (
    IJARA_SUBTYPES,
    ISH_CATEGORIES,
    SHIKOYAT_CATEGORIES,
    TOPILDI_CATEGORIES,
    TOPILDI_SUBTYPES,
    Kind,
    Listing,
)

WELCOME = (
    "Assalomu alaykum! Bu <b>Navoiyda Bugun</b> boti.\n\n"
    "Nima kerak?\n"
    "🔍 <b>Ish</b> — Vohada ish e'lonlari, maoshi bilan\n"
    "📦 <b>Topildi / Yo'qoldi</b> — bepul, darhol\n"
    "🏠 <b>Ijara</b> — uy, kvartira, xona\n"
    "❗ <b>Muammo</b> — svet, gaz, suv, yo'l: yozing, ko'taramiz"
)

MENU_HINT = "Kerakli bo'limni tanlang 👇"
CANCELLED = "Bekor qilindi. Menyu 👇"
ASK_PHONE = "Bog'lanish uchun telefon raqamingiz kerak. Pastdagi tugmani bosing 👇"
PHONE_SAVED = "Rahmat, saqlandi ✅"

KIND_NAMES = {
    Kind.ISH: "Ish",
    Kind.TOPILDI: "Topildi / Yo'qoldi",
    Kind.IJARA: "Ijara",
    Kind.SHIKOYAT: "Muammo",
}

SUBMITTED_FAST = "Qabul qilindi ✅ Moderator ko'rib chiqadi va e'loningiz darhol chiqadi."
SUBMITTED_DELAYED = (
    "Qabul qilindi ✅ Moderator tasdiqlagach e'lon <b>{delay} daqiqadan keyin</b> chiqadi.\n\n"
    "Darhol chiqishini xohlaysizmi? {need} ta do'stingiz shu havola orqali kirsa, keyingi e'loningiz "
    "navbatsiz chiqadi:\n{link}"
)
PUBLISHED_DM = "E'loningiz chiqdi 🎉\n{url}"
REJECTED_DM = "E'loningiz qabul qilinmadi ❌\nSabab: {reason}\n\nTuzatib qayta yuborishingiz mumkin."
FOLLOWUP_ISH = "3 kun o'tdi. «{title}» — odam topildimi?"
FOLLOWUP_TOPILDI = "3 kun o'tdi. «{title}» — topildimi?"
FOLLOWUP_IJARA = "3 kun o'tdi. «{title}» — ijara hal bo'ldimi?"
CLOSED_RESOLVED = "Zo'r! E'lon yopildi ✅ Kanalda «Topildi» belgisi qo'yiladi."
CLOSED_UNRESOLVED = "Tushunarli. E'lon yopildi, xohlasangiz yangisini bering."
MUTED = "Bildirishnomalar o'chirildi 🔕 Bot sizga o'zi yozmaydi. Yoqish: /sozlamalar"
UNMUTED = "Bildirishnomalar yoqildi 🔔"
NO_LISTINGS = "Hozircha e'lon yo'q."
CONTACT_SENT = "Xabaringiz e'lon egasiga yuborildi. U sizga o'zi yozadi."
CONTACT_INCOMING = "«{title}» e'loningiz bo'yicha {name} bog'lanmoqchi.\nYozish: tg://user?id={uid}"

FORM_ISH = {
    "category": "Qaysi yo'nalish?",
    "title": "Lavozim nomi? (masalan: Ofitsiant, Yuk tushiruvchi)",
    "salary": "Maosh? <b>Majburiy</b> — maoshsiz e'lon chiqmaydi. (masalan: 3 mln, kuniga 150 ming)",
    "location": "Qayerda? (tuman / mo'ljal)",
    "description": "Qo'shimcha shart (ish vaqti, tajriba). Bo'lmasa «-» yozing.",
}
FORM_TOPILDI = {
    "subtype": "Yo'qotdingizmi yoki topdingizmi?",
    "category": "Nima?",
    "title": "Qisqa tavsif (masalan: Qora Samsung telefon, chexolda)",
    "location": "Qayerda? (joy, ko'cha, vaqt)",
    "photo": "Rasm bo'lsa yuboring, bo'lmasa «-» yozing.",
}
FORM_IJARA = {
    "subtype": "Ijaraga berasizmi yoki qidiryapsizmi?",
    "title": "Nima? (masalan: 2 xonali kvartira, 1 xona talabaga)",
    "price": "Narx? (oyiga, so'mda)",
    "location": "Qayerda? (tuman / mo'ljal)",
    "description": "Shart va tafsilot (mebel, kim uchun). Bo'lmasa «-».",
}
FORM_SHIKOYAT = {
    "category": "Muammo nima haqida?",
    "title": "Qisqa: nima bo'ldi? (masalan: 3 kundan beri svet yo'q)",
    "location": "Qayerda? (ko'cha, mahalla)",
    "photo": "Rasm/video bo'lsa yuboring, bo'lmasa «-».",
}

HASHTAG = {
    Kind.ISH: "#VohadaIsh",
    Kind.TOPILDI: "#TopildiYoqoldi",
    Kind.IJARA: "#NavoiyIjara",
    Kind.SHIKOYAT: "#NavoiyMuammo",
}


def label(kind: Kind, listing: Listing) -> str:
    if kind == Kind.ISH:
        return ISH_CATEGORIES.get(listing.category or "", "")
    if kind == Kind.TOPILDI:
        return f"{TOPILDI_SUBTYPES.get(listing.subtype or '', '')} · {TOPILDI_CATEGORIES.get(listing.category or '', '')}"
    if kind == Kind.IJARA:
        return IJARA_SUBTYPES.get(listing.subtype or "", "")
    return SHIKOYAT_CATEGORIES.get(listing.category or "", "")


def render_post(listing: Listing, bot_username: str, *, resolved: bool = False) -> str:
    """Kanal posti. Topildi: telefon yashirin, bog'lanish bot orqali."""
    k = listing.kind
    head = f"{HASHTAG[k]} · {label(k, listing)}".strip(" ·")
    lines = [f"<b>{head}</b>", "", f"<b>{listing.title}</b>"]
    if k == Kind.ISH and listing.salary:
        lines.append(f"💰 Maosh: {listing.salary}")
    if k == Kind.IJARA and listing.price:
        lines.append(f"💰 Narx: {listing.price}")
    if listing.location:
        lines.append(f"📍 {listing.location}")
    if listing.description and listing.description != "-":
        lines.append(f"\n{listing.description}")
    if resolved:
        lines.append("\n✅ <b>TOPILDI / YOPILDI</b>")
    elif listing.hide_phone:
        lines.append(f"\n📩 Bog'lanish: https://t.me/{bot_username}?start=c{listing.id}")
    else:
        lines.append(f"\n📞 {listing.phone}")
    lines.append(f"\n<i>Navoiyda Bugun botida bepul berildi · @{bot_username}</i>")
    return "\n".join(lines)


def render_card(listing: Listing) -> str:
    """Bot ichida ko'rish uchun qisqa karta."""
    extra = listing.salary or listing.price or ""
    loc = f" · 📍 {listing.location}" if listing.location else ""
    return f"<b>{listing.title}</b>{(' · 💰 ' + extra) if extra else ''}{loc}"


def render_moderation(listing: Listing, user_name: str) -> str:
    return (
        f"🆕 <b>{KIND_NAMES[listing.kind]}</b> #{listing.id} · {'⚡ darhol' if listing.fast_track else '⏳ kutadi'}\n"
        f"👤 {user_name} · 📞 {listing.phone}\n"
        f"{label(listing.kind, listing)}\n\n"
        f"<b>{listing.title}</b>\n"
        f"{('💰 ' + (listing.salary or listing.price)) if (listing.salary or listing.price) else ''}\n"
        f"📍 {listing.location}\n{listing.description}"
    )


def render_stats(s: dict) -> str:
    alert = "\n⚠️ <b>Blok 5% dan oshdi — oxirgi yuborilgan xabarni to'xtating.</b>" if s["alert_block_rate"] else ""
    lst = "\n".join(
        f"• {KIND_NAMES[Kind(k)]}: {v['published']} chiqqan · {v['pending']} navbatda · {v['new_24h']} bugun"
        for k, v in s["listings"].items()
    )
    return (
        f"📊 <b>Bot holati</b>\n"
        f"Foydalanuvchi: {s['users_total']} (24 soat: +{s['users_new_24h']}, 7 kun: +{s['users_new_7d']})\n"
        f"7 kunlik tiriklik: {s['retention_7d_pct']}%\n"
        f"Blok: {s['blocked_total']} ({s['block_rate_pct']}%), 24 soatda {s['blocked_24h']}\n"
        f"🔕 O'chirgan: {s['muted']}\n\n{lst}{alert}"
    )
