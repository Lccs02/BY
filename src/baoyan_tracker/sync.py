"""Full-recalculation sync from check-ins to tasks, goals, milestones, and weeks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from .bitable_service import BitableService, PlannedChange
from .business_time import business_today, milliseconds_to_business_date
from .progress_engine import (
    calculate_actual_progress,
    calculate_expected_value,
    calculate_risk,
    calculate_time_progress,
    calculate_velocity,
)


@dataclass(frozen=True)
class RecordMutation:
    table_id: str
    record_id: str | None
    resource: str
    fields: dict[str, Any]
    create: bool = False


@dataclass
class PreparedCheckin:
    record: dict[str, Any]
    fields: dict[str, Any]
    day: date
    category: str
    goal_id: str | None
    task_id: str | None
    quantity: float
    minutes: float
    unit: str


def _as_date(value: Any) -> date:
    if isinstance(value, (int, float)):
        return milliseconds_to_business_date(value)
    if isinstance(value, str) and value.isdigit():
        return milliseconds_to_business_date(value)
    return date.fromisoformat(str(value)[:10])


def _as_milliseconds(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)


def _day_milliseconds(value: date) -> int:
    return int(datetime.combine(value, time.min, tzinfo=UTC).timestamp() * 1000)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _different(current: Any, desired: Any) -> bool:
    if desired == "" and current is None:
        return False
    if isinstance(desired, (int, float)) and not isinstance(desired, bool):
        if current in (None, ""):
            return True
        return abs(_number(current) - float(desired)) > 0.005
    return current != desired


def _changed_fields(current: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in desired.items() if _different(current.get(key), value)}


def _record_id(record: dict[str, Any]) -> str:
    return str(record["record_id"])


def _goal_unit(goal_type: str) -> str:
    return "problem" if goal_type == "COUNT" else "minute"


def _week_key(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def _prepare_checkins(
    checkins: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    goals: list[dict[str, Any]],
) -> tuple[list[PreparedCheckin], list[RecordMutation]]:
    goal_by_id = {
        str(record.get("fields", {}).get("目标ID")): record
        for record in goals
        if record.get("fields", {}).get("目标ID")
    }
    goal_ids_by_category: dict[str, list[str]] = defaultdict(list)
    for goal_id, record in goal_by_id.items():
        fields = record.get("fields") or {}
        if fields.get("状态") != "暂停":
            goal_ids_by_category[str(fields.get("类别") or "")].append(goal_id)

    task_by_id = {_record_id(record): record for record in tasks}
    task_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tasks_by_day_category: dict[tuple[date, str], list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        fields = task.get("fields") or {}
        if fields.get("任务名称"):
            task_by_name[str(fields["任务名称"])].append(task)
        if fields.get("日期") and fields.get("类别"):
            tasks_by_day_category[(_as_date(fields["日期"]), str(fields["类别"]))].append(task)

    prepared: list[PreparedCheckin] = []
    backfills: list[RecordMutation] = []
    for record in checkins:
        fields = dict(record.get("fields") or {})
        created_ms = _as_milliseconds(
            fields.get("创建时间") or record.get("created_time") or record.get("created_at") or 0
        )
        raw_day = fields.get("日期") or fields.get("打卡时间") or created_ms
        day = _as_date(raw_day)
        category = str(fields.get("类别") or "")
        content = str(fields.get("内容") or "")

        task: dict[str, Any] | None = None
        explicit_task = str(fields.get("所属任务") or "")
        if explicit_task:
            task = task_by_id.get(explicit_task)
            if task is None:
                named = task_by_name.get(explicit_task, [])
                task = named[0] if len(named) == 1 else None
        if task is None and content:
            matching = [
                item
                for item in task_by_name.get(content, [])
                if (item.get("fields") or {}).get("类别") == category
            ]
            task = matching[0] if len(matching) == 1 else None
        candidates = tasks_by_day_category.get((day, category), [])
        if task is None and len(candidates) == 1:
            task = candidates[0]

        task_fields = task.get("fields") or {} if task else {}
        goal_id = str(fields.get("所属目标") or task_fields.get("所属目标") or "") or None
        if goal_id not in goal_by_id:
            candidates_goal = goal_ids_by_category.get(category, [])
            goal_id = candidates_goal[0] if len(candidates_goal) == 1 else None
        goal_fields = goal_by_id.get(goal_id, {}).get("fields") or {}
        goal_type = str(goal_fields.get("目标类型") or "TIME")
        unit = _goal_unit(goal_type)
        quantity = _number(fields.get("数量"))
        minutes = _number(fields.get("投入分钟"))
        amount = quantity if goal_type == "COUNT" else minutes
        task_id = _record_id(task) if task else None

        desired = {
            "打卡时间": fields.get("打卡时间") or created_ms,
            "日期": fields.get("日期") or _day_milliseconds(day),
            "所属目标": goal_id or "",
            "所属任务": str(task_fields.get("任务名称") or ""),
            "单位": unit,
        }
        changed = _changed_fields(fields, desired)
        if changed:
            backfills.append(
                RecordMutation(
                    str(record["table_id"]),
                    _record_id(record),
                    f"CHECKIN/{_record_id(record)}",
                    changed,
                )
            )
            fields.update(changed)
        prepared.append(
            PreparedCheckin(
                record,
                fields,
                day,
                category,
                goal_id,
                task_id,
                amount,
                minutes,
                unit,
            )
        )
    return prepared, backfills


def _task_mutations(
    table_id: str,
    tasks: list[dict[str, Any]],
    checkins: list[PreparedCheckin],
    goals: list[dict[str, Any]],
    as_of: date,
) -> tuple[list[RecordMutation], dict[str, dict[str, Any]]]:
    goal_by_category = {
        str(record.get("fields", {}).get("类别")): record.get("fields") or {}
        for record in goals
        if record.get("fields", {}).get("类别")
    }
    by_task: dict[str, list[PreparedCheckin]] = defaultdict(list)
    for checkin in checkins:
        if checkin.task_id:
            by_task[checkin.task_id].append(checkin)

    mutations: list[RecordMutation] = []
    computed: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = _record_id(task)
        fields = task.get("fields") or {}
        entries = by_task.get(task_id, [])
        goal_fields = goal_by_category.get(str(fields.get("类别") or ""), {})
        goal_type = str(goal_fields.get("目标类型") or "TIME")
        unit = _goal_unit(goal_type)
        actual = sum(item.quantity for item in entries)
        actual_minutes = sum(item.minutes for item in entries)
        planned = _number(fields.get("计划量"))
        if fields.get("状态") == "跳过":
            status = "跳过"
        elif actual <= 0:
            status = "未开始"
        elif planned > 0 and actual < planned:
            status = "部分完成"
        else:
            status = "已完成"
        task_day = _as_date(fields["日期"]) if fields.get("日期") else None
        desired = {
            "实际量": round(actual, 2),
            "实际时间": round(actual_minutes, 2),
            "单位": unit,
            "状态": status,
            "是否今日": task_day == as_of,
        }
        if not fields.get("所属目标") and goal_fields.get("目标ID"):
            desired["所属目标"] = goal_fields["目标ID"]
        computed[task_id] = {**fields, **desired}
        changed = _changed_fields(fields, desired)
        if changed:
            mutations.append(
                RecordMutation(table_id, task_id, f"TASK/{fields.get('任务名称')}", changed)
            )
    return mutations, computed


def _goal_mutations(
    table_id: str,
    goals: list[dict[str, Any]],
    checkins: list[PreparedCheckin],
    as_of: date,
) -> tuple[list[RecordMutation], dict[str, dict[str, Any]]]:
    by_goal: dict[str, list[PreparedCheckin]] = defaultdict(list)
    for checkin in checkins:
        if checkin.goal_id:
            by_goal[checkin.goal_id].append(checkin)

    mutations: list[RecordMutation] = []
    computed: dict[str, dict[str, Any]] = {}
    for record in goals:
        fields = record.get("fields") or {}
        goal_id = str(fields.get("目标ID") or "")
        if not goal_id or not fields.get("开始日期") or not fields.get("截止日期"):
            continue
        start = _as_date(fields["开始日期"])
        deadline = _as_date(fields["截止日期"])
        target = _number(fields.get("目标值"))
        entries = by_goal.get(goal_id, [])
        current = sum(item.quantity for item in entries)
        dated_entries = [(item.day, item.quantity) for item in entries]
        v7 = calculate_velocity(dated_entries, 7, as_of)
        v14 = calculate_velocity(dated_entries, 14, as_of)
        v30 = calculate_velocity(dated_entries, 30, as_of)
        last_activity = max((item.day for item in entries if item.quantity > 0), default=None)
        inactive_days = (as_of - last_activity).days if last_activity else None
        time_progress = calculate_time_progress(start, deadline, as_of)
        actual_progress = calculate_actual_progress(current, target)
        expected_value = calculate_expected_value(target, start, deadline, as_of)
        assessment = calculate_risk(
            start=start,
            deadline=deadline,
            current_value=current,
            target_value=target,
            as_of=as_of,
            velocity_7d=v7,
            velocity_14d=v14,
            velocity_30d=v30,
            days_since_activity=inactive_days,
        )
        estimated = (
            _day_milliseconds(assessment.estimated_completion)
            if assessment.estimated_completion
            else None
        )
        desired = {
            "当前值": round(current, 2),
            "单位": _goal_unit(str(fields.get("目标类型") or "TIME")),
            "剩余天数": max((deadline - as_of).days, 0),
            "时间进度": round(time_progress * 100, 2),
            "实际进度": round(actual_progress * 100, 2),
            "计划值": round(expected_value, 2),
            "进度差": round((actual_progress - time_progress) * 100, 2),
            "风险状态": assessment.level.value,
            "7日速度": round(v7, 4),
            "14日速度": round(v14, 4),
            "30日速度": round(v30, 4),
            "预计完成日期": estimated,
        }
        computed[goal_id] = {**fields, **desired}
        changed = _changed_fields(fields, desired)
        if changed:
            mutations.append(RecordMutation(table_id, _record_id(record), f"GOAL/{goal_id}", changed))
    return mutations, computed


def _milestone_mutations(
    table_id: str,
    milestones: list[dict[str, Any]],
    goals: dict[str, dict[str, Any]],
    as_of: date,
) -> list[RecordMutation]:
    mutations: list[RecordMutation] = []
    for record in milestones:
        fields = record.get("fields") or {}
        goal = goals.get(str(fields.get("所属目标") or ""))
        if not goal:
            continue
        current = _number(goal.get("当前值"))
        target = _number(fields.get("目标值"))
        complete = target > 0 and current >= target
        desired: dict[str, Any] = {
            "当前值": round(current, 2),
            "单位": goal.get("单位"),
            "状态": "已完成" if complete else "进行中",
        }
        if complete and not fields.get("完成日期"):
            desired["完成日期"] = _day_milliseconds(as_of)
        elif not complete and fields.get("完成日期"):
            desired["完成日期"] = None
        changed = _changed_fields(fields, desired)
        if changed:
            mutations.append(
                RecordMutation(
                    table_id,
                    _record_id(record),
                    f"MILESTONE/{fields.get('里程碑ID')}",
                    changed,
                )
            )
    return mutations


def _weekly_mutations(
    table_id: str,
    reviews: list[dict[str, Any]],
    task_fields: dict[str, dict[str, Any]],
    checkins: list[PreparedCheckin],
    goal_fields: dict[str, dict[str, Any]],
) -> list[RecordMutation]:
    tasks_by_week: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fields in task_fields.values():
        if fields.get("日期"):
            tasks_by_week[_week_key(_as_date(fields["日期"]))].append(fields)
    checkins_by_week: dict[str, list[PreparedCheckin]] = defaultdict(list)
    for checkin in checkins:
        checkins_by_week[_week_key(checkin.day)].append(checkin)
    existing = {
        str(record.get("fields", {}).get("周次")): record
        for record in reviews
        if record.get("fields", {}).get("周次")
    }
    risk_names = [
        str(fields.get("目标名称") or goal_id)
        for goal_id, fields in goal_fields.items()
        if fields.get("风险状态") in {"AT_RISK", "CRITICAL"}
    ]

    mutations: list[RecordMutation] = []
    for week_key in sorted(set(tasks_by_week) | set(checkins_by_week)):
        year = int(week_key[:4])
        week = int(week_key[-2:])
        week_start = date.fromisocalendar(year, week, 1)
        week_end = week_start + timedelta(days=6)
        tasks = tasks_by_week.get(week_key, [])
        entries = checkins_by_week.get(week_key, [])
        eligible = [task for task in tasks if task.get("状态") != "跳过"]
        completed = sum(task.get("状态") == "已完成" for task in eligible)
        completion_rate = completed / len(eligible) * 100 if eligible else 0.0
        category_minutes = defaultdict(float)
        leetcode_count = 0.0
        for entry in entries:
            category_minutes[entry.category] += entry.minutes
            if entry.category == "LeetCode":
                leetcode_count += entry.quantity
        deviations: list[tuple[float, dict[str, Any]]] = []
        progress: list[tuple[float, dict[str, Any]]] = []
        for task in eligible:
            planned = _number(task.get("计划量"))
            actual = _number(task.get("实际量"))
            deviations.append((planned - actual, task))
            if planned > 0:
                progress.append((actual / planned, task))
        worst = max(deviations, default=(0.0, {}), key=lambda item: item[0])
        best = max(progress, default=(0.0, {}), key=lambda item: item[0])
        desired = {
            "周次": week_key,
            "开始日期": _day_milliseconds(week_start),
            "结束日期": _day_milliseconds(week_end),
            "计划时间": round(sum(_number(task.get("预计时间")) for task in tasks), 2),
            "实际时间": round(sum(entry.minutes for entry in entries), 2),
            "任务完成率": round(completion_rate, 2),
            "科研时间": round(category_minutes["科研"], 2),
            "课程时间": round(category_minutes["课程"], 2),
            "英语时间": round(category_minutes["英语"], 2),
            "LeetCode题数": round(leetcode_count, 2),
            "408时间": round(category_minutes["408"], 2),
            "最大进展": (
                f"{best[1].get('任务名称')}: {best[0] * 100:.1f}%" if best[1] else ""
            ),
            "最大偏差": (
                f"{worst[1].get('任务名称')}: -{max(worst[0], 0):g}"
                if worst[1] and worst[0] > 0
                else "无"
            ),
            "风险目标": "、".join(risk_names),
        }
        record = existing.get(week_key)
        if record:
            current = record.get("fields") or {}
            changed = _changed_fields(current, desired)
            if changed:
                mutations.append(
                    RecordMutation(table_id, _record_id(record), f"WEEK/{week_key}", changed)
                )
        else:
            mutations.append(RecordMutation(table_id, None, f"WEEK/{week_key}", desired, True))
    return mutations


def build_sync_mutations(
    service: BitableService, as_of: date | None = None
) -> list[RecordMutation]:
    as_of = as_of or business_today()
    tables = {str(item.get("name")): item for item in service.list_tables()}
    ids = {name: str(table["table_id"]) for name, table in tables.items()}
    records: dict[str, list[dict[str, Any]]] = {}
    for name in (
        "01_长期目标",
        "02_阶段里程碑",
        "03_每日任务",
        "04_打卡记录",
        "05_周复盘",
    ):
        records[name] = service.list_records(ids[name])
        for record in records[name]:
            record["table_id"] = ids[name]

    checkins, checkin_mutations = _prepare_checkins(
        records["04_打卡记录"], records["03_每日任务"], records["01_长期目标"]
    )
    task_mutations, task_fields = _task_mutations(
        ids["03_每日任务"],
        records["03_每日任务"],
        checkins,
        records["01_长期目标"],
        as_of,
    )
    goal_mutations, goal_fields = _goal_mutations(
        ids["01_长期目标"], records["01_长期目标"], checkins, as_of
    )
    milestone_mutations = _milestone_mutations(
        ids["02_阶段里程碑"], records["02_阶段里程碑"], goal_fields, as_of
    )
    weekly_mutations = _weekly_mutations(
        ids["05_周复盘"], records["05_周复盘"], task_fields, checkins, goal_fields
    )
    return [
        *checkin_mutations,
        *task_mutations,
        *goal_mutations,
        *milestone_mutations,
        *weekly_mutations,
    ]


def sync_progress(
    service: BitableService, *, apply: bool, as_of: date | None = None
) -> list[PlannedChange]:
    mutations = build_sync_mutations(service, as_of)
    changes: list[PlannedChange] = []
    for mutation in mutations:
        action = "CREATE" if mutation.create else "UPDATE"
        fields = ", ".join(mutation.fields)
        changes.append(PlannedChange(f"{action} AGGREGATE", f"{mutation.resource} ({fields})"))
        if not apply:
            continue
        if mutation.create:
            service.create_record(mutation.table_id, mutation.fields)
        else:
            assert mutation.record_id is not None
            service.update_record(mutation.table_id, mutation.record_id, mutation.fields)
    return changes
