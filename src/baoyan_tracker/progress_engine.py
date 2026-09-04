"""Transparent, deterministic progress and risk calculations."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from .business_time import business_today


class RiskLevel(StrEnum):
    ON_TRACK = "ON_TRACK"
    SLIGHTLY_BEHIND = "SLIGHTLY_BEHIND"
    AT_RISK = "AT_RISK"
    CRITICAL = "CRITICAL"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    progress_gap: float
    expected_progress: float
    actual_progress: float
    estimated_completion: date | None
    reasons: tuple[str, ...]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def calculate_time_progress(start: date, deadline: date, as_of: date | None = None) -> float:
    """Fraction of calendar time elapsed, clamped to [0, 1]."""

    as_of = as_of or business_today()
    if deadline <= start:
        return 1.0 if as_of >= deadline else 0.0
    return _clamp((as_of - start).days / (deadline - start).days)


def calculate_expected_value(
    target_value: float, start: date, deadline: date, as_of: date | None = None
) -> float:
    return max(target_value, 0.0) * calculate_time_progress(start, deadline, as_of)


def calculate_actual_progress(current_value: float, target_value: float) -> float:
    if target_value <= 0:
        return 0.0
    return _clamp(current_value / target_value)


def calculate_progress_gap(actual_progress: float, expected_progress: float) -> float:
    """Actual minus expected progress; a negative result means behind schedule."""

    return actual_progress - expected_progress


def calculate_velocity(
    entries: Iterable[tuple[date, float]], window_days: int, as_of: date | None = None
) -> float:
    """Average contributed quantity per calendar day in a trailing inclusive window."""

    if window_days <= 0:
        raise ValueError("window_days must be positive")
    as_of = as_of or business_today()
    start = as_of - timedelta(days=window_days - 1)
    total = sum(value for day, value in entries if start <= day <= as_of)
    return total / window_days


def estimate_completion_date(
    current_value: float,
    target_value: float,
    daily_velocity: float,
    as_of: date | None = None,
) -> date | None:
    as_of = as_of or business_today()
    if current_value >= target_value:
        return as_of
    if daily_velocity <= 0:
        return None
    days = math.ceil((target_value - current_value) / daily_velocity)
    return as_of + timedelta(days=days)


def calculate_streak(activity_dates: Iterable[date], as_of: date | None = None) -> int:
    """Count consecutive active days, retaining a streak when last active yesterday."""

    as_of = as_of or business_today()
    active = set(activity_dates)
    cursor = as_of if as_of in active else as_of - timedelta(days=1)
    streak = 0
    while cursor in active:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def calculate_risk(
    *,
    start: date,
    deadline: date,
    current_value: float,
    target_value: float,
    as_of: date | None = None,
    velocity_7d: float | None = None,
    velocity_14d: float | None = None,
    velocity_30d: float | None = None,
    days_since_activity: int | None = None,
) -> RiskAssessment:
    """Assess schedule risk using explicit thresholds and explainable escalations."""

    as_of = as_of or business_today()
    if target_value <= 0:
        return RiskAssessment(
            RiskLevel.ON_TRACK,
            0.0,
            0.0,
            0.0,
            None,
            ("目标值尚未设置，暂不评估进度风险",),
        )
    actual = calculate_actual_progress(current_value, target_value)
    expected = calculate_time_progress(start, deadline, as_of)
    gap = calculate_progress_gap(actual, expected)
    velocities = [v for v in (velocity_7d, velocity_14d, velocity_30d) if v is not None]
    forecast_velocity = (
        velocity_14d if velocity_14d is not None else (velocities[0] if velocities else 0)
    )
    forecast = estimate_completion_date(current_value, target_value, forecast_velocity, as_of)

    if target_value > 0 and current_value >= target_value:
        return RiskAssessment(RiskLevel.COMPLETED, gap, expected, actual, as_of, ("目标值已完成",))

    if gap >= 0:
        level = RiskLevel.ON_TRACK
        reasons = ["实际进度不低于计划进度"]
    elif gap >= -0.05:
        level = RiskLevel.SLIGHTLY_BEHIND
        reasons = ["进度落后不超过5个百分点"]
    elif gap >= -0.15:
        level = RiskLevel.AT_RISK
        reasons = ["进度落后5至15个百分点"]
    else:
        level = RiskLevel.CRITICAL
        reasons = ["进度落后超过15个百分点"]

    severity = {
        RiskLevel.ON_TRACK: 0,
        RiskLevel.SLIGHTLY_BEHIND: 1,
        RiskLevel.AT_RISK: 2,
        RiskLevel.CRITICAL: 3,
    }

    def escalate(minimum: RiskLevel, reason: str) -> None:
        nonlocal level
        if severity[level] < severity[minimum]:
            level = minimum
        reasons.append(reason)

    if as_of > deadline:
        escalate(RiskLevel.CRITICAL, "截止日期已过且目标未完成")
    if days_since_activity is not None and days_since_activity >= 14:
        escalate(RiskLevel.AT_RISK, "连续14天或更久没有投入")
    elif days_since_activity is not None and days_since_activity >= 7:
        escalate(RiskLevel.SLIGHTLY_BEHIND, "连续7天或更久没有投入")
    elapsed_days = max((as_of - start).days, 0)
    if forecast is None and target_value > current_value and expected > 0 and elapsed_days >= 7:
        escalate(RiskLevel.AT_RISK, "近期速度为零，无法预计完成日期")
    elif forecast is not None and forecast > deadline:
        overdue = (forecast - deadline).days
        escalate(
            RiskLevel.CRITICAL if overdue > 14 else RiskLevel.AT_RISK,
            f"按近期速度预计晚于截止日期{overdue}天",
        )
    if velocity_7d is not None and velocity_30d and velocity_7d < velocity_30d * 0.5:
        escalate(RiskLevel.AT_RISK, "最近7天速度低于30天均速的一半")

    return RiskAssessment(level, gap, expected, actual, forecast, tuple(reasons))
