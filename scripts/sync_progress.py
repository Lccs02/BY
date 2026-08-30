"""Dry-run or apply calculated progress fields."""

from __future__ import annotations

import argparse

from baoyan_tracker.bitable_service import BitableService
from baoyan_tracker.config import ConfigurationError, load_settings
from baoyan_tracker.feishu_client import FeishuAPIError, FeishuClient
from baoyan_tracker.sync import sync_progress


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        settings = load_settings()
        token = settings.resolved_app_token
        if not token:
            print("[FAIL] No Bitable URL/app token configured")
            return 2
        with FeishuClient(settings) as client:
            changes = sync_progress(BitableService(client, token), apply=args.apply)
        if not changes:
            print("No changes required")
        else:
            prefix = "APPLIED" if args.apply else "PLAN"
            for change in changes:
                print(f"{prefix}: {change}")
        return 0
    except (ConfigurationError, FeishuAPIError, KeyError) as exc:
        print(f"[FAIL] Progress sync: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
