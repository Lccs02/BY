"""Configuration-driven, idempotent daily task generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .bitable_service import BitableService, PlannedChange
from .business_time import business_today
from .schema import timestamp

TASK_RULES_ENV = "TASK_RULES_PATH"
DEFAULT_RULES_RELATIVE_PATH = Path("config") / "task_rules.json"


class TaskRulesNotFoundError(FileNotFoundError):
    """Raised when no task-rules configuration can be resolved."""


class TaskRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    weekdays: tuple[int, ...]
    task_name: str = Field(min_length=1)
    goal_id: str = Field(min_length=1)
    unit: str
    priority: str = "P1"
    plan_quantity: float | None = None
    estimated_minutes: float | None = None
    plan_by_weekday: dict[int, float] = Field(default_factory=dict)
    minutes_by_weekday: dict[int, float] = Field(default_factory=dict)
    content_cycle: tuple[str, ...] = ()

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value or any(day < 1 or day > 7 for day in value):
            raise ValueError("weekdays must contain ISO weekday values from 1 to 7")
        if len(set(value)) != len(value):
            raise ValueError("weekdays must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_quantities(self) -> TaskRule:
        if self.plan_quantity is None and not self.plan_by_weekday:
            raise ValueError("plan_quantity or plan_by_weekday is required")
        if self.estimated_minutes is None and not self.minutes_by_weekday:
            raise ValueError("estimated_minutes or minutes_by_weekday is required")
        for weekday in (*self.plan_by_weekday, *self.minutes_by_weekday):
            if weekday not in self.weekdays:
                raise ValueError("weekday-specific values must belong to weekdays")
        return self

    def matches(self, day: date) -> bool:
        return day.isoweekday() in self.weekdays

    def task_content(self, day: date) -> str:
        if not self.content_cycle:
            return self.task_name
        weekday_index = self.weekdays.index(day.isoweekday())
        occurrence = (day.toordinal() // 7) * len(self.weekdays) + weekday_index
        return f"{self.task_name}：{self.content_cycle[occurrence % len(self.content_cycle)]}"

    def quantity_for(self, day: date) -> float:
        return self.plan_by_weekday.get(day.isoweekday(), self.plan_quantity or 0)

    def minutes_for(self, day: date) -> float:
        return self.minutes_by_weekday.get(day.isoweekday(), self.estimated_minutes or 0)


class TaskRuleSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    default_days: int = Field(default=3, ge=1, le=31)
    rules: tuple[TaskRule, ...]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> TaskRuleSet:
        ids = [rule.rule_id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule_id values must be unique")
        return self


@dataclass(frozen=True)
class GeneratedTask:
    unique_key: str
    fields: dict[str, Any]


def resolve_task_rules_path(path: Path | str | None = None) -> Path:
    """Resolve task rules without relying on the installed module location.

    An explicit argument is authoritative. Otherwise ``TASK_RULES_PATH`` is
    authoritative when set, followed by ``config/task_rules.json`` below the
    current working directory.
    """

    if path is not None:
        candidates = (Path(path).expanduser(),)
    else:
        configured = os.getenv(TASK_RULES_ENV)
        if configured and configured.strip():
            candidates = (Path(configured.strip()).expanduser(),)
        else:
            candidates = (Path.cwd() / DEFAULT_RULES_RELATIVE_PATH,)

    checked: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        checked.append(resolved)
        if resolved.is_file():
            return resolved

    locations = "\n".join(f"- {candidate}" for candidate in checked)
    raise TaskRulesNotFoundError(
        "Task rules file not found.\n"
        f"Checked:\n{locations}\n"
        f"Pass an explicit path, set {TASK_RULES_ENV}, or run from the repository root."
    )


def load_task_rules(path: Path | str | None = None) -> TaskRuleSet:
    rule_path = resolve_task_rules_path(path)
    return TaskRuleSet.model_validate_json(rule_path.read_text(encoding="utf-8"))


def resolve_dates(
    *,
    explicit_date: date | None = None,
    today_only: bool = False,
    days: int | None = None,
    default_days: int = 3,
    today: date | None = None,
) -> tuple[date, ...]:
    today = today or business_today()
    if explicit_date:
        return (explicit_date,)
    count = 1 if today_only else (days if days is not None else default_days)
    if count < 1 or count > 31:
        raise ValueError("days must be between 1 and 31")
    return tuple(today + timedelta(days=offset) for offset in range(count))


def build_tasks(ruleset: TaskRuleSet, dates: tuple[date, ...]) -> tuple[GeneratedTask, ...]:
    tasks: list[GeneratedTask] = []
    current_day = business_today()
    for day in dates:
        for rule in ruleset.rules:
            if not rule.matches(day):
                continue
            unique_key = f"{day.isoformat()}|{rule.category}|{rule.rule_id}"
            tasks.append(
                GeneratedTask(
                    unique_key,
                    {
                        "日期": timestamp(day.isoformat()),
                        "类别": rule.category,
                        "任务名称": rule.task_content(day),
                        "所属目标": rule.goal_id,
                        "计划量": rule.quantity_for(day),
                        "单位": rule.unit,
                        "预计时间": rule.minutes_for(day),
                        "优先级": rule.priority,
                        "状态": "未开始",
                        "是否今日": day == current_day,
                        "备注": f"自动生成：{rule.rule_id}",
                        "规则ID": unique_key,
                    },
                )
            )
    return tuple(tasks)


def _changed(current: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for key, value in desired.items():
        old = current.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                equal = abs(float(old) - float(value)) <= 0.005
            except (TypeError, ValueError):
                equal = False
        else:
            equal = old == value
        if not equal:
            changed[key] = value
    return changed


def generate_daily_tasks(
    service: BitableService,
    ruleset: TaskRuleSet,
    dates: tuple[date, ...],
    *,
    apply: bool,
    force: bool = False,
) -> list[PlannedChange]:
    tables = {str(item.get("name")): item for item in service.list_tables()}
    table_id = str(tables["03_每日任务"]["table_id"])
    existing = service.list_records(table_id)
    by_key = {
        str(record.get("fields", {}).get("规则ID")): record
        for record in existing
        if record.get("fields", {}).get("规则ID")
    }
    changes: list[PlannedChange] = []
    for task in build_tasks(ruleset, dates):
        record = by_key.get(task.unique_key)
        if record is None:
            changes.append(PlannedChange("CREATE DAILY TASK", task.unique_key))
            if apply:
                created = service.create_record(table_id, task.fields)
                by_key[task.unique_key] = created
            continue
        if not force:
            continue
        current = record.get("fields") or {}
        # Actual values and status always remain owned by the sync/user workflow.
        maintainable = {
            key: value
            for key, value in task.fields.items()
            if key not in {"状态", "是否今日"}
        }
        changed = _changed(current, maintainable)
        if changed:
            changes.append(PlannedChange("FORCE UPDATE DAILY TASK", task.unique_key))
            if apply:
                service.update_record(table_id, str(record["record_id"]), changed)
    return changes
