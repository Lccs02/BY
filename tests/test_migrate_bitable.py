from __future__ import annotations

import pytest

from scripts.migrate_feishu_bitable import clean_url, snapshot


class FakeService:
    def list_tables(self):
        return [{"name": "01_长期目标", "table_id": "tbl1"}]

    def list_fields(self, _table_id):
        return [
            {"field_name": "目标ID", "type": 1},
            {"field_name": "目标值", "type": 2},
        ]

    def list_records(self, _table_id):
        return [{"fields": {"目标ID": "G1", "目标值": "12.5"}}]


def test_clean_url_removes_disposable_login_data():
    assert (
        clean_url("https://my.feishu.cn/wiki/abc123?disposable_login_token=secret#fragment")
        == "https://my.feishu.cn/wiki/abc123"
    )


def test_clean_url_rejects_non_feishu_hosts():
    with pytest.raises(ValueError):
        clean_url("https://example.com/wiki/abc123")


def test_snapshot_converts_number_field_strings():
    records = snapshot(FakeService())["01_长期目标"].records
    assert records == ({"目标ID": "G1", "目标值": 12.5},)
