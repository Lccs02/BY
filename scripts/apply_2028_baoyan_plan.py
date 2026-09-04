"""Apply the focused 2028 Qingbei academic recommendation plan."""

from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from baoyan_tracker.bitable_service import BitableService, PlannedChange
from baoyan_tracker.bootstrap import Bootstrapper
from baoyan_tracker.business_time import business_today
from baoyan_tracker.config import ConfigurationError, load_settings
from baoyan_tracker.feishu_client import FeishuAPIError, FeishuClient
from baoyan_tracker.schema import (
    CCF_A_SUBMISSION_ROUTE,
    LONG_TERM_GOALS,
    MILESTONES,
    RESEARCH_PROJECTS,
    TableSpec,
)
from baoyan_tracker.sync import sync_progress
from baoyan_tracker.task_generator import generate_daily_tasks, load_task_rules, resolve_dates

LEGACY_RULE_IDS = {"english_daily", "leetcode_tts", "408_mws"}


def _different(current: Any, desired: Any) -> bool:
    if desired == "" and current is None:
        return False
    if isinstance(desired, (int, float)) and not isinstance(desired, bool):
        try:
            return abs(float(current) - float(desired)) > 0.005
        except (TypeError, ValueError):
            return True
    return current != desired


def upsert_seed_plan(
    service: BitableService,
    spec: TableSpec,
    *,
    apply: bool,
) -> list[PlannedChange]:
    tables = {str(item.get("name")): item for item in service.list_tables()}
    table = tables.get(spec.name)
    if table is None:
        # Bootstrap already reports the planned table and seed creation in dry-run mode.
        return []
    table_id = str(table["table_id"])
    records = service.list_records(table_id)
    existing = {
        str(record.get("fields", {}).get(spec.unique_key)): record
        for record in records
        if record.get("fields", {}).get(spec.unique_key)
    }
    changes: list[PlannedChange] = []
    for seed in spec.seeds:
        key = str(seed[spec.unique_key])
        record = existing.get(key)
        if record is None:
            # Bootstrap owns missing seed creation; this pass only updates existing rows.
            continue
        current = record.get("fields") or {}
        desired = dict(seed)
        if spec is MILESTONES:
            # Never undo progress that the user has marked manually.
            for field in ("当前值", "状态", "完成日期"):
                desired.pop(field, None)
        elif spec is CCF_A_SUBMISSION_ROUTE:
            # The route definition is managed here; the user's live workflow stage is not.
            desired.pop("当前状态", None)
        changed = {
            field: value
            for field, value in desired.items()
            if _different(current.get(field), value)
        }
        if changed:
            changes.append(
                PlannedChange(
                    "UPDATE PLAN RECORD",
                    f"{spec.name}/{key} ({', '.join(changed)})",
                )
            )
            if apply:
                service.update_record(table_id, str(record["record_id"]), changed)
    return changes


def remove_legacy_unstarted_tasks(service: BitableService, *, apply: bool) -> list[PlannedChange]:
    tables = {str(item.get("name")): item for item in service.list_tables()}
    table_id = str(tables["03_每日任务"]["table_id"])
    changes: list[PlannedChange] = []
    for record in service.list_records(table_id):
        fields = record.get("fields") or {}
        rule_id = str(fields.get("规则ID") or "").rsplit("|", 1)[-1]
        has_progress = (
            float(fields.get("实际量") or 0) > 0 or float(fields.get("实际时间") or 0) > 0
        )
        if rule_id not in LEGACY_RULE_IDS or has_progress:
            continue
        changes.append(
            PlannedChange("DELETE LEGACY TASK", str(fields.get("规则ID") or record["record_id"]))
        )
        if apply:
            service.delete_record(table_id, str(record["record_id"]))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    apply = bool(args.apply)
    as_of = args.as_of or business_today()
    try:
        settings = load_settings()
        if not settings.resolved_app_token:
            raise ConfigurationError("FEISHU_APP_TOKEN is missing")
        rules = load_task_rules()
        with FeishuClient(settings) as client:
            service = BitableService(client, settings.resolved_app_token)
            if apply:
                service.rename_app("2028届清北学术保研计划")
            changes = list(Bootstrapper(service).run(apply=apply).changes)
            for spec in (
                LONG_TERM_GOALS,
                MILESTONES,
                RESEARCH_PROJECTS,
                CCF_A_SUBMISSION_ROUTE,
            ):
                changes.extend(upsert_seed_plan(service, spec, apply=apply))
            changes.extend(remove_legacy_unstarted_tasks(service, apply=apply))
            changes.extend(
                generate_daily_tasks(
                    service,
                    rules,
                    resolve_dates(default_days=rules.default_days, today=as_of),
                    apply=apply,
                )
            )
            changes.extend(sync_progress(service, apply=apply, as_of=as_of))
        if not changes:
            print("No changes required")
        else:
            prefix = "APPLIED" if apply else "PLAN"
            for change in changes:
                print(f"{prefix}: {change}")
        return 0
    except (ConfigurationError, FeishuAPIError, ValueError, KeyError) as exc:
        print(f"[FAIL] Apply 2028 plan: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
