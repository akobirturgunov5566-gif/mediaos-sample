"""Sozlamalar — hammasi .env / environment orqali. Kodda token yo'q."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    channel_id: int = 0
    mod_chat_id: int = 0
    admin_ids: str = ""
    database_url: str = ""
    free_delay_minutes: int = 120
    fast_track_referrals: int = 3
    digest_time: str = "18:00"
    timezone: str = "Asia/Tashkent"

    @property
    def admins(self) -> set[int]:
        return {int(x) for x in self.admin_ids.split(",") if x.strip().isdigit()}

    @property
    def db_url(self) -> str:
        return self.database_url or "sqlite+aiosqlite:///./bot.db"


settings = Settings()
