from datetime import UTC, datetime

from baoyan_tracker.business_time import get_business_timezone, milliseconds_to_business_date


def test_utc_late_evening_maps_to_next_shanghai_business_date(monkeypatch):
    monkeypatch.setenv("BUSINESS_TIMEZONE", "Asia/Shanghai")
    get_business_timezone.cache_clear()
    moment = datetime(2026, 8, 31, 16, 30, tzinfo=UTC)
    assert milliseconds_to_business_date(int(moment.timestamp() * 1000)).isoformat() == "2026-09-01"
