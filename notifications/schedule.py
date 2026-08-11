"""GATE-7 · 3-QATLAM — Media OS ish-rejim / vaqt-darvoza (Asia/Tashkent).

Tamoyil: ODAM DAM OLADI — TIZIM ISHLAYDI. Xodimga yangi vazifa yoki oddiy eslatma faqat
ish-vaqtida yetkaziladi; ish-vaqtidan tashqarida NAVBATga qo'yiladi (yo'qolmaydi, keyingi
ish-tong 10:00 da chiqadi). AI (publish/statistika/monitoring/ertangi-brief) dam kuni ham
ishlaydi — faqat xodimga vazifa yubormaydi.

Ish-rejim: Dushanba–Shanba 10:00–20:00, tushlik 12:00–13:00, Yakshanba + O'zR bayrami = dam.

Vaqt-darvoza istisnolari (dam-vaqtda ham O'TADI):
  - 🔴 favqulodda-eskalatsiya (priority="red")
  - avto-publish jarayon-xabari (bypass_schedule=True)
  - Founder / CEO topic (bypass_schedule=True)

MUHIM (regressiya-keys): o'tgan deadline uchun "1 soat qoldi" HECH QACHON aytilmaydi.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from tz import TASHKENT_TZ

# ── Ish-rejim konstantalari (Asia/Tashkent) ──────────────────────────────────
WORK_START_HOUR = 10          # ish-tong 10:00
WORK_END_HOUR = 20            # 20:00 dan keyin = ish-vaqtidan tashqari
LUNCH_START_HOUR = 12         # tushlik 12:00–13:00: faqat 🔴 o'tadi
LUNCH_END_HOUR = 13
_SUNDAY = 6                   # date.weekday(): Dushanba=0 … Yakshanba=6

# O'zR belgilangan bayramlari (dam kuni). Oy-lunar hayitlar HAR YILI o'zgaradi —
# yangilanishi kerak (pastdagi 2026 hayit sanalari TASDIQLANSIN).
UZ_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 1),    # Yangi yil
    date(2026, 1, 14),   # Vatan himoyachilari kuni
    date(2026, 3, 8),    # Xotin-qizlar kuni
    date(2026, 3, 20),   # Ramazon hayit (taxminiy — tasdiqlansin)
    date(2026, 3, 21),   # Navro'z
    date(2026, 5, 9),    # Xotira va qadrlash kuni
    date(2026, 5, 27),   # Qurbon hayit (taxminiy — tasdiqlansin)
    date(2026, 9, 1),    # Mustaqillik kuni
    date(2026, 10, 1),   # O'qituvchi va murabbiylar kuni
    date(2026, 12, 8),   # Konstitutsiya kuni
}

# Runtime override (test/konfiguratsiya uchun). Bo'sh bo'lsa UZ_HOLIDAYS_2026 ishlatiladi.
_holidays_override: set[date] | None = None


def _to_tashkent(dt: datetime) -> datetime:
    """Naive → Tashkent deb olinadi; aware → Tashkentga keltiriladi."""
    return dt.replace(tzinfo=TASHKENT_TZ) if dt.tzinfo is None else dt.astimezone(TASHKENT_TZ)


def _holidays() -> set[date]:
    return _holidays_override if _holidays_override is not None else UZ_HOLIDAYS_2026


def set_holidays_override(days: set[date] | None) -> None:
    """Test/konfiguratsiya uchun bayram-to'plamini almashtirish."""
    global _holidays_override
    _holidays_override = days


def is_holiday(d: date) -> bool:
    return d in _holidays()


def is_rest_day(d: date) -> bool:
    """Yakshanba yoki O'zR bayrami = dam kuni."""
    return d.weekday() == _SUNDAY or is_holiday(d)


def is_working_day(d: date) -> bool:
    return not is_rest_day(d)


def is_within_work_hours(dt: datetime) -> bool:
    """Ish-soati oynasi ichida (10:00–20:00), ish kunida."""
    t = _to_tashkent(dt)
    return is_working_day(t.date()) and WORK_START_HOUR <= t.hour < WORK_END_HOUR


def is_lunch(dt: datetime) -> bool:
    """Tushlik oynasi (12:00–13:00) — bu vaqtda faqat 🔴 o'tadi."""
    t = _to_tashkent(dt)
    return LUNCH_START_HOUR <= t.hour < LUNCH_END_HOUR


def is_deliverable_now(dt: datetime) -> bool:
    """Oddiy (🔴 emas) xodim-xabari shu lahzada yetkazilishi mumkinmi.

    Ish kunida, 10:00–20:00 ichida, tushlik oynasidan tashqarida.
    """
    return is_within_work_hours(dt) and not is_lunch(dt)


def next_delivery_time(dt: datetime) -> datetime:
    """`dt` dan keyingi eng yaqin yetkazish lahzasi (oddiy xodim-xabari uchun).

    - Tushlik ichida → o'sha kun 13:00.
    - Ish kunida 10:00 dan oldin → o'sha kun 10:00.
    - Ish-soatidan keyin / dam kunida → keyingi ish-kuni 10:00.
    """
    t = _to_tashkent(dt)
    # Tushlik → shu kun 13:00 (ish kuni bo'lsa)
    if is_working_day(t.date()) and is_lunch(t):
        return t.replace(hour=LUNCH_END_HOUR, minute=0, second=0, microsecond=0)
    # Ish kunida ish-tongidan oldin → shu kun 10:00
    if is_working_day(t.date()) and t.hour < WORK_START_HOUR:
        return t.replace(hour=WORK_START_HOUR, minute=0, second=0, microsecond=0)
    # Ish kunida ish-soati ichida (tushlikdan tashqari) → hoziroq
    if is_deliverable_now(t):
        return t
    # Aks holda: keyingi ish-kuni 10:00
    nxt = t.date() + timedelta(days=1)
    while is_rest_day(nxt):
        nxt = nxt + timedelta(days=1)
    return datetime.combine(nxt, time(WORK_START_HOUR, 0), tzinfo=TASHKENT_TZ)


def should_deliver_now(
    now: datetime,
    *,
    priority: str = "normal",
    bypass_schedule: bool = False,
) -> tuple[bool, datetime | None]:
    """Vaqt-darvoza qarori.

    Qaytadi: (hozir_yetkazilsinmi, navbat_vaqti).
      - hozir=True  → navbat_vaqti=None.
      - hozir=False → navbat_vaqti = keyingi ish-lahzasi (xabar NAVBATga qo'yiladi).

    Istisnolar (doim hozir): priority=="red" (🔴 favqulodda), bypass_schedule=True
    (avto-publish jarayon-xabari, Founder/CEO topic).
    """
    if bypass_schedule or priority == "red":
        return True, None
    if is_deliverable_now(now):
        return True, None
    return False, next_delivery_time(now)


def time_left_label(deadline: datetime, now: datetime) -> str | None:
    """Deadlinegacha qolgan vaqt yorlig'i — o'tgan deadline uchun HECH QACHON qaytmaydi.

    Regressiya-keys: o'tib ketgan deadline'ga "1 soat qoldi" degan
    sanoq YUBORILMASIN. now >= deadline bo'lsa None qaytadi (chaqiruvchi "kechikdi"
    matnini ishlatishi kerak).
    """
    dl = _to_tashkent(deadline)
    n = _to_tashkent(now)
    if n >= dl:
        return None
    mins = int((dl - n).total_seconds() // 60)
    if mins < 60:
        return f"{mins} daqiqa qoldi"
    hours, rem = divmod(mins, 60)
    if rem == 0:
        return f"{hours} soat qoldi"
    return f"{hours} soat {rem} daqiqa qoldi"
