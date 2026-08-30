from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from baoyan_tracker.schema import timestamp
from baoyan_tracker.sync import _different, sync_progress


class FakeService:
    def __init__(self):
        self.tables = {
            "01_长期目标": "goals",
            "02_阶段里程碑": "milestones",
            "03_每日任务": "tasks",
            "04_打卡记录": "checkins",
            "05_周复盘": "weeks",
        }
        self.records: dict[str, list[dict[str, Any]]] = {
            "goals": [
                {
                    "record_id": "goal-1",
                    "fields": {
                        "目标ID": "GOAL-LC-220",
                        "目标名称": "LeetCode",
                        "类别": "LeetCode",
                        "目标类型": "COUNT",
                        "开始日期": timestamp("2026-01-01"),
                        "截止日期": timestamp("2026-12-31"),
                        "目标值": 220,
                        "当前值": 99,
                        "状态": "进行中",
                    },
                }
            ],
            "milestones": [],
            "tasks": [
                {
                    "record_id": "task-1",
                    "fields": {
                        "日期": timestamp("2026-08-24"),
                        "类别": "LeetCode",
                        "任务名称": "LC two",
                        "所属目标": "GOAL-LC-220",
                        "计划量": 2,
                        "预计时间": 40,
                        "状态": "未开始",
                    },
                }
            ],
            "checkins": [
                {
                    "record_id": "checkin-1",
                    "created_time": str(timestamp("2026-08-24")),
                    "fields": {
                        "日期": timestamp("2026-08-24"),
                        "类别": "LeetCode",
                        "数量": 2,
                        "投入分钟": 35,
                    },
                }
            ],
            "weeks": [],
        }

    def list_tables(self):
        return [{"name": name, "table_id": table_id} for name, table_id in self.tables.items()]

    def list_records(self, table_id: str):
        return deepcopy(self.records[table_id])

    def update_record(self, table_id: str, record_id: str, fields: dict[str, Any]):
        record = next(item for item in self.records[table_id] if item["record_id"] == record_id)
        record["fields"].update(fields)
        return record

    def create_record(self, table_id: str, fields: dict[str, Any]):
        record = {"record_id": f"new-{len(self.records[table_id])}", "fields": fields.copy()}
        self.records[table_id].append(record)
        return record


def _fields(service: FakeService, table: str, record_id: str | None = None):
    records = service.records[table]
    if record_id:
        return next(item["fields"] for item in records if item["record_id"] == record_id)
    return records[0]["fields"]


def test_full_recalculation_is_idempotent_and_handles_edit_delete():
    service = FakeService()
    as_of = date(2026, 8, 30)

    assert sync_progress(service, apply=True, as_of=as_of)
    assert _fields(service, "tasks")["实际量"] == 2
    assert _fields(service, "tasks")["实际时间"] == 35
    assert _fields(service, "tasks")["状态"] == "已完成"
    assert _fields(service, "goals")["当前值"] == 2
    assert _fields(service, "goals")["单位"] == "problem"
    assert _fields(service, "weeks")["LeetCode题数"] == 2
    assert _fields(service, "weeks")["实际时间"] == 35

    assert sync_progress(service, apply=True, as_of=as_of) == []

    _fields(service, "checkins")["数量"] = 3
    assert sync_progress(service, apply=True, as_of=as_of)
    assert _fields(service, "tasks")["实际量"] == 3
    assert _fields(service, "goals")["当前值"] == 3
    assert _fields(service, "weeks")["LeetCode题数"] == 3

    service.records["checkins"].clear()
    assert sync_progress(service, apply=True, as_of=as_of)
    assert _fields(service, "tasks")["实际量"] == 0
    assert _fields(service, "tasks")["实际时间"] == 0
    assert _fields(service, "tasks")["状态"] == "未开始"
    assert _fields(service, "goals")["当前值"] == 0
    assert _fields(service, "weeks")["LeetCode题数"] == 0
    assert sync_progress(service, apply=True, as_of=as_of) == []


def test_feishu_missing_text_is_equivalent_to_desired_empty_text():
    assert _different(None, "") is False
