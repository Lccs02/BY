"""Generate configured daily tasks for one date or a short future window."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from baoyan_tracker.bitable_service import BitableService
from baoyan_tracker.config import ConfigurationError, load_settings
from baoyan_tracker.feishu_client import FeishuAPIError, FeishuClient
from baoyan_tracker.task_generator import (
    TaskRulesNotFoundError,
    generate_daily_tasks,
    load_task_rules,
    resolve_dates,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TASK_RULES_PATH = REPOSITORY_ROOT / "config" / "task_rules.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--date", type=date.fromisoformat)
    target.add_argument("--today", action="store_true")
    target.add_argument("--days", type=int)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        rules = load_task_rules(TASK_RULES_PATH)
        dates = resolve_dates(
            explicit_date=args.date,
            today_only=args.today,
            days=args.days,
            default_days=rules.default_days,
        )
        settings = load_settings()
        token = settings.resolved_app_token
        if not token:
            print("[FAIL] No Bitable URL/app token configured")
            return 2
        with FeishuClient(settings) as client:
            changes = generate_daily_tasks(
                BitableService(client, token), rules, dates, apply=args.apply, force=args.force
            )
        if not changes:
            print("No changes required")
        else:
            prefix = "APPLIED" if args.apply else "PLAN"
            for change in changes:
                print(f"{prefix}: {change}")
        return 0
    except (ConfigurationError, FeishuAPIError, TaskRulesNotFoundError, ValueError) as exc:
        print(f"[FAIL] Daily task generation: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
