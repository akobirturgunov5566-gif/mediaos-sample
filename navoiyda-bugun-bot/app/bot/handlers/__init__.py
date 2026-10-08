"""Routerlar fabrika orqali: aiogram bitta Router'ni ikki Dispatcher'ga ulashga ruxsat bermaydi."""
from __future__ import annotations

import importlib

from aiogram import Router

# Tartib muhim: aniq-matnli tugmalar (start, my, browse) FSM matn handlerlaridan (create) OLDIN turadi
_ORDER = ("moderation", "start", "my", "browse", "create")


def make_routers() -> list[Router]:
    out = []
    for name in _ORDER:
        mod = importlib.import_module(f"{__name__}.{name}")
        out.append(mod.build())
    return out
