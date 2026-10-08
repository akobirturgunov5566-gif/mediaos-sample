"""Kelajakdagi "Navoiyda Bugun" ilovasi uchun REST API. Bot bilan bitta baza, bitta services qatlami.

Ishga tushirish: uvicorn app.api.main:app --port 8080
"""
from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import SessionLocal
from ..models import Kind, Listing
from ..services import listings as svc
from ..services import metrics

app = FastAPI(title="Navoiyda Bugun API", version="0.1.0")


async def get_session():
    async with SessionLocal() as s:
        yield s


class ListingOut(BaseModel):
    id: int
    kind: str
    subtype: str | None
    category: str | None
    title: str
    description: str
    salary: str | None
    price: str | None
    location: str
    phone: str | None
    photo_file_id: str | None
    published_at: datetime | None
    views: int

    @classmethod
    def of(cls, l: Listing) -> "ListingOut":
        return cls(
            id=l.id, kind=l.kind.value, subtype=l.subtype, category=l.category, title=l.title,
            description=l.description, salary=l.salary, price=l.price, location=l.location,
            phone=None if l.hide_phone else l.phone, photo_file_id=l.photo_file_id,
            published_at=l.published_at, views=l.views,
        )


@app.get("/api/listings", response_model=list[ListingOut])
async def list_listings(
    kind: Kind, category: str | None = None, subtype: str | None = None,
    limit: int = Query(20, le=50), offset: int = 0, session: AsyncSession = Depends(get_session),
):
    rows = await svc.browse(session, kind, category=category, subtype=subtype, limit=limit, offset=offset)
    return [ListingOut.of(l) for l in rows]


@app.get("/api/listings/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: int, session: AsyncSession = Depends(get_session)):
    l = await session.get(Listing, listing_id)
    if l is None or l.status.value != "published":
        raise HTTPException(404, "not found")
    l.views += 1
    await session.commit()
    return ListingOut.of(l)


@app.get("/api/stats")
async def stats(session: AsyncSession = Depends(get_session)):
    return await metrics.summary(session)


@app.get("/healthz")
async def healthz():
    return {"ok": True}
