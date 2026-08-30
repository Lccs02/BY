"""Idempotent schema and seed initialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .bitable_service import BitableService, PlannedChange, missing_names, records_missing_by_key
from .schema import TABLE_SPECS, TableSpec


@dataclass
class BootstrapResult:
    changes: list[PlannedChange] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


class Bootstrapper:
    def __init__(self, service: BitableService):
        self.service = service

    @staticmethod
    def _table_id(table: dict[str, Any]) -> str:
        return str(table["table_id"])

    def run(self, *, apply: bool) -> BootstrapResult:
        result = BootstrapResult()
        existing_tables = {item.get("name"): item for item in self.service.list_tables()}
        self._remove_blank_default_table(existing_tables, result, apply)
        for spec in TABLE_SPECS:
            table = existing_tables.get(spec.name)
            if table is None:
                result.changes.append(PlannedChange("CREATE TABLE", spec.name))
                if not apply:
                    for seed in spec.seeds:
                        result.changes.append(
                            PlannedChange("CREATE SEED", f"{spec.name}/{seed[spec.unique_key]}")
                        )
                    continue
                table = self.service.create_table(
                    spec.name, [field.api_payload() for field in spec.fields]
                )
                existing_tables[spec.name] = table
            self._ensure_fields(spec, table, result, apply)
            self._ensure_views(spec, table, result, apply)
            self._ensure_seeds(spec, table, result, apply)
        return result

    def _remove_blank_default_table(
        self,
        existing_tables: dict[Any, dict[str, Any]],
        result: BootstrapResult,
        apply: bool,
    ) -> None:
        """Remove only the untouched placeholder table created with a new Bitable app."""

        table = existing_tables.get("数据表")
        if table is None:
            return
        table_id = self._table_id(table)
        records = self.service.list_records(table_id)
        has_user_data = any(
            value not in (None, "", [], {})
            for record in records
            for value in (record.get("fields") or {}).values()
        )
        if has_user_data:
            return
        result.changes.append(PlannedChange("DELETE BLANK DEFAULT TABLE", "数据表"))
        if apply:
            self.service.delete_table(table_id)
            existing_tables.pop("数据表", None)

    def _ensure_fields(
        self,
        spec: TableSpec,
        table: dict[str, Any],
        result: BootstrapResult,
        apply: bool,
    ) -> None:
        table_id = self._table_id(table)
        existing = self.service.list_fields(table_id)
        existing_names = [str(item.get("field_name")) for item in existing]
        missing = missing_names(existing_names, [field.name for field in spec.fields])
        fields_by_name = {field.name: field for field in spec.fields}
        for name in missing:
            result.changes.append(PlannedChange("CREATE FIELD", f"{spec.name}/{name}"))
            if apply:
                self.service.create_field(table_id, fields_by_name[name].api_payload())

    def _ensure_seeds(
        self,
        spec: TableSpec,
        table: dict[str, Any],
        result: BootstrapResult,
        apply: bool,
    ) -> None:
        if not spec.seeds:
            return
        table_id = self._table_id(table)
        existing_records = self.service.list_records(table_id)
        existing_fields = [item.get("fields") or {} for item in existing_records]
        missing = records_missing_by_key(existing_fields, spec.seeds, spec.unique_key)
        for seed in missing:
            result.changes.append(
                PlannedChange("CREATE SEED", f"{spec.name}/{seed[spec.unique_key]}")
            )
            if apply:
                self.service.create_record(table_id, seed)

    def _ensure_views(
        self,
        spec: TableSpec,
        table: dict[str, Any],
        result: BootstrapResult,
        apply: bool,
    ) -> None:
        if not spec.views:
            return
        table_id = self._table_id(table)
        existing = self.service.list_views(table_id)
        existing_names = [str(item.get("view_name")) for item in existing]
        for name in missing_names(existing_names, spec.views):
            result.changes.append(PlannedChange("CREATE VIEW", f"{spec.name}/{name}"))
            if apply:
                self.service.create_view(table_id, name)
