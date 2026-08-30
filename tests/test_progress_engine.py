from __future__ import annotations

from datetime import date

import pytest

from baoyan_tracker.progress_engine import (
    RiskLevel,
    calculate_actual_progress,
    calculate_expected_value,
    calculate_progress_gap,
    calculate_risk,
    calculate_streak,
    calculate_velocity,
    estimate_completion_date,
)


def test_expected_progress_and_gap():
    start = date(2026, 1, 1)
    deadline = date(2026, 1, 11)
    assert calculate_expected_value(100, start, deadline, date(2026, 1, 6)) == 50
    actual = calculate_actual_progress(45, 100)
    assert calculate_progress_gap(actual, 0.5) == pytest.approx(-0.05)


def test_velocity_and_estimated_completion():
    as_of = date(2026, 1, 7)
    entries = [(date(2026, 1, 1), 7), (date(2026, 1, 7), 7)]
    velocity = calculate_velocity(entries, 7, as_of)
    assert velocity == 2
    assert estimate_completion_date(10, 20, velocity, as_of) == date(2026, 1, 12)
    assert estimate_completion_date(10, 20, 0, as_of) is None


def test_risk_threshold_and_forecast_escalation():
    assessment = calculate_risk(
        start=date(2026, 1, 1),
        deadline=date(2026, 1, 11),
        as_of=date(2026, 1, 6),
        current_value=40,
        target_value=100,
        velocity_14d=10,
    )
    assert assessment.level == RiskLevel.AT_RISK
    assert assessment.reasons


def test_completed_risk():
    assessment = calculate_risk(
        start=date(2026, 1, 1),
        deadline=date(2026, 2, 1),
        as_of=date(2026, 1, 10),
        current_value=100,
        target_value=100,
    )
    assert assessment.level == RiskLevel.COMPLETED


def test_unconfigured_target_is_not_false_positive_risk():
    assessment = calculate_risk(
        start=date(2026, 1, 1),
        deadline=date(2026, 2, 1),
        as_of=date(2026, 1, 10),
        current_value=0,
        target_value=0,
    )
    assert assessment.level == RiskLevel.ON_TRACK


def test_streak_allows_yesterday_but_not_older_gap():
    as_of = date(2026, 1, 10)
    active = [date(2026, 1, 9), date(2026, 1, 8), date(2026, 1, 7)]
    assert calculate_streak(active, as_of) == 3
    assert calculate_streak([date(2026, 1, 8)], as_of) == 0
