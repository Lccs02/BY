"""Run the destructive-but-cleaned Bitable write/read smoke test."""

from __future__ import annotations

import argparse

from baoyan_tracker.bitable_service import BitableService
from baoyan_tracker.config import ConfigurationError, load_settings, save_app_token
from baoyan_tracker.feishu_client import FeishuAPIError, FeishuClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--create-if-missing",
        action="store_true",
        help="Create the personal 保研监督系统 Bitable when no token is configured.",
    )
    args = parser.parse_args()
    try:
        settings = load_settings()
        with FeishuClient(settings) as client:
            client.authenticate()
            token = settings.resolved_app_token
            if token:
                service = BitableService(client, token)
                service.list_tables()
                print("[PASS] Bitable read access")
            elif args.create_if_missing:
                service = BitableService.create_app(client, "保研监督系统")
                save_app_token(settings, service.app_token)
                print("[PASS] Bitable create app")
            else:
                print("[FAIL] No Bitable URL/app token configured")
                return 2
            deleted = service.connection_test()
            if not deleted:
                print("[WARN] Test table renamed with DELETE_ME suffix; remove it in Feishu UI")
        return 0
    except (ConfigurationError, FeishuAPIError) as exc:
        print(f"[FAIL] Bitable connection: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
