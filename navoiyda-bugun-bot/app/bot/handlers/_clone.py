from __future__ import annotations

from aiogram import Router


def clone_router(src: Router) -> Router:
    """Router'dagi barcha handlerlarni (filtrlari bilan) yangi, ulanmagan Router'ga ko'chiradi.

    aiogram bitta Router'ni ikki Dispatcher'ga ulashga ruxsat bermaydi; testlar va
    qayta ishga tushirishlar uchun har safar yangi nusxa kerak.
    """
    dst = Router(name=src.name)
    for event_name, observer in src.observers.items():
        target = dst.observers[event_name]
        for h in observer.handlers:
            target.register(h.callback, *[f.callback for f in (h.filters or [])], flags=dict(h.flags))
    return dst
