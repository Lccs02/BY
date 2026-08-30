"""Plan or apply the idempotent Feishu Bitable initialization."""

from __future__ import annotations

import argparse

from baoyan_tracker.bitable_service import BitableService, PlannedChange
from baoyan_tracker.bootstrap import Bootstrapper
from baoyan_tracker.config import ConfigurationError, load_settings, save_app_token
from baoyan_tracker.feishu_client import FeishuAPIError, FeishuClient
from baoyan_tracker.schema import TABLE_SPECS


def _show_initial_plan() -> None:
    print(PlannedChange("CREATE BITABLE", "保研监督系统"))
    for spec in TABLE_SPECS:
        print(PlannedChange("CREATE TABLE", spec.name))
        for seed in spec.seeds:
            print(PlannedChange("CREATE SEED", f"{spec.name}/{seed[spec.unique_key]}"))


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show required changes only")
    mode.add_argument("--apply", action="store_true", help="Apply missing schema and seed data")
    args = parser.parse_args()

    try:
        settings = load_settings()
        with FeishuClient(settings) as client:
            client.authenticate()
            token = settings.resolved_app_token
            if not token and args.dry_run:
                _show_initial_plan()
                return 0
            if not token:
                service = BitableService.create_app(client, "保研监督系统")
                save_app_token(settings, service.app_token)
                print("APPLIED: CREATE BITABLE 保研监督系统")
            else:
                service = BitableService(client, token)
            result = Bootstrapper(service).run(apply=args.apply)
            if not result.changed:
                print("No changes required")
            else:
                prefix = "APPLIED" if args.apply else "PLAN"
                for change in result.changes:
                    print(f"{prefix}: {change}")
        return 0
    except (ConfigurationError, FeishuAPIError) as exc:
        print(f"[FAIL] Bootstrap: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
