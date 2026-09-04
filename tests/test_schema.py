from baoyan_tracker.schema import CCF_A_SUBMISSION_ROUTE, LONG_TERM_GOALS, MILESTONES


def test_ccf_a_route_is_a_research_result_view_not_a_new_goal() -> None:
    assert len(LONG_TERM_GOALS.seeds) == 6
    assert len(CCF_A_SUBMISSION_ROUTE.fields) == 6
    assert {row["会议"] for row in CCF_A_SUBMISSION_ROUTE.seeds} == {
        "ICML 2027",
        "IEEE S&P 2027 Cycle 2",
        "NSDI 2027 Fall Cycle",
        "USENIX Security 2027 Cycle 2",
        "SIGCOMM 2027",
    }


def test_ccf_a_milestones_are_gates_not_submission_quotas() -> None:
    milestones = {row["里程碑ID"]: row for row in MILESTONES.seeds}
    for milestone_id in (
        "CONF-20261101-SP-GATE",
        "CONF-20270110-VENUE-GATE",
        "CONF-20270331-NEXT-GATE",
    ):
        assert milestones[milestone_id]["所属目标"] == "GOAL-RESEARCH"
        assert milestones[milestone_id]["目标值"] == 1

    assert "投稿质量" in milestones["RES-20270415-DRAFT"]["名称"]
