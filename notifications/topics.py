"""GATE-7 · 2-QATLAM — Topic-arxitektura + rang-tili (BITTA joyda, D-talab).

8 semantik topic (forum-rejim) + 6 rangli holat-tili. Har GATE-7 topic quyi
`ForumTopicType` bilan bog'lanadi (mavjud routing/`resolve_thread_id` uchun) —
mavjud enum O'ZGARMAYDI, bu faqat markazlashtirilgan xarita.

Maxfiylik-chizig'i (ikki-brain, topic-darajada): maosh / aylanma / shaxsiy-KPI-tafsilot
FAQAT Founder-topic. Moliya: to'lov-holati → CEO, maosh/jami → Founder.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from models.enums import ForumTopicType


class Color(str, Enum):
    """Rang-tili — har xabar boshida holatni 1 emoji bilan bildiradi."""

    STARTED = "🟢"       # boshlandi
    YOUR_TURN = "🔵"     # navbat sizda
    ATTENTION = "🟡"     # e'tibor
    PROBLEM = "🔴"       # muammo (favqulodda)
    AI_TIP = "🟣"        # AI tavsiya
    RESULT = "🏆"        # natija


class Topic(str, Enum):
    """8 GATE-7 topic (yuqori-daraja semantik guruhlash)."""

    ELONLAR = "elonlar"            # 📢 E'lonlar
    AI = "ai"                      # 🤖 Bugun Media AI (tong/yakun/hafta/motivatsiya)
    KONTENT_ZAVODI = "kontent"     # 🎬 Kontent zavodi
    SMM = "smm"                    # 📲 SMM loyihalar
    MUAMMOLAR = "muammolar"        # 🚨 Muammolar (FAQAT muammo)
    NATIJALAR = "natijalar"        # 🏆 Natijalar
    CEO = "ceo"                    # 📊 CEO Operatsion
    FOUNDER = "founder"            # 👑 Founder (maxfiy)


@dataclass(frozen=True)
class TopicSpec:
    key: Topic
    emoji: str
    title: str
    founder_only: bool           # maxfiy — faqat Founder-topic
    # Mavjud forum-routing uchun quyi topic-turlari (resolve_thread_id kandidatlari).
    forum_types: tuple[ForumTopicType, ...]


TOPICS: dict[Topic, TopicSpec] = {
    Topic.ELONLAR: TopicSpec(
        Topic.ELONLAR, "📢", "E'lonlar", False,
        (ForumTopicType.OFFICIAL_NEWS, ForumTopicType.COMMUNICATION, ForumTopicType.UMUMIY),
    ),
    Topic.AI: TopicSpec(
        Topic.AI, "🤖", "Bugun Media AI", False,
        (ForumTopicType.MOTIVATION,),
    ),
    Topic.KONTENT_ZAVODI: TopicSpec(
        Topic.KONTENT_ZAVODI, "🎬", "Kontent zavodi", False,
        (ForumTopicType.DAILY_TASKS, ForumTopicType.SYOMKA, ForumTopicType.MONTAJ,
         ForumTopicType.SCENARIOS),
    ),
    Topic.SMM: TopicSpec(
        Topic.SMM, "📲", "SMM loyihalar", False,
        (ForumTopicType.SMM, ForumTopicType.MONTHLY_PROJECTS),
    ),
    Topic.MUAMMOLAR: TopicSpec(
        Topic.MUAMMOLAR, "🚨", "Muammolar", False,
        (ForumTopicType.TIZIM,),
    ),
    Topic.NATIJALAR: TopicSpec(
        Topic.NATIJALAR, "🏆", "Natijalar", False,
        (ForumTopicType.REPORTS, ForumTopicType.KPI),
    ),
    Topic.CEO: TopicSpec(
        Topic.CEO, "📊", "CEO Operatsion", False,
        (ForumTopicType.REPORT,),
    ),
    Topic.FOUNDER: TopicSpec(
        Topic.FOUNDER, "👑", "Founder", True,   # maxfiy
        (ForumTopicType.FINANCE,),
    ),
}


def spec(topic: Topic) -> TopicSpec:
    return TOPICS[topic]


def is_founder_only(topic: Topic) -> bool:
    """Maxfiylik-chizig'i: bu topic faqat Founder-uchunmi (maosh/aylanma/shaxsiy-KPI)."""
    return TOPICS[topic].founder_only


def forum_types_for(topic: Topic) -> tuple[ForumTopicType, ...]:
    """Mavjud `resolve_thread_id` uchun quyi forum-topic kandidatlari."""
    return TOPICS[topic].forum_types


def color_prefix(color: Color) -> str:
    """Xabar boshiga qo'yiladigan rang-emoji."""
    return color.value


# Rang → ma'no (rang-tili legendasi).
COLOR_MEANING: dict[Color, str] = {
    Color.STARTED: "boshlandi",
    Color.YOUR_TURN: "navbat sizda",
    Color.ATTENTION: "e'tibor",
    Color.PROBLEM: "muammo",
    Color.AI_TIP: "AI tavsiya",
    Color.RESULT: "natija",
}


def config_dict(include_founder: bool = True) -> dict:
    """GATE-7 topic-arxitekturasi konfiguratsiyasi (CEO panel / API uchun).

    include_founder=False bo'lsa maxfiy (founder_only) topiklar chiqarilmaydi (ikki-brain).
    Diqqat: bu FAQAT topic-konfiguratsiya (nom/routing/rang) — maxfiy topic ichidagi
    maosh/aylanma/shaxsiy-KPI MA'LUMOTI bu yerda yo'q.
    """
    topics = [
        {
            "key": s.key.value,
            "emoji": s.emoji,
            "title": s.title,
            "founder_only": s.founder_only,
            "forum_types": [ft.value for ft in s.forum_types],
        }
        for s in TOPICS.values()
        if include_founder or not s.founder_only
    ]
    colors = [{"emoji": c.value, "meaning": m} for c, m in COLOR_MEANING.items()]
    return {"topics": topics, "colors": colors}
