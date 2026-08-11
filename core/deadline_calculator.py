"""Deadline kalkulyatori — post chiqish vaqtidan orqaga hisoblash.

Product decision (2026-04-25) — Phase 1: Excel kontent plan yuklashda har slot uchun
ssenariy → syomka → montaj → SMM tasdiq → abloshka → post zanjirining
deadline'lari avtomatik to'ldiriladi.

Format-ga qarab profillar:
  - reels      : klassik (ssen 2 kun oldin → syomka 1 kun oldin → montaj kechagi)
  - story      : tezkor (ssen 12 soat oldin, syomka post kuni, montaj 4 soat oldin)
  - kollab     : mijoz tayyor video → faqat ssen brief (1 kun oldin)
  - carousel   : reels'ga yaqin lekin montaj qisqaroq
  - tg / post  : tezkor matnli post (ssen 1 kun oldin, montaj — yo'q)

Profil mavjud bo'lmasa default reels'ga moslashadi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from tz import TASHKENT_TZ


@dataclass(frozen=True)
class DeadlineProfile:
    """Bitta format uchun orqaga hisoblash qoidalari."""

    ssenariy_offset: timedelta  # post`dan ssenariy deadline'igacha
    syomka_offset_days: int | None  # post kunidan necha kun oldin syomka (None = syomka yo'q)
    syomka_end_hour: int  # syomka kuni soat (deadline) — masalan 18 = 18:00
    montaj_offset: timedelta | None  # post`dan montaj deadline'igacha (None = montaj yo'q)
    smm_tasdiq_offset: timedelta  # post`dan SMM tasdiq deadline'igacha
    abloshka_offset: timedelta  # post`dan abloshka deadline'igacha


# Format → profil xaritasi (lower-case kalitlar bilan).
_PROFILES: dict[str, DeadlineProfile] = {
    "reels": DeadlineProfile(
        ssenariy_offset=timedelta(days=2, hours=15),
        syomka_offset_days=1,
        syomka_end_hour=18,
        montaj_offset=timedelta(hours=11),
        smm_tasdiq_offset=timedelta(hours=2),
        abloshka_offset=timedelta(hours=1),
    ),
    "story": DeadlineProfile(
        ssenariy_offset=timedelta(hours=12),
        syomka_offset_days=0,
        syomka_end_hour=14,
        montaj_offset=timedelta(hours=4),
        smm_tasdiq_offset=timedelta(hours=1),
        abloshka_offset=timedelta(minutes=30),
    ),
    "kollab": DeadlineProfile(
        ssenariy_offset=timedelta(days=1),
        syomka_offset_days=None,
        syomka_end_hour=0,
        montaj_offset=None,
        smm_tasdiq_offset=timedelta(hours=2),
        abloshka_offset=timedelta(hours=1),
    ),
    "carousel": DeadlineProfile(
        ssenariy_offset=timedelta(days=2),
        syomka_offset_days=1,
        syomka_end_hour=18,
        montaj_offset=timedelta(hours=8),
        smm_tasdiq_offset=timedelta(hours=2),
        abloshka_offset=timedelta(hours=1),
    ),
    "tg": DeadlineProfile(
        ssenariy_offset=timedelta(days=1),
        syomka_offset_days=None,
        syomka_end_hour=0,
        montaj_offset=None,
        smm_tasdiq_offset=timedelta(hours=2),
        abloshka_offset=timedelta(hours=1),
    ),
    "post": DeadlineProfile(
        ssenariy_offset=timedelta(days=1),
        syomka_offset_days=None,
        syomka_end_hour=0,
        montaj_offset=None,
        smm_tasdiq_offset=timedelta(hours=2),
        abloshka_offset=timedelta(hours=1),
    ),
}

_DEFAULT_PROFILE_KEY = "reels"


def _resolve_profile(format_name: str | None) -> DeadlineProfile:
    """Format nomidan profilga moslashish (case-insensitive, prefix match)."""
    if not format_name:
        return _PROFILES[_DEFAULT_PROFILE_KEY]
    key = format_name.strip().lower()
    if key in _PROFILES:
        return _PROFILES[key]
    # Prefiks bo'yicha (masalan "Reels (vertikal)" → reels)
    for k, profile in _PROFILES.items():
        if key.startswith(k):
            return profile
    return _PROFILES[_DEFAULT_PROFILE_KEY]


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TASHKENT_TZ)
    return dt


@dataclass
class CalculatedDeadlines:
    """Hisoblangan deadline'lar to'plami."""

    ssenariy_deadline: datetime
    syomka_kuni: date | None
    syomka_deadline: datetime | None
    montaj_deadline: datetime | None
    smm_tasdiq_deadline: datetime
    abloshka_deadline: datetime
    publish_deadline: datetime


def calculate_deadlines(
    post_dt: datetime,
    format_name: str | None,
    *,
    explicit_syomka_kuni: date | None = None,
) -> CalculatedDeadlines:
    """Berilgan post vaqtidan orqaga hisoblab deadline'larni qaytaradi.

    Args:
      post_dt: post chiqish sana+vaqti (Tashkent vaqti). tzinfo bo'lmasa Tashkent
        deb qabul qilinadi.
      format_name: Excel`dagi format nomi (case-insensitive).
      explicit_syomka_kuni: Excel`da `syomka_kuni` ustuni to'ldirilgan bo'lsa,
        profilning syomka_offset_days dan ustun.
    """
    profile = _resolve_profile(format_name)
    pdt = _aware(post_dt)

    # Ssenariy deadline (har doim hisoblanadi).
    ssen_dl = pdt - profile.ssenariy_offset

    # Syomka kuni va deadline (None — syomkasiz formatlar uchun).
    syomka_kuni: date | None = None
    syomka_dl: datetime | None = None
    if explicit_syomka_kuni is not None:
        syomka_kuni = explicit_syomka_kuni
    elif profile.syomka_offset_days is not None:
        syomka_kuni = (pdt - timedelta(days=profile.syomka_offset_days)).date()
    if syomka_kuni is not None:
        syomka_dl = datetime.combine(
            syomka_kuni, time(profile.syomka_end_hour, 0), tzinfo=TASHKENT_TZ
        )

    montaj_dl: datetime | None = None
    if profile.montaj_offset is not None:
        montaj_dl = pdt - profile.montaj_offset

    smm_dl = pdt - profile.smm_tasdiq_offset
    abl_dl = pdt - profile.abloshka_offset

    return CalculatedDeadlines(
        ssenariy_deadline=ssen_dl,
        syomka_kuni=syomka_kuni,
        syomka_deadline=syomka_dl,
        montaj_deadline=montaj_dl,
        smm_tasdiq_deadline=smm_dl,
        abloshka_deadline=abl_dl,
        publish_deadline=pdt,
    )


def known_format_keys() -> list[str]:
    """Test va admin paneli uchun mavjud profil kalitlari."""
    return list(_PROFILES.keys())
