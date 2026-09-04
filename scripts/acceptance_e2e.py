"""Destructive-but-cleaned live business acceptance for the single-entry data flow."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from baoyan_tracker.bitable_service import BitableService
from baoyan_tracker.business_time import business_today
from baoyan_tracker.config import load_settings
from baoyan_tracker.feishu_client import FeishuClient
from baoyan_tracker.schema import timestamp
from baoyan_tracker.sync import sync_progress


def _number(value: Any) -> float:
    return float(value or 0)


def _assert_close(actual: Any, expected: float, label: str) -> None:
    if abs(_number(actual) - expected) > 0.01:
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def _as_date(value: Any) -> date:
    return datetime.fromtimestamp(_number(value) / 1000, tz=UTC).astimezone().date()


def _fields_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record["record_id"]): record.get("fields") or {} for record in records}


def _record_by_field(
    records: list[dict[str, Any]], field: str, value: str
) -> dict[str, Any]:
    return next(record for record in records if (record.get("fields") or {}).get(field) == value)


def _sync_three_times(service: BitableService, as_of: date) -> None:
    first = sync_progress(service, apply=True, as_of=as_of)
    if not first:
        raise AssertionError("first sync unexpectedly made no changes")
    if sync_progress(service, apply=True, as_of=as_of):
        raise AssertionError("second sync was not idempotent")
    if sync_progress(service, apply=True, as_of=as_of):
        raise AssertionError("third sync was not idempotent")


def main() -> int:
    run_id = f"__E2E__{uuid.uuid4().hex[:8]}"
    settings = load_settings()
    token = settings.resolved_app_token
    if not token:
        raise RuntimeError("No Bitable app token configured")

    with FeishuClient(settings) as client:
        service = BitableService(client, token)
        table_items = service.list_tables()
        tables = {str(item["name"]): str(item["table_id"]) for item in table_items}
        task_table = tables["03_每日任务"]
        checkin_table = tables["04_打卡记录"]
        goal_table = tables["01_长期目标"]
        week_table = tables["05_周复盘"]
        baseline_ids = {
            name: {str(record["record_id"]) for record in service.list_records(table_id)}
            for name, table_id in tables.items()
        }
        baseline_goals = {
            str(record.get("fields", {}).get("目标ID")): _number(
                record.get("fields", {}).get("当前值")
            )
            for record in service.list_records(goal_table)
        }
        created_tasks: list[str] = []
        created_checkins: list[str] = []
        deleted_checkins: set[str] = set()

        # A complete ISO week: 2026-W35, Monday through Sunday.
        start = date(2026, 8, 24)
        end = start + timedelta(days=6)
        task_specs = (
            (0, "科研", "科研完整完成", 60, 60),
            (0, "英语", "英语完整完成", 30, 30),
            (1, "LeetCode", "LeetCode完成", 2, 40),
            (2, "408", "408未完成一", 60, 60),
            (3, "课程", "课程部分完成", 90, 90),
            (3, "408", "408未完成二", 60, 60),
            (4, "LeetCode", "LeetCode超额", 2, 50),
            (4, "408", "408未完成三", 60, 60),
            (6, "科研", "科研完整完成二", 120, 120),
        )
        checkin_specs = (
            (0, "科研", 0, 60),
            (0, "英语", 0, 30),
            (1, "LeetCode", 2, 40),
            (3, "课程", 0, 45),
            (4, "LeetCode", 3, 50),
            (6, "科研", 0, 120),
        )

        try:
            task_names: dict[tuple[int, str], str] = {}
            for offset, category, label, plan, planned_minutes in task_specs:
                name = f"{run_id}_{label}"
                task_names[(offset, category)] = name
                record = service.create_record(
                    task_table,
                    {
                        "日期": timestamp((start + timedelta(days=offset)).isoformat()),
                        "类别": category,
                        "任务名称": name,
                        "计划量": plan,
                        "预计时间": planned_minutes,
                        "优先级": "P1",
                        "状态": "未开始",
                        "备注": run_id,
                    },
                )
                created_tasks.append(str(record["record_id"]))

            lc_edit_record_id = ""
            for offset, category, quantity, minutes in checkin_specs:
                fields: dict[str, Any] = {
                    "日期": timestamp((start + timedelta(days=offset)).isoformat()),
                    "类别": category,
                    "投入分钟": minutes,
                    "备注": run_id,
                }
                if quantity:
                    fields["数量"] = quantity
                record = service.create_record(checkin_table, fields)
                record_id = str(record["record_id"])
                created_checkins.append(record_id)
                if offset == 1 and category == "LeetCode":
                    lc_edit_record_id = record_id

            _sync_three_times(service, end)
            print("[PASS] sync x3 is idempotent")

            tasks = service.list_records(task_table)
            task_values = {
                str(record.get("fields", {}).get("任务名称")): record.get("fields") or {}
                for record in tasks
            }
            expected_tasks = {
                "科研完整完成": (60, "已完成"),
                "英语完整完成": (30, "已完成"),
                "LeetCode完成": (2, "已完成"),
                "408未完成一": (0, "未开始"),
                "课程部分完成": (45, "部分完成"),
                "408未完成二": (0, "未开始"),
                "LeetCode超额": (3, "已完成"),
                "408未完成三": (0, "未开始"),
                "科研完整完成二": (120, "已完成"),
            }
            for label, (actual, status) in expected_tasks.items():
                fields = task_values[f"{run_id}_{label}"]
                _assert_close(fields.get("实际量"), actual, f"task {label} actual")
                if fields.get("状态") != status:
                    raise AssertionError(f"task {label} status: {fields.get('状态')}")
            print("[PASS] complete/partial/unstarted/overtime task aggregation")

            checkins = _fields_by_id(service.list_records(checkin_table))
            for record_id in created_checkins:
                fields = checkins[record_id]
                required = ("打卡时间", "日期", "所属目标", "所属任务", "单位")
                missing = [key for key in required if not fields.get(key)]
                if missing:
                    raise AssertionError(
                        f"check-in inference incomplete: {record_id}, missing={missing}"
                    )
            print("[PASS] check-in relation/date/unit inference")

            goals = {
                str(record.get("fields", {}).get("目标ID")): record.get("fields") or {}
                for record in service.list_records(goal_table)
            }
            expected_goals = {
                "GOAL-RESEARCH": 180,
                "GOAL-ENGLISH-DAILY": 30,
                "GOAL-LC-220": 5,
                "GOAL-408": 0,
                "GOAL-GPA": 45,
            }
            for goal_id, value in expected_goals.items():
                _assert_close(goals[goal_id].get("当前值"), value, f"goal {goal_id}")
                for key in ("实际进度", "进度差", "7日速度", "14日速度", "30日速度"):
                    if goals[goal_id].get(key) is None:
                        raise AssertionError(f"goal {goal_id} missing {key}")
                if not goals[goal_id].get("风险状态"):
                    raise AssertionError(f"goal {goal_id} missing risk")
            velocity_totals = {
                "GOAL-RESEARCH": 180,
                "GOAL-ENGLISH-DAILY": 30,
                "GOAL-LC-220": 5,
                "GOAL-408": 0,
                "GOAL-GPA": 45,
            }
            for goal_id, total in velocity_totals.items():
                _assert_close(goals[goal_id].get("7日速度"), total / 7, f"{goal_id} v7")
                _assert_close(goals[goal_id].get("14日速度"), total / 14, f"{goal_id} v14")
                _assert_close(goals[goal_id].get("30日速度"), total / 30, f"{goal_id} v30")
                _assert_close(goals[goal_id].get("计划值"), 0, f"{goal_id} expected")
            lc_target = _number(goals["GOAL-LC-220"].get("目标值"))
            english_target = _number(goals["GOAL-ENGLISH-DAILY"].get("目标值"))
            _assert_close(
                goals["GOAL-LC-220"].get("实际进度"),
                5 / lc_target * 100,
                "LC progress",
            )
            _assert_close(
                goals["GOAL-ENGLISH-DAILY"].get("实际进度"),
                30 / english_target * 100,
                "English progress",
            )
            lc_days = math.ceil((lc_target - 5) / (5 / 14))
            expected_lc_completion = end + timedelta(days=lc_days)
            if _as_date(goals["GOAL-LC-220"].get("预计完成日期")) != expected_lc_completion:
                raise AssertionError("LeetCode estimated completion date differs")
            if goals["GOAL-LC-220"].get("风险状态") != "CRITICAL":
                raise AssertionError("LeetCode forecast should escalate risk to CRITICAL")
            print("[PASS] goal totals/velocity/expected/forecast/risk")

            week = _record_by_field(service.list_records(week_table), "周次", "2026-W35")
            week_fields = week.get("fields") or {}
            expected_week = {
                "计划时间": 570,
                "实际时间": 345,
                "任务完成率": 55.56,
                "科研时间": 180,
                "课程时间": 45,
                "英语时间": 30,
                "LeetCode题数": 5,
                "408时间": 0,
            }
            for key, value in expected_week.items():
                _assert_close(week_fields.get(key), value, f"week {key}")
            if not week_fields.get("最大偏差"):
                raise AssertionError("weekly maximum deviation missing")
            print("[PASS] weekly automatic aggregation")

            # Edit a raw check-in, verify full recalculation, then delete and verify rollback.
            service.update_record(checkin_table, lc_edit_record_id, {"数量": 4})
            sync_progress(service, apply=True, as_of=end)
            edited_task = _record_by_field(
                service.list_records(task_table), "任务名称", task_names[(1, "LeetCode")]
            )
            _assert_close(edited_task.get("fields", {}).get("实际量"), 4, "edited task")
            edited_goal = _record_by_field(
                service.list_records(goal_table), "目标ID", "GOAL-LC-220"
            )
            _assert_close(edited_goal.get("fields", {}).get("当前值"), 7, "edited goal")
            edited_week = _record_by_field(service.list_records(week_table), "周次", "2026-W35")
            _assert_close(edited_week.get("fields", {}).get("LeetCode题数"), 7, "edited week")
            print("[PASS] edited check-in fully recalculates")

            service.delete_record(checkin_table, lc_edit_record_id)
            deleted_checkins.add(lc_edit_record_id)
            sync_progress(service, apply=True, as_of=end)
            deleted_task = _record_by_field(
                service.list_records(task_table), "任务名称", task_names[(1, "LeetCode")]
            )
            _assert_close(deleted_task.get("fields", {}).get("实际量"), 0, "deleted task")
            deleted_goal = _record_by_field(
                service.list_records(goal_table), "目标ID", "GOAL-LC-220"
            )
            _assert_close(deleted_goal.get("fields", {}).get("当前值"), 3, "deleted goal")
            deleted_week = _record_by_field(service.list_records(week_table), "周次", "2026-W35")
            _assert_close(deleted_week.get("fields", {}).get("LeetCode题数"), 3, "deleted week")
            print("[PASS] deleted check-in fully recalculates")

            # Mobile-style fast check-in: only category, amount, and optional content.
            today = business_today()
            quick_name = f"{run_id}_快速打卡"
            quick_task = service.create_record(
                task_table,
                {
                    "日期": timestamp(today.isoformat()),
                    "类别": "英语",
                    "任务名称": quick_name,
                    "计划量": 10,
                    "预计时间": 10,
                    "状态": "未开始",
                    "备注": run_id,
                },
            )
            created_tasks.append(str(quick_task["record_id"]))
            quick = service.create_record(
                checkin_table,
                {"类别": "英语", "投入分钟": 10, "内容": quick_name, "备注": run_id},
            )
            quick_id = str(quick["record_id"])
            created_checkins.append(quick_id)
            sync_progress(service, apply=True, as_of=today)
            quick_fields = _fields_by_id(service.list_records(checkin_table))[quick_id]
            for key in ("打卡时间", "日期", "所属目标", "所属任务", "单位"):
                if not quick_fields.get(key):
                    raise AssertionError(f"quick check-in missing inferred {key}")
            if quick_fields.get("单位") != "minute":
                raise AssertionError("quick check-in unit is not minute")
            print("[PASS] mobile quick check-in requires only category and amount")
        finally:
            # Delete only records created by this run, then recompute from remaining raw data.
            current_checkins = {
                str(record["record_id"]) for record in service.list_records(checkin_table)
            }
            for record_id in created_checkins:
                if record_id in current_checkins and record_id not in deleted_checkins:
                    service.delete_record(checkin_table, record_id)
            current_tasks = {str(record["record_id"]) for record in service.list_records(task_table)}
            for record_id in created_tasks:
                if record_id in current_tasks:
                    service.delete_record(task_table, record_id)
            current_weeks = {str(record["record_id"]) for record in service.list_records(week_table)}
            for record_id in current_weeks - baseline_ids["05_周复盘"]:
                service.delete_record(week_table, record_id)
            sync_progress(service, apply=True)

            if {
                str(record["record_id"]) for record in service.list_records(task_table)
            } != baseline_ids["03_每日任务"]:
                raise AssertionError("task cleanup did not restore baseline")
            if {
                str(record["record_id"]) for record in service.list_records(checkin_table)
            } != baseline_ids["04_打卡记录"]:
                raise AssertionError("check-in cleanup did not restore baseline")
            if {
                str(record["record_id"]) for record in service.list_records(week_table)
            } != baseline_ids["05_周复盘"]:
                raise AssertionError("weekly cleanup did not restore baseline")
            restored_goals = {
                str(record.get("fields", {}).get("目标ID")): _number(
                    record.get("fields", {}).get("当前值")
                )
                for record in service.list_records(goal_table)
            }
            if restored_goals != baseline_goals:
                raise AssertionError("goal cleanup did not restore baseline")
            print("[PASS] temporary records removed and baseline restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
