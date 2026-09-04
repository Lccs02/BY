"""Migrate the configured Bitable to a user-owned Bitable or Wiki node."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from baoyan_tracker.bitable_service import BitableService
from baoyan_tracker.bootstrap import Bootstrapper
from baoyan_tracker.config import ConfigurationError, Settings, load_settings, save_app_token
from baoyan_tracker.feishu_client import FeishuAPIError, FeishuClient
from baoyan_tracker.schema import CREATED_TIME, NUMBER, TABLE_SPECS

WIKI_TOKEN_PATTERN = re.compile(r"/wiki/([A-Za-z0-9_-]+)")
BASE_TOKEN_PATTERN = re.compile(r"/(?:base|app)/([A-Za-z0-9_-]+)")


@dataclass(frozen=True)
class TableSnapshot:
    records: tuple[dict[str, Any], ...]


def clean_url(value: str) -> str:
    """Remove query and fragment data, including disposable login credentials."""

    parts = urlsplit(value.strip())
    if parts.scheme != "https" or not parts.netloc.endswith(".feishu.cn"):
        raise ValueError("target must be an https://*.feishu.cn URL")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def resolve_target_token(client: FeishuClient, target_url: str) -> str:
    base_match = BASE_TOKEN_PATTERN.search(target_url)
    if base_match:
        return base_match.group(1)
    wiki_match = WIKI_TOKEN_PATTERN.search(target_url)
    if not wiki_match:
        raise ValueError("target URL must contain /base/<token> or /wiki/<token>")
    data = client.request(
        "GET",
        "/wiki/v2/spaces/get_node",
        operation="resolve target Wiki node",
        params={"token": wiki_match.group(1)},
    )
    node = data.get("node") or data
    if node.get("obj_type") != "bitable" or not node.get("obj_token"):
        raise ValueError("target Wiki node is not a Bitable")
    return str(node["obj_token"])


def snapshot(service: BitableService) -> dict[str, TableSnapshot]:
    result: dict[str, TableSnapshot] = {}
    specs = {spec.name: spec for spec in TABLE_SPECS}
    for table in service.list_tables():
        name = str(table.get("name"))
        if name not in specs:
            continue
        table_id = str(table["table_id"])
        readonly = {
            str(field.get("field_name"))
            for field in service.list_fields(table_id)
            if field.get("type") == CREATED_TIME
        }
        number_fields = {field.name for field in specs[name].fields if field.type == NUMBER}
        records = []
        for record in service.list_records(table_id):
            fields = {
                key: value
                for key, value in (record.get("fields") or {}).items()
                if key not in readonly and value not in (None, "", [], {})
            }
            for key in number_fields & fields.keys():
                value = fields[key]
                if isinstance(value, str):
                    parsed = float(value)
                    fields[key] = int(parsed) if parsed.is_integer() else parsed
            if fields:
                records.append(fields)
        result[name] = TableSnapshot(tuple(records))
    return result


def ensure_empty_target(service: BitableService) -> None:
    tables = service.list_tables()
    for table in tables:
        table_id = str(table["table_id"])
        fields = service.list_fields(table_id)
        records = service.list_records(table_id)
        has_values = any(
            value not in (None, "", [], {})
            for record in records
            for value in (record.get("fields") or {}).values()
        )
        if table.get("name") != "数据表" or len(fields) > 1 or has_values:
            raise ValueError("target Bitable is not empty; migration stopped without changes")


def replace_records(
    service: BitableService, snapshots: dict[str, TableSnapshot]
) -> tuple[int, int]:
    tables = {str(table.get("name")): table for table in service.list_tables()}
    deleted = 0
    created = 0
    for spec in TABLE_SPECS:
        table = tables[spec.name]
        table_id = str(table["table_id"])
        for record in service.list_records(table_id):
            service.delete_record(table_id, str(record["record_id"]))
            deleted += 1
        for fields in snapshots.get(spec.name, TableSnapshot(())).records:
            service.create_record(table_id, fields)
            created += 1
    return deleted, created


def persist_target(settings: Settings, app_token: str, target_url: str) -> None:
    path = save_app_token(settings, app_token)
    lines = path.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    replaced = False
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key == "FEISHU_BITABLE_URL":
            if not replaced:
                output.append(f"FEISHU_BITABLE_URL={target_url}")
                replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"FEISHU_BITABLE_URL={target_url}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Replace records in a target whose schema was created by an interrupted migration.",
    )
    args = parser.parse_args()
    try:
        settings = load_settings()
        source_token = settings.resolved_app_token
        if not source_token:
            raise ConfigurationError("source FEISHU_APP_TOKEN is missing")
        target_url = clean_url(args.target_url)
        with FeishuClient(settings) as client:
            target_token = resolve_target_token(client, target_url)
            if target_token == source_token:
                raise ValueError("source and target Bitable are the same")
            source = BitableService(client, source_token)
            target = BitableService(client, target_token)
            snapshots = snapshot(source)
            if not args.resume:
                ensure_empty_target(target)
            counts = {name: len(data.records) for name, data in snapshots.items()}
            print(f"PLAN: migrate records {counts}")
            print("PLAN: initialize 6 tables and create 快速打卡 form view")
            print("PLAN: switch local backend configuration to the new Bitable")
            if not args.apply:
                return 0
            target.rename_app("保研监督系统")
            Bootstrapper(target).run(apply=True)
            deleted, created = replace_records(target, snapshots)
            persist_target(settings, target_token, target_url)
            print(f"APPLIED: replaced {deleted} seed records and migrated {created} records")
            print("APPLIED: local backend now targets the user-owned Bitable")
        return 0
    except (ConfigurationError, FeishuAPIError, ValueError, KeyError) as exc:
        print(f"[FAIL] Migration: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
