"""Declarative Bitable schema and initial personal Baoyan records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any

TEXT = 1
NUMBER = 2
SINGLE_SELECT = 3
DATE = 5
CHECKBOX = 7
CREATED_TIME = 1001


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: int = TEXT
    options: tuple[str, ...] = ()

    def api_payload(self) -> dict[str, Any]:
        result: dict[str, Any] = {"field_name": self.name, "type": self.type}
        if self.type == SINGLE_SELECT and self.options:
            result["property"] = {"options": [{"name": name} for name in self.options]}
        elif self.type == DATE:
            result["property"] = {"date_formatter": "yyyy-MM-dd"}
        return result


@dataclass(frozen=True)
class TableSpec:
    name: str
    unique_key: str
    fields: tuple[FieldSpec, ...]
    seeds: tuple[dict[str, Any], ...] = ()
    views: tuple[str, ...] = ()


CATEGORIES = ("科研", "课程", "英语", "LeetCode", "408", "保研事务", "其他")
PRIORITIES = ("P0", "P1", "P2", "P3")
GOAL_STATUSES = ("未开始", "进行中", "已完成", "暂停")
TASK_STATUSES = ("未开始", "进行中", "部分完成", "已完成", "跳过")
RISK_LEVELS = ("ON_TRACK", "SLIGHTLY_BEHIND", "AT_RISK", "CRITICAL", "COMPLETED")


def timestamp(value: str) -> int:
    parsed = date.fromisoformat(value)
    return int(datetime.combine(parsed, time.min, tzinfo=UTC).timestamp() * 1000)


LONG_TERM_GOALS = TableSpec(
    name="01_长期目标",
    unique_key="目标ID",
    fields=(
        FieldSpec("目标ID"),
        FieldSpec("目标名称"),
        FieldSpec("类别", SINGLE_SELECT, CATEGORIES),
        FieldSpec("目标类型", SINGLE_SELECT, ("COUNT", "TIME", "PERCENTAGE", "MILESTONE")),
        FieldSpec("开始日期", DATE),
        FieldSpec("截止日期", DATE),
        FieldSpec("目标值", NUMBER),
        FieldSpec("当前值", NUMBER),
        FieldSpec("单位"),
        FieldSpec("优先级", SINGLE_SELECT, PRIORITIES),
        FieldSpec("状态", SINGLE_SELECT, GOAL_STATUSES),
        FieldSpec("备注"),
        FieldSpec("剩余天数", NUMBER),
        FieldSpec("时间进度", NUMBER),
        FieldSpec("实际进度", NUMBER),
        FieldSpec("计划值", NUMBER),
        FieldSpec("进度差", NUMBER),
        FieldSpec("风险状态", SINGLE_SELECT, RISK_LEVELS),
        FieldSpec("7日速度", NUMBER),
        FieldSpec("14日速度", NUMBER),
        FieldSpec("30日速度", NUMBER),
        FieldSpec("预计完成日期", DATE),
    ),
    seeds=(
        {
            "目标ID": "GOAL-LC-220",
            "目标名称": "LeetCode 220 道核心题",
            "类别": "LeetCode",
            "目标类型": "COUNT",
            "开始日期": timestamp("2026-08-31"),
            "截止日期": timestamp("2027-05-31"),
            "目标值": 220,
            "当前值": 0,
            "单位": "problem",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "按阶段里程碑推进",
        },
        {
            "目标ID": "GOAL-ENGLISH-DAILY",
            "目标名称": "英语面试能力与每日训练",
            "类别": "英语",
            "目标类型": "TIME",
            "开始日期": timestamp("2026-08-31"),
            "截止日期": timestamp("2027-07-01"),
            "目标值": 9120,
            "当前值": 0,
            "单位": "minute",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "每天30分钟：自我介绍、科研介绍、英语面试、技术问答",
        },
        {
            "目标ID": "GOAL-408",
            "目标名称": "408 系统复习",
            "类别": "408",
            "目标类型": "TIME",
            "开始日期": timestamp("2026-08-31"),
            "截止日期": timestamp("2027-05-31"),
            "目标值": 0,
            "当前值": 0,
            "单位": "minute",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "数据结构、计算机网络、操作系统、计算机组成原理；目标时长待补充",
        },
        {
            "目标ID": "GOAL-RESEARCH",
            "目标名称": "科研长期投入",
            "类别": "科研",
            "目标类型": "TIME",
            "开始日期": timestamp("2026-08-31"),
            "截止日期": timestamp("2027-07-01"),
            "目标值": 0,
            "当前值": 0,
            "单位": "minute",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "具体论文项目由用户后续补充；目标时长待补充",
        },
        {
            "目标ID": "GOAL-GPA",
            "目标名称": "课程/GPA维护",
            "类别": "课程",
            "目标类型": "TIME",
            "开始日期": timestamp("2026-08-31"),
            "截止日期": timestamp("2027-05-31"),
            "目标值": 0,
            "当前值": 0,
            "单位": "minute",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "追踪每周课程学习投入；目标时长待补充",
        },
    ),
    views=("风险目标",),
)


MILESTONES = TableSpec(
    name="02_阶段里程碑",
    unique_key="里程碑ID",
    fields=(
        FieldSpec("里程碑ID"),
        FieldSpec("所属目标"),
        FieldSpec("名称"),
        FieldSpec("截止日期", DATE),
        FieldSpec("目标值", NUMBER),
        FieldSpec("当前值", NUMBER),
        FieldSpec("单位"),
        FieldSpec("状态", SINGLE_SELECT, GOAL_STATUSES),
        FieldSpec("完成日期", DATE),
        FieldSpec("备注"),
    ),
    seeds=tuple(
        {
            "里程碑ID": key,
            "所属目标": goal,
            "名称": name,
            "截止日期": timestamp(deadline),
            "目标值": target,
            "当前值": 0,
            "单位": unit,
            "状态": "未开始",
            "备注": note,
        }
        for key, goal, name, deadline, target, unit, note in (
            ("DL-CONTACT-20270201", "保研事务", "开始套磁", "2027-02-01", 1, "节点", "保研 Deadline"),
            ("DL-CAMP-READY-20270531", "保研事务", "夏令营准备完成", "2027-05-31", 1, "节点", "保研 Deadline"),
            ("DL-CAMP-20270701", "保研事务", "夏令营阶段", "2027-07-01", 1, "节点", "保研 Deadline"),
            ("LC-20261031-050", "GOAL-LC-220", "LeetCode 累计 50 题", "2026-10-31", 50, "题", ""),
            ("LC-20261231-110", "GOAL-LC-220", "LeetCode 累计 110 题", "2026-12-31", 110, "题", ""),
            ("LC-20270131-150", "GOAL-LC-220", "LeetCode 累计 150 题", "2027-01-31", 150, "题", ""),
            ("LC-20270331-180", "GOAL-LC-220", "LeetCode 累计 180 题", "2027-03-31", 180, "题", ""),
            ("LC-20270531-220", "GOAL-LC-220", "LeetCode 累计 220 题", "2027-05-31", 220, "题", ""),
        )
    ),
    views=("里程碑",),
)


DAILY_TASKS = TableSpec(
    name="03_每日任务",
    unique_key="任务名称",
    fields=(
        FieldSpec("日期", DATE),
        FieldSpec("类别", SINGLE_SELECT, CATEGORIES),
        FieldSpec("任务名称"),
        FieldSpec("所属目标"),
        FieldSpec("所属里程碑"),
        FieldSpec("计划量", NUMBER),
        FieldSpec("实际量", NUMBER),
        FieldSpec("单位"),
        FieldSpec("预计时间", NUMBER),
        FieldSpec("实际时间", NUMBER),
        FieldSpec("优先级", SINGLE_SELECT, PRIORITIES),
        FieldSpec("状态", SINGLE_SELECT, TASK_STATUSES),
        FieldSpec("是否今日", CHECKBOX),
        FieldSpec("备注"),
        FieldSpec("规则ID"),
    ),
    views=("今日", "本周", "未完成", "科研", "课程", "英语", "LeetCode", "408"),
)


CHECKINS = TableSpec(
    name="04_打卡记录",
    unique_key="内容",
    fields=(
        FieldSpec("打卡时间", DATE),
        FieldSpec("创建时间", CREATED_TIME),
        FieldSpec("日期", DATE),
        FieldSpec("类别", SINGLE_SELECT, CATEGORIES),
        FieldSpec("内容"),
        FieldSpec("所属目标"),
        FieldSpec("所属任务"),
        FieldSpec("数量", NUMBER),
        FieldSpec("单位"),
        FieldSpec("投入分钟", NUMBER),
        FieldSpec("备注"),
    ),
)


WEEKLY_REVIEWS = TableSpec(
    name="05_周复盘",
    unique_key="周次",
    fields=(
        FieldSpec("周次"),
        FieldSpec("开始日期", DATE),
        FieldSpec("结束日期", DATE),
        FieldSpec("计划时间", NUMBER),
        FieldSpec("实际时间", NUMBER),
        FieldSpec("任务完成率", NUMBER),
        FieldSpec("科研时间", NUMBER),
        FieldSpec("课程时间", NUMBER),
        FieldSpec("英语时间", NUMBER),
        FieldSpec("LeetCode题数", NUMBER),
        FieldSpec("408时间", NUMBER),
        FieldSpec("最大进展"),
        FieldSpec("最大偏差"),
        FieldSpec("风险目标"),
        FieldSpec("本周总结"),
        FieldSpec("本周问题"),
        FieldSpec("下周调整"),
    ),
    views=("周复盘",),
)


RESEARCH_PROJECTS = TableSpec(
    name="06_科研项目",
    unique_key="项目名称",
    fields=(
        FieldSpec("项目名称"),
        FieldSpec("研究方向"),
        FieldSpec(
            "当前阶段",
            SINGLE_SELECT,
            (
                "Idea",
                "Literature Review",
                "Method",
                "Implementation",
                "Experiments",
                "Writing",
                "Submission",
                "Rebuttal",
                "Revision",
                "Accepted",
            ),
        ),
        FieldSpec("开始日期", DATE),
        FieldSpec("目标投稿日期", DATE),
        FieldSpec("状态", SINGLE_SELECT, GOAL_STATUSES),
        FieldSpec("本周投入", NUMBER),
        FieldSpec("累计投入", NUMBER),
        FieldSpec("备注"),
    ),
)


TABLE_SPECS = (
    LONG_TERM_GOALS,
    MILESTONES,
    DAILY_TASKS,
    CHECKINS,
    WEEKLY_REVIEWS,
    RESEARCH_PROJECTS,
)
