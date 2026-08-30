from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from baoyan_tracker.task_generator import (
    build_tasks,
    generate_daily_tasks,
    load_task_rules,
    resolve_dates,
)


class FakeTaskService:
    def __init__(self):
        self.records: list[dict[str, Any]] = []

    def list_tables(self):
        return [{"name": "03_每日任务", "table_id": "tasks"}]

    def list_records(self, table_id: str):
        assert table_id == "tasks"
        return deepcopy(self.records)

    def create_record(self, table_id: str, fields: dict[str, Any]):
        assert table_id == "tasks"
        record = {"record_id": f"task-{len(self.records) + 1}", "fields": fields.copy()}
        self.records.append(record)
        return deepcopy(record)

    def update_record(self, table_id: str, record_id: str, fields: dict[str, Any]):
        assert table_id == "tasks"
        record = next(item for item in self.records if item["record_id"] == record_id)
        record["fields"].update(fields)
        return deepcopy(record)


def test_rule_parsing_and_weekday_matching():
    rules = load_task_rules()
    assert len(rules.rules) == 3
    tuesday = date(2026, 9, 1)
    tasks = build_tasks(rules, (tuesday,))
    categories = {task.fields["类别"] for task in tasks}
    assert categories == {"英语", "LeetCode"}
    leetcode = next(task for task in tasks if task.fields["类别"] == "LeetCode")
    assert leetcode.fields["计划量"] == 2
    assert leetcode.fields["预计时间"] == 60


def test_408_rotation_and_sunday_duration():
    rules = load_task_rules()
    sunday = date(2026, 9, 6)
    task = next(item for item in build_tasks(rules, (sunday,)) if item.fields["类别"] == "408")
    assert task.fields["计划量"] == 120
    assert task.fields["单位"] == "minute"
    assert any(subject in task.fields["任务名称"] for subject in rules.rules[2].content_cycle)


def test_future_date_resolution_is_bounded_and_inclusive():
    today = date(2026, 9, 1)
    assert resolve_dates(today_only=True, today=today) == (today,)
    assert resolve_dates(days=3, today=today) == (
        date(2026, 9, 1),
        date(2026, 9, 2),
        date(2026, 9, 3),
    )


def test_duplicate_prevention_and_manual_edit_preservation():
    service = FakeTaskService()
    rules = load_task_rules()
    dates = (date(2026, 9, 1),)
    first = generate_daily_tasks(service, rules, dates, apply=True)
    assert len(first) == 2
    assert generate_daily_tasks(service, rules, dates, apply=True) == []
    assert generate_daily_tasks(service, rules, dates, apply=True) == []
    assert len(service.records) == 2

    english = next(item for item in service.records if item["fields"]["类别"] == "英语")
    english["fields"]["计划量"] = 20
    english["fields"]["预计时间"] = 25
    english["fields"]["备注"] = "manual edit"
    assert generate_daily_tasks(service, rules, dates, apply=True) == []
    assert english["fields"]["计划量"] == 20
    assert english["fields"]["预计时间"] == 25
    assert english["fields"]["备注"] == "manual edit"

    changes = generate_daily_tasks(service, rules, dates, apply=True, force=True)
    assert len(changes) == 1
    assert english["fields"]["计划量"] == 30
    assert english["fields"]["预计时间"] == 30
    assert english["fields"]["备注"] == "自动生成：english_daily"


def test_rules_path_is_project_configuration():
    expected = Path(__file__).resolve().parents[1] / "config" / "task_rules.json"
    assert load_task_rules(expected).default_days == 3
