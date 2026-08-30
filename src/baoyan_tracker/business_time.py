"""Single source of truth for timezone-aware business dates."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_BUSINESS_TIMEZONE = "Asia/Shanghai"


@lru_cache(maxsize=8)
def get_business_timezone(name: str | None = None) -> ZoneInfo:
    timezone_name = name or os.getenv("BUSINESS_TIMEZONE", DEFAULT_BUSINESS_TIMEZONE)
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown BUSINESS_TIMEZONE: {timezone_name}") from exc


def business_now(timezone_name: str | None = None) -> datetime:
    return datetime.now(tz=get_business_timezone(timezone_name))


def business_today(timezone_name: str | None = None) -> date:
    return business_now(timezone_name).date()


def milliseconds_to_business_date(value: float | str) -> date:
    return datetime.fromtimestamp(float(value) / 1000, tz=UTC).astimezone(
        get_business_timezone()
    ).date()
