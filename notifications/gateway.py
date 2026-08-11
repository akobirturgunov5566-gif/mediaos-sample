"""GATE-7 · E — NOTIFICATION GATEWAY (bitta darvoza).

Barcha bot-xabar shu yagona darvozadan o'tadi: (1) shablon+rol-render (templates) →
matn/rang/topic/tugma; (2) topic-routing + maxfiylik (topics); (3) vaqt-darvoza
(schedule) → hozir-yetkaz yoki NAVBAT.

MUHIM: bu darvoza QAROR + KOMPOZITSIYA qatlami. U FIZIK yubormaydi va dedup/flood/
idempotency'ga TEGMAYDI (temir-chegara). Chaqiruvchi `route()` natijasini oladi va
mavjud (o'zgarmagan) yuborish yo'li orqali jo'natadi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tz import now_tashkent

from . import schedule, templates
from .topics import Color, Topic, forum_types_for, is_founder_only


@dataclass
class GatewayDecision:
    deliver_now: bool                 # hozir yuborilsinmi
    queue_at: datetime | None         # yo'q bo'lsa — shu lahzada navbat-vaqti
    message: templates.Message        # tayyor matn/rang/topic/tugma
    topic: Topic
    color: Color
    founder_only: bool                # maxfiy topic (maosh/aylanma/shaxsiy-KPI)

    @property
    def forum_types(self):
        """Mavjud resolve_thread_id uchun quyi forum-topic kandidatlari."""
        return forum_types_for(self.topic)


# Vaqt-darvozani chetlab o'tadigan topiclar (leadership — doim yetkaziladi).
_BYPASS_TOPICS = (Topic.FOUNDER, Topic.CEO)


def route(
    event: str,
    role: str,
    ctx: dict | None = None,
    *,
    now: datetime | None = None,
    bypass_schedule: bool = False,
) -> GatewayDecision:
    """Hodisa → to'liq yetkazish qarori.

    bypass_schedule=True — avto-publish jarayon-xabari uchun (chaqiruvchi belgilaydi).
    Founder/CEO topiclari avtomatik bypass. 🔴 (Color.PROBLEM) → priority="red" → doim hozir.
    """
    now = now or now_tashkent()
    msg = templates.render(event, role, ctx)

    priority = "red" if msg.color == Color.PROBLEM else "normal"
    bypass = bypass_schedule or msg.topic in _BYPASS_TOPICS
    deliver_now, queue_at = schedule.should_deliver_now(
        now, priority=priority, bypass_schedule=bypass
    )

    return GatewayDecision(
        deliver_now=deliver_now,
        queue_at=queue_at,
        message=msg,
        topic=msg.topic,
        color=msg.color,
        founder_only=is_founder_only(msg.topic),
    )
