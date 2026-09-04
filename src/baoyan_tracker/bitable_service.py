"""High-level, idempotent operations for Feishu Bitable."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .feishu_client import FeishuAPIError, FeishuClient


@dataclass(frozen=True)
class PlannedChange:
    action: str
    resource: str

    def __str__(self) -> str:
        return f"{self.action}: {self.resource}"


def missing_names(existing: Iterable[str], desired: Iterable[str]) -> list[str]:
    """Return desired names that do not already exist, retaining desired order."""

    known = set(existing)
    return [name for name in desired if name not in known]


def records_missing_by_key(
    existing: Iterable[dict[str, Any]], desired: Iterable[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    """Select seed rows whose stable key is absent from existing rows."""

    known = {row.get(key) for row in existing}
    return [row for row in desired if row.get(key) not in known]


class BitableService:
    def __init__(self, client: FeishuClient, app_token: str):
        self.client = client
        self.app_token = app_token

    @classmethod
    def create_app(cls, client: FeishuClient, name: str) -> BitableService:
        data = client.request(
            "POST",
            "/bitable/v1/apps",
            operation="create Bitable app",
            json={"name": name},
        )
        app = data.get("app") or data
        token = app.get("app_token")
        if not token:
            raise FeishuAPIError("create Bitable app", "invalid_response", "app_token missing")
        return cls(client, str(token))

    def rename_app(self, name: str) -> None:
        self.client.request(
            "PUT",
            f"/bitable/v1/apps/{self.app_token}",
            operation="rename Bitable app",
            json={"name": name},
        )

    def _list_paginated(self, path: str, operation: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            data = self.client.request("GET", path, operation=operation, params=params)
            items.extend(data.get("items") or [])
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
        return items

    def list_tables(self) -> list[dict[str, Any]]:
        return self._list_paginated(
            f"/bitable/v1/apps/{self.app_token}/tables", "list Bitable tables"
        )

    def create_table(self, name: str, fields: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        table: dict[str, Any] = {"name": name, "default_view_name": "默认视图"}
        if fields:
            table["fields"] = fields
        data = self.client.request(
            "POST",
            f"/bitable/v1/apps/{self.app_token}/tables",
            operation=f"create table {name}",
            json={"table": table},
        )
        return data.get("table") or data

    def delete_table(self, table_id: str) -> None:
        self.client.request(
            "DELETE",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}",
            operation="delete Bitable table",
        )

    def rename_table(self, table_id: str, name: str) -> None:
        self.client.request(
            "PATCH",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}",
            operation="rename Bitable table",
            json={"name": name},
        )

    def list_fields(self, table_id: str) -> list[dict[str, Any]]:
        return self._list_paginated(
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields",
            "list Bitable fields",
        )

    def create_field(self, table_id: str, field: dict[str, Any]) -> dict[str, Any]:
        data = self.client.request(
            "POST",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields",
            operation=f"create field {field.get('field_name', '')}",
            json=field,
        )
        return data.get("field") or data

    def list_views(self, table_id: str) -> list[dict[str, Any]]:
        return self._list_paginated(
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/views",
            "list Bitable views",
        )

    def create_view(self, table_id: str, name: str, *, view_type: str = "grid") -> dict[str, Any]:
        data = self.client.request(
            "POST",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/views",
            operation=f"create view {name}",
            json={"view_name": name, "view_type": view_type},
        )
        return data.get("view") or data

    def list_records(self, table_id: str) -> list[dict[str, Any]]:
        return self._list_paginated(
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records",
            "list Bitable records",
        )

    def create_record(self, table_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        data = self.client.request(
            "POST",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records",
            operation="create Bitable record",
            json={"fields": fields},
        )
        return data.get("record") or data

    def get_record(self, table_id: str, record_id: str) -> dict[str, Any]:
        data = self.client.request(
            "GET",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}",
            operation="read Bitable record",
        )
        return data.get("record") or data

    def update_record(
        self, table_id: str, record_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        data = self.client.request(
            "PUT",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}",
            operation="update Bitable record",
            json={"fields": fields},
        )
        return data.get("record") or data

    def delete_record(self, table_id: str, record_id: str) -> None:
        self.client.request(
            "DELETE",
            f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}",
            operation="delete Bitable record",
        )

    def connection_test(self, emit: Callable[[str], None] = print) -> bool:
        """Perform the mandated create/write/read/delete smoke test."""

        table = self.create_table(
            "__codex_connection_test__",
            [
                {"field_name": "测试文本", "type": 1},
                {"field_name": "测试数值", "type": 2},
            ],
        )
        table_id = str(table["table_id"])
        emit("[PASS] Bitable create table")
        fields = self.list_fields(table_id)
        names = {item.get("field_name") for item in fields}
        if not {"测试文本", "测试数值"}.issubset(names):
            raise FeishuAPIError("create test fields", "verification", "test fields missing")
        emit("[PASS] Bitable create field")
        record = self.create_record(
            table_id, {"测试文本": "Codex API Connection OK", "测试数值": 1}
        )
        emit("[PASS] Bitable create record")
        record_id = str(record["record_id"])
        fetched = self.get_record(table_id, record_id)
        values = fetched.get("fields") or {}
        if (
            values.get("测试文本") != "Codex API Connection OK"
            or float(values.get("测试数值", 0)) != 1.0
        ):
            raise FeishuAPIError("read test record", "verification", "record values differ")
        emit("[PASS] Bitable read record")
        try:
            self.delete_table(table_id)
            emit("[PASS] Bitable delete test table")
            return True
        except FeishuAPIError:
            self.rename_table(table_id, "__codex_connection_test__DELETE_ME")
            return False
