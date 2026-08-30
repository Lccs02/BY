"""Print non-sensitive Bitable structure summary."""

from __future__ import annotations

from baoyan_tracker.bitable_service import BitableService
from baoyan_tracker.config import ConfigurationError, load_settings
from baoyan_tracker.feishu_client import FeishuAPIError, FeishuClient


def main() -> int:
    try:
        settings = load_settings()
        token = settings.resolved_app_token
        if not token:
            print("[FAIL] No Bitable URL/app token configured")
            return 2
        with FeishuClient(settings) as client:
            service = BitableService(client, token)
            for table in service.list_tables():
                fields = service.list_fields(str(table["table_id"]))
                views = service.list_views(str(table["table_id"]))
                records = service.list_records(str(table["table_id"]))
                print(
                    f"{table.get('name')}: {len(fields)} fields, "
                    f"{len(views)} views, {len(records)} records"
                )
        return 0
    except (ConfigurationError, FeishuAPIError) as exc:
        print(f"[FAIL] Inspect: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
