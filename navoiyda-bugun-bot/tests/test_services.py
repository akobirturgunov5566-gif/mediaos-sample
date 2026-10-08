from datetime import timedelta

from app.util import utcnow

import pytest
from app.util import utcnow

from app.models import Kind, Status
from app.services import listings as svc
from app.services import metrics, referrals, users


async def _user(session, uid=1, phone="+998901234567"):
    u, created = await users.get_or_create_user(session, uid, f"User{uid}")
    if phone:
        await users.set_phone(session, uid, phone)
    await session.flush()
    return u


ISH = {"category": "haydovchi", "title": "Haydovchi kerak", "salary": "4 mln", "location": "Navoiy", "description": "-", "phone": "+998901234567"}


async def test_ish_without_salary_rejected(session):
    await _user(session)
    with pytest.raises(svc.ListingError):
        await svc.create_listing(session, 1, Kind.ISH, {**ISH, "salary": None}, fast_track_cost=3, free_delay_minutes=120)


async def test_topildi_is_free_and_fast(session):
    await _user(session)
    l = await svc.create_listing(
        session, 1, Kind.TOPILDI,
        {"subtype": "yoqoldi", "category": "hujjat", "title": "Pasport yo'qoldi", "location": "Bozor", "phone": "+998901234567"},
        fast_track_cost=3, free_delay_minutes=120,
    )
    assert l.fast_track is True
    assert l.hide_phone is True  # telefon kanalda ko'rinmaydi
    l = await svc.approve(session, l.id, moderator_id=99, free_delay_minutes=120)
    assert l.status == Status.SCHEDULED
    assert l.publish_after <= utcnow()  # darhol


async def test_ish_free_is_delayed_but_referrals_fast_track(session):
    await _user(session, 1)
    l1 = await svc.create_listing(session, 1, Kind.ISH, ISH, fast_track_cost=3, free_delay_minutes=120)
    assert l1.fast_track is False
    await svc.approve(session, l1.id, 99, free_delay_minutes=120)
    assert l1.publish_after > utcnow() + timedelta(minutes=100)

    # 3 ta do'st referal bilan kirdi
    for uid in (2, 3, 4):
        await _user(session, uid, phone=None)
        assert await referrals.register_referral(session, 1, uid) is True
    assert (await session.get(users.User, 1)).ref_points == 3
    # takror va o'ziga-o'zi hisoblanmaydi
    assert await referrals.register_referral(session, 1, 2) is False
    assert await referrals.register_referral(session, 1, 1) is False

    l2 = await svc.create_listing(session, 1, Kind.ISH, ISH, fast_track_cost=3, free_delay_minutes=120)
    assert l2.fast_track is True
    assert (await session.get(users.User, 1)).ref_points == 0
    await svc.approve(session, l2.id, 99, free_delay_minutes=120)
    due = await svc.due_for_publish(session)
    assert [d.id for d in due] == [l2.id]


async def test_publish_close_expire_followup(session):
    await _user(session)
    l = await svc.create_listing(session, 1, Kind.ISH, ISH, fast_track_cost=0, free_delay_minutes=0)
    await svc.approve(session, l.id, 99, free_delay_minutes=0)
    await svc.mark_published(session, l, channel_message_id=555)
    assert l.status == Status.PUBLISHED and l.expires_at is not None

    # 3 kundan keyin follow-up
    assert await svc.followups_due(session) == []
    l.published_at = utcnow() - timedelta(days=4)
    assert [x.id for x in await svc.followups_due(session)] == [l.id]

    # begona yopa olmaydi
    await _user(session, 2)
    with pytest.raises(svc.ListingError):
        await svc.close(session, l.id, 2, resolved=True)
    l = await svc.close(session, l.id, 1, resolved=True)
    assert l.status == Status.CLOSED

    # eskirish
    l2 = await svc.create_listing(session, 1, Kind.IJARA, {"subtype": "beraman", "title": "2 xonali", "price": "2 mln", "location": "Karmana", "phone": "+9989"}, fast_track_cost=0, free_delay_minutes=0)
    await svc.approve(session, l2.id, 99, free_delay_minutes=0)
    await svc.mark_published(session, l2, None)
    l2.expires_at = utcnow() - timedelta(minutes=1)
    assert [x.id for x in await svc.expire_old(session)] == [l2.id]
    assert l2.status == Status.EXPIRED


async def test_reject_and_pending_limit(session):
    await _user(session)
    ids = []
    for _ in range(3):
        ids.append((await svc.create_listing(session, 1, Kind.ISH, ISH, fast_track_cost=0, free_delay_minutes=0)).id)
    with pytest.raises(svc.ListingError):  # 4-chi navbatga sig'maydi
        await svc.create_listing(session, 1, Kind.ISH, ISH, fast_track_cost=0, free_delay_minutes=0)
    l = await svc.reject(session, ids[0], 99, "maosh yo'q")
    assert l.status == Status.REJECTED and l.reject_reason == "maosh yo'q"
    with pytest.raises(svc.ListingError):  # ikki marta ko'rib bo'lmaydi
        await svc.reject(session, ids[0], 99, "x")


async def test_subscriptions_and_mute(session):
    await _user(session, 1)
    assert await users.toggle_subscription(session, 1, "ish:haydovchi") is True
    assert [u.id for u in await users.subscribers_for(session, "ish", "haydovchi")] == [1]
    assert await users.subscribers_for(session, "ish", "ofis") == []
    await users.set_notify(session, 1, False)  # 🔕
    assert await users.subscribers_for(session, "ish", "haydovchi") == []


async def test_metrics_block_alert(session):
    for uid in range(1, 11):
        await _user(session, uid, phone=None)
    await users.mark_blocked(session, 1)
    s = await metrics.summary(session)
    assert s["users_total"] == 10 and s["blocked_total"] == 1
    assert s["block_rate_pct"] == 10.0 and s["alert_block_rate"] is True
    # qaytib kelsa blok olinadi
    await users.get_or_create_user(session, 1, "User1")
    s = await metrics.summary(session)
    assert s["blocked_total"] == 0 and s["alert_block_rate"] is False
