from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from baoyan_tracker import task_generator
from baoyan_tracker.task_generator import (
    TaskRulesNotFoundError,
    build_tasks,
    generate_daily_tasks,
    load_task_rules,
    resolve_dates,
)

PROJECT_RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "task_rules.json"


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
    rules = load_task_rules(PROJECT_RULES_PATH)
    assert len(rules.rules) == 3
    tuesday = date(2026, 9, 1)
    tasks = build_tasks(rules, (tuesday,))
    categories = {task.fields["类别"] for task in tasks}
    assert categories == {"英语", "LeetCode"}
    leetcode = next(task for task in tasks if task.fields["类别"] == "LeetCode")
    assert leetcode.fields["计划量"] == 2
    assert leetcode.fields["预计时间"] == 60


def test_408_rotation_and_sunday_duration():
    rules = load_task_rules(PROJECT_RULES_PATH)
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
    rules = load_task_rules(PROJECT_RULES_PATH)
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


def _write_rules(path: Path, *, default_days: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "{\n"
        f'  "default_days": {default_days},\n'
        '  "rules": [\n'
        "    {\n"
        '      "rule_id": "test_rule",\n'
        '      "category": "英语",\n'
        '      "weekdays": [1],\n'
        '      "task_name": "Test task",\n'
        '      "goal_id": "GOAL-TEST",\n'
        '      "unit": "minute",\n'
        '      "plan_quantity": 30,\n'
        '      "estimated_minutes": 30\n'
        "    }\n"
        "  ]\n"
        "}\n",
        encoding="utf-8",
    )
    return path


def test_rules_path_explicit_argument_has_priority(tmp_path, monkeypatch):
    explicit = _write_rules(tmp_path / "explicit.json", default_days=2)
    environment = _write_rules(tmp_path / "environment.json", default_days=4)
    monkeypatch.setenv("TASK_RULES_PATH", str(environment))
    assert load_task_rules(str(explicit)).default_days == 2


def test_rules_path_uses_environment_variable(tmp_path, monkeypatch):
    configured = _write_rules(tmp_path / "configured.json", default_days=5)
    _write_rules(tmp_path / "config" / "task_rules.json", default_days=6)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TASK_RULES_PATH", str(configured))
    assert load_task_rules().default_days == 5


def test_rules_path_uses_current_working_directory(tmp_path, monkeypatch):
    configured = _write_rules(tmp_path / "config" / "task_rules.json", default_days=7)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TASK_RULES_PATH", raising=False)
    assert load_task_rules().default_days == 7
    assert configured.is_file()


def test_rules_path_does_not_depend_on_installed_module_location(tmp_path, monkeypatch):
    configured = _write_rules(tmp_path / "config" / "task_rules.json", default_days=8)
    installed_module = tmp_path / "python" / "site-packages" / "baoyan_tracker"
    monkeypatch.setattr(task_generator, "__file__", str(installed_module / "task_generator.py"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TASK_RULES_PATH", raising=False)
    assert load_task_rules().default_days == 8
    assert configured.is_file()


def test_rules_path_missing_error_lists_checked_location(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TASK_RULES_PATH", raising=False)
    expected = (tmp_path / "config" / "task_rules.json").resolve()
    with pytest.raises(TaskRulesNotFoundError) as error:
        load_task_rules()
    message = str(error.value)
    assert "Task rules file not found." in message
    assert "Checked:" in message
    assert str(expected) in message
