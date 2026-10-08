from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC (baza ustunlari naive). datetime.utcnow() o'rniga."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
