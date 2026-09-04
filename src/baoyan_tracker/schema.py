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
    form_views: tuple[str, ...] = ()


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
            "开始日期": timestamp("2026-09-01"),
            "截止日期": timestamp("2027-05-31"),
            "目标值": 220,
            "当前值": 0,
            "单位": "problem",
            "优先级": "P2",
            "状态": "进行中",
            "备注": "算法副线；按 50→110→150→180→220 推进，完成后只做高频题二刷，不继续堆数量。",
        },
        {
            "目标ID": "GOAL-ENGLISH-DAILY",
            "目标名称": "CET-6 500+（冲刺 550）",
            "类别": "英语",
            "目标类型": "TIME",
            "开始日期": timestamp("2026-09-01"),
            "截止日期": timestamp("2026-12-31"),
            "目标值": 7200,
            "当前值": 0,
            "单位": "minute",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "当前 445；2026 年 12 月重考，底线 500、冲刺 550。9 月基线，10 月提分，11 月稳定 500+，12 月考试。",
        },
        {
            "目标ID": "GOAL-408",
            "目标名称": "408 一轮复习与真题强化",
            "类别": "408",
            "目标类型": "TIME",
            "开始日期": timestamp("2026-09-01"),
            "截止日期": timestamp("2027-05-31"),
            "目标值": 9000,
            "当前值": 0,
            "单位": "minute",
            "优先级": "P2",
            "状态": "进行中",
            "备注": "长期副线，每周约 4 小时；先完成一轮系统复习，再进入真题与错题强化，不挤占科研。",
        },
        {
            "目标ID": "GOAL-RESEARCH",
            "目标名称": "科研主线：时空预测→World Model+RL→网络智能决策",
            "类别": "科研",
            "目标类型": "TIME",
            "开始日期": timestamp("2026-09-01"),
            "截止日期": timestamp("2027-08-31"),
            "目标值": 25200,
            "当前值": 0,
            "单位": "minute",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "最高优先级。IoTJ 卫星多业务流量预测与 AAAI 多粒度时空预测 → World Model → RL → 网络/卫星网络智能决策；以成果里程碑为主，420 小时仅监控连续投入。",
        },
        {
            "目标ID": "GOAL-GPA",
            "目标名称": "专业排名稳定前 5%",
            "类别": "课程",
            "目标类型": "TIME",
            "开始日期": timestamp("2026-09-01"),
            "截止日期": timestamp("2027-06-30"),
            "目标值": 14400,
            "当前值": 0,
            "单位": "minute",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "当前约前 5%–10%，目标稳定前 5%；只记录课程核心投入，最终判断以学期成绩与专业排名为准。",
        },
        {
            "目标ID": "GOAL-BAOYAN-MENTORS",
            "目标名称": "保研申请与导师池（≥30 人）",
            "类别": "保研事务",
            "目标类型": "COUNT",
            "开始日期": timestamp("2026-12-01"),
            "截止日期": timestamp("2027-08-31"),
            "目标值": 30,
            "当前值": 0,
            "单位": "导师",
            "优先级": "P0",
            "状态": "进行中",
            "备注": "清北第一梯队，C9/中科院第二梯队，强 985 保底梯队；2027-02-01 固定开始正式套磁。每新增 1 位完成初筛的导师记 1。",
        },
    ),
    views=("清北差距总览", "风险目标"),
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
            "状态": status,
            "备注": note,
        }
        for key, goal, name, deadline, target, unit, note, status in (
            (
                "RES-20260930-SCOPE",
                "GOAL-RESEARCH",
                "完成 World Model/RL 调研与科研主线收敛",
                "2026-09-30",
                1,
                "节点",
                "输出方向图谱、核心论文清单，以及与卫星/网络智能决策的桥接问题。",
                "进行中",
            ),
            (
                "RES-20261115-BASELINE",
                "GOAL-RESEARCH",
                "完成问题定义、数据方案与可复现 baseline",
                "2026-11-15",
                1,
                "节点",
                "明确任务、指标、强基线与复现实验，避免只做概念堆叠。",
                "未开始",
            ),
            (
                "RES-20270215-EXPERIMENT",
                "GOAL-RESEARCH",
                "完成 World Model + RL 初步实验",
                "2027-02-15",
                1,
                "节点",
                "得到可解释的初步结果，并确定消融与对照实验。",
                "未开始",
            ),
            (
                "RES-20270415-DRAFT",
                "GOAL-RESEARCH",
                "形成完整科研项目与论文初稿",
                "2027-04-15",
                1,
                "节点",
                "问题、方法、实验、局限和下一步形成闭环。",
                "未开始",
            ),
            (
                "RES-20270520-CAMP",
                "GOAL-RESEARCH",
                "夏令营前形成可展示科研成果包",
                "2027-05-20",
                1,
                "节点",
                "包含代码/实验、图表、论文稿或技术报告，以及 5 分钟科研陈述。",
                "未开始",
            ),
            (
                "ENG-20260930-BASELINE",
                "GOAL-ENGLISH-DAILY",
                "完成 CET-6 基线模考与错因分析",
                "2026-09-30",
                1,
                "节点",
                "保留总分及听力、阅读、写作翻译分项基线。",
                "进行中",
            ),
            (
                "ENG-20261031-0480",
                "GOAL-ENGLISH-DAILY",
                "连续 3 次模考均分达到 480",
                "2026-10-31",
                480,
                "分",
                "阶段提分检查，不以单次最高分代替稳定水平。",
                "未开始",
            ),
            (
                "ENG-20261130-0500",
                "GOAL-ENGLISH-DAILY",
                "连续 3 次模考均分稳定 500+",
                "2026-11-30",
                500,
                "分",
                "底线 500；如已稳定达标，再向 550 冲刺。",
                "未开始",
            ),
            (
                "ENG-20261231-EXAM",
                "GOAL-ENGLISH-DAILY",
                "参加 2026 年 12 月 CET-6",
                "2026-12-31",
                1,
                "节点",
                "具体考试日以准考证为准；成绩目标 500+，冲刺 550。",
                "未开始",
            ),
            (
                "GPA-20260930-BASELINE",
                "GOAL-GPA",
                "记录当前排名并锁定高风险课程",
                "2026-09-30",
                1,
                "节点",
                "记录当前专业排名区间、核心课程权重与最可能拉低排名的课程。",
                "进行中",
            ),
            (
                "GPA-20270131-AUTUMN",
                "GOAL-GPA",
                "秋季学期成绩与排名复盘：进入前 5%",
                "2027-01-31",
                5,
                "排名%",
                "以教务成绩和正式排名为准；排名数值越小越好，需手动更新状态。",
                "未开始",
            ),
            (
                "GPA-20270630-FINAL",
                "GOAL-GPA",
                "春季学期结束后专业排名稳定前 5%",
                "2027-06-30",
                5,
                "排名%",
                "面向夏令营/预推免材料的最终核心排名指标。",
                "未开始",
            ),
            (
                "408-20270131-ROUND1",
                "GOAL-408",
                "完成 408 一轮系统复习",
                "2027-01-31",
                1,
                "节点",
                "四科形成完整知识框架和薄弱点清单。",
                "未开始",
            ),
            (
                "408-20270531-INTENSIVE",
                "GOAL-408",
                "完成首轮真题与错题强化框架",
                "2027-05-31",
                1,
                "节点",
                "进入真题/强化阶段即可，不追求挤占科研时间。",
                "未开始",
            ),
            (
                "BAOYAN-20270115-PACK",
                "GOAL-BAOYAN-MENTORS",
                "完成 CV、科研介绍与成果证据包 V1",
                "2027-01-15",
                1,
                "节点",
                "突出独立一作 IoTJ、AAAI 和连续科研主线；EI 作为经历，不作为主卖点。",
                "未开始",
            ),
            (
                "BAOYAN-20270131-POOL",
                "GOAL-BAOYAN-MENTORS",
                "目标导师池达到 30 人",
                "2027-01-31",
                30,
                "导师",
                "清北优先，C9/中科院次之，强 985 保底；完成研究匹配和梯队标记。",
                "未开始",
            ),
            (
                "DL-CONTACT-20270201",
                "GOAL-BAOYAN-MENTORS",
                "开始正式套磁",
                "2027-02-01",
                1,
                "节点",
                "固定时间点，不提前；按梯队个性化联系。",
                "未开始",
            ),
            (
                "BAOYAN-20270331-CONTACT",
                "GOAL-BAOYAN-MENTORS",
                "完成首轮分层套磁与跟进",
                "2027-03-31",
                1,
                "节点",
                "记录回复、方向匹配、后续动作，不用邮件数量制造虚假进度。",
                "未开始",
            ),
            (
                "DL-CAMP-READY-20270531",
                "GOAL-BAOYAN-MENTORS",
                "夏令营材料与中英文科研介绍定稿",
                "2027-05-31",
                1,
                "节点",
                "CV、成绩、个人陈述、推荐材料、科研陈述和常见面试问题统一归档。",
                "未开始",
            ),
            (
                "DL-CAMP-20270701",
                "GOAL-BAOYAN-MENTORS",
                "进入夏令营/预推免集中阶段",
                "2027-07-01",
                1,
                "节点",
                "以清北为第一梯队，同时保持 C9/中科院/强 985 梯度。",
                "未开始",
            ),
            (
                "BAOYAN-20270831-REVIEW",
                "GOAL-BAOYAN-MENTORS",
                "完成夏令营/预推免阶段复盘与选择",
                "2027-08-31",
                1,
                "节点",
                "汇总 offer、导师匹配、研究方向与风险，形成下一阶段决策。",
                "未开始",
            ),
            (
                "LC-20261031-050",
                "GOAL-LC-220",
                "LeetCode 累计 50 题",
                "2026-10-31",
                50,
                "problem",
                "",
                "进行中",
            ),
            (
                "LC-20261231-110",
                "GOAL-LC-220",
                "LeetCode 累计 110 题",
                "2026-12-31",
                110,
                "problem",
                "",
                "进行中",
            ),
            (
                "LC-20270131-150",
                "GOAL-LC-220",
                "LeetCode 累计 150 题",
                "2027-01-31",
                150,
                "problem",
                "",
                "进行中",
            ),
            (
                "LC-20270331-180",
                "GOAL-LC-220",
                "LeetCode 累计 180 题",
                "2027-03-31",
                180,
                "problem",
                "",
                "进行中",
            ),
            (
                "LC-20270531-220",
                "GOAL-LC-220",
                "LeetCode 累计 220 题",
                "2027-05-31",
                220,
                "problem",
                "",
                "进行中",
            ),
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
    form_views=("快速打卡",),
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
    seeds=(
        {
            "项目名称": "EI 水印方向会议论文",
            "研究方向": "数字水印（课程作业转化）",
            "当前阶段": "Accepted",
            "状态": "已完成",
            "本周投入": 0,
            "累计投入": 0,
            "备注": "一作已录用；作为科研起点与完整经历，不作为后续清北申请的核心研究主线。",
        },
        {
            "项目名称": "IoTJ 卫星多业务流量预测",
            "研究方向": "卫星网络、多业务流量预测、时空建模",
            "当前阶段": "Submission",
            "状态": "进行中",
            "本周投入": 0,
            "累计投入": 0,
            "备注": "中科院二区 TOP 期刊在投；独立一作。持续维护审稿回应、代码与实验可复现性。",
        },
        {
            "项目名称": "AAAI 多粒度时空预测",
            "研究方向": "多粒度时空预测",
            "当前阶段": "Submission",
            "状态": "进行中",
            "本周投入": 0,
            "累计投入": 0,
            "备注": "AAAI 在投；独立一作。沉淀可迁移的方法、实验与科研叙事。",
        },
        {
            "项目名称": "World Model 驱动的网络智能决策",
            "研究方向": "World Model、Reinforcement Learning、卫星/网络智能决策",
            "当前阶段": "Literature Review",
            "开始日期": timestamp("2026-09-01"),
            "目标投稿日期": timestamp("2027-05-31"),
            "状态": "进行中",
            "本周投入": 0,
            "累计投入": 0,
            "备注": "承接 IoTJ 与 AAAI 的预测能力，向预测—建模—决策闭环延伸，形成连续科研主线。",
        },
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
