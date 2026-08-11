"""Avto taqsimlash — Excel kontent plan yuklashda bo'sh qoldirilgan
ssenarist/operator/BF maydonlarini admin paneldan boshqariladigan
`AutoAssignmentRule` jadvali asosida to'ldirish.

Product decision (2026-04-25) — Phase 1: hardcoded loginlar emas, balki admin sozlangan
qoidalar.

Tanlash mantiqi:
  1. Faol qoidalarni `role_kind` bo'yicha tekshiramiz.
  2. `format_filter` to'g'ri kelishi kerak (yoki NULL — har formatga).
  3. Mavzuga `match_keywords` (vergul bilan ajratilgan) bo'yicha mos kelishi kerak;
     "*" — har qanday mavzu uchun.
  4. Birinchi mos qoida g'olib (priority DESC, sort_order ASC).
  5. Operator/BF uchun: shu kungi yuklamaga qarab eng kam yuklangani tanlanadi
     (qoidaga teng baho berilsa).
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AutoAssignmentRule, SyomkaPlan, User

ROLE_KINDS = ("ssenarist", "operator", "brand_face")


def _normalize(s: str | None) -> str:
    return (s or "").strip().lower()


def _split_keywords(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def _candidate_rules(
    db: Session,
    role_kind: str,
    format_name: str | None,
) -> Sequence[AutoAssignmentRule]:
    """role_kind + format_filter bo'yicha faol qoidalarni qaytaradi."""
    fmt_lower = _normalize(format_name)
    q = select(AutoAssignmentRule).where(
        AutoAssignmentRule.role_kind == role_kind,
        AutoAssignmentRule.is_active.is_(True),
    )
    rows = list(db.scalars(q).all())
    # format_filter bo'yicha filtrlash (None — har formatga)
    matches: list[AutoAssignmentRule] = []
    for r in rows:
        ff = _normalize(r.format_filter)
        if ff and ff != fmt_lower:
            continue
        matches.append(r)
    matches.sort(key=lambda r: (-int(r.priority or 0), int(r.sort_order or 0), int(r.id)))
    return matches


def _rule_matches_topic(rule: AutoAssignmentRule, topic: str) -> bool:
    keywords = _split_keywords(rule.match_keywords)
    if not keywords or "*" in keywords:
        return True
    t = _normalize(topic)
    return any(kw in t for kw in keywords)


def _user_active(db: Session, user_id: int) -> User | None:
    from services.staff_filters import is_tg_linked

    u = db.get(User, user_id)
    # triage-e: aktiv + TG ulangan (zombie'ni Excel avto-tayinlovga kiritmaymiz)
    if u and bool(getattr(u, "is_active", True)) and is_tg_linked(u):
        return u
    return None


def _least_loaded(db: Session, candidate_ids: list[int], on_date: date | None) -> int | None:
    """Bir necha nomzod ichidan eng kam yuklangani.

    Yuklama: shu kunga rejalashtirilgan SyomkaPlan operator/BF tayinlovlari soni.
    """
    if not candidate_ids:
        return None
    if on_date is None or len(candidate_ids) == 1:
        return candidate_ids[0]
    # operator + brand_face yuklamasini birgalikda hisoblaymiz (bir kishi ikkala
    # rolda ham bo'lishi mumkin emas, lekin bir kunga ko'p syomka — ha).
    ops_count = dict(
        db.execute(
            select(SyomkaPlan.operator_id, func.count(SyomkaPlan.id))
            .where(
                SyomkaPlan.date == on_date,
                SyomkaPlan.operator_id.in_(candidate_ids),
            )
            .group_by(SyomkaPlan.operator_id)
        ).all()
    )
    bf_count = dict(
        db.execute(
            select(SyomkaPlan.brand_face_id, func.count(SyomkaPlan.id))
            .where(
                SyomkaPlan.date == on_date,
                SyomkaPlan.brand_face_id.in_(candidate_ids),
            )
            .group_by(SyomkaPlan.brand_face_id)
        ).all()
    )
    best_id = candidate_ids[0]
    best_load = float("inf")
    for cid in candidate_ids:
        load = int(ops_count.get(cid, 0)) + int(bf_count.get(cid, 0))
        if load < best_load:
            best_load = load
            best_id = cid
    return best_id


def assign_user(
    db: Session,
    role_kind: str,
    format_name: str | None,
    topic: str,
    *,
    on_date: date | None = None,
) -> int | None:
    """Berilgan rol uchun mos foydalanuvchi ID sini qaytaradi yoki None.

    `role_kind`: "ssenarist" | "operator" | "brand_face".
    `topic`: slot mavzusi (kalit so'zlarga tekshirish uchun).
    `on_date`: operator/BF uchun yuklama tekshiriladigan kun (odatda syomka kuni).
    """
    if role_kind not in ROLE_KINDS:
        return None
    rules = _candidate_rules(db, role_kind, format_name)
    if not rules:
        return None

    # Mavzuga aniq mos keluvchi qoidalar
    aniq: list[AutoAssignmentRule] = []
    universal: list[AutoAssignmentRule] = []
    for r in rules:
        if _rule_matches_topic(r, topic):
            kws = _split_keywords(r.match_keywords)
            if "*" in kws or not kws:
                universal.append(r)
            else:
                aniq.append(r)

    # Aniq mos qoida bor bo'lsa — birinchisini olamiz (priority bo'yicha tartiblangan).
    for bucket in (aniq, universal):
        if not bucket:
            continue
        # Eng yuqori prioritet bilan qoidalardan kandidatlarni yig'amiz —
        # operator/BF uchun load-balance tanlash mumkin bo'lsin.
        top_priority = bucket[0].priority
        same_top = [r for r in bucket if r.priority == top_priority]
        candidate_ids: list[int] = []
        for r in same_top:
            u = _user_active(db, int(r.user_id))
            if u and int(u.id) not in candidate_ids:
                candidate_ids.append(int(u.id))
        if not candidate_ids:
            continue
        if role_kind == "ssenarist":
            return candidate_ids[0]
        # operator / brand_face — eng kam yuklangani
        return _least_loaded(db, candidate_ids, on_date)

    return None
