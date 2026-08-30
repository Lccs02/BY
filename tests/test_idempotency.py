from baoyan_tracker.bitable_service import missing_names, records_missing_by_key


def test_missing_names_preserves_order():
    assert missing_names(["A", "C"], ["A", "B", "C", "D"]) == ["B", "D"]


def test_seed_rows_are_deduplicated_by_stable_key():
    existing = [{"目标ID": "A"}]
    desired = [{"目标ID": "A"}, {"目标ID": "B"}]
    assert records_missing_by_key(existing, desired, "目标ID") == [{"目标ID": "B"}]
