from datetime import datetime

from httpx import ASGITransport, AsyncClient

from app.bot import texts
from app.models import Kind, Listing, Status
from app.services import listings as svc, users


def test_render_post_hides_phone_for_topildi():
    l = Listing(id=7, kind=Kind.TOPILDI, subtype="topildi", category="telefon", title="Samsung topildi", location="Bozor", phone="+998901112233", hide_phone=True)
    text = texts.render_post(l, "navoiydabugun_bot")
    assert "+998901112233" not in text
    assert "start=c7" in text and "#TopildiYoqoldi" in text
    resolved = texts.render_post(l, "navoiydabugun_bot", resolved=True)
    assert "TOPILDI" in resolved and "start=c7" not in resolved


def test_render_post_ish_shows_salary_and_phone():
    l = Listing(id=1, kind=Kind.ISH, category="kunlik", title="Yuk tushirish", salary="150 ming", location="Karmana", phone="+99890", description="-")
    text = texts.render_post(l, "b")
    assert "150 ming" in text and "+99890" in text and "#VohadaIsh" in text


async def test_api_lists_only_published(session_factory, monkeypatch):
    from app.api import main as api

    monkeypatch.setattr(api, "SessionLocal", session_factory)
    async with session_factory() as s:
        await users.get_or_create_user(s, 1, "A")
        await users.set_phone(s, 1, "+1")
        pub = await svc.create_listing(s, 1, Kind.ISH, {"category": "ofis", "title": "Buxgalter", "salary": "5 mln", "location": "N", "phone": "+1"}, fast_track_cost=0, free_delay_minutes=0)
        await svc.approve(s, pub.id, 9, free_delay_minutes=0)
        await svc.mark_published(s, pub, 1)
        hidden = await svc.create_listing(s, 1, Kind.TOPILDI, {"subtype": "yoqoldi", "category": "kalit", "title": "Kalit", "location": "N", "phone": "+1"}, fast_track_cost=0, free_delay_minutes=0)
        await svc.approve(s, hidden.id, 9, free_delay_minutes=0)
        await svc.mark_published(s, hidden, 2)
        await svc.create_listing(s, 1, Kind.ISH, {"category": "ofis", "title": "Pending", "salary": "1", "location": "N", "phone": "+1"}, fast_track_cost=0, free_delay_minutes=0)
        await s.commit()

    async with AsyncClient(transport=ASGITransport(app=api.app), base_url="http://t") as c:
        r = await c.get("/api/listings", params={"kind": "ish"})
        assert r.status_code == 200
        assert [x["title"] for x in r.json()] == ["Buxgalter"]
        assert r.json()[0]["phone"] == "+1"
        r = await c.get("/api/listings", params={"kind": "topildi"})
        assert r.json()[0]["phone"] is None  # yashirin
        r = await c.get("/api/stats")
        assert r.json()["listings"]["ish"]["pending"] == 1
        assert (await c.get("/healthz")).json() == {"ok": True}
