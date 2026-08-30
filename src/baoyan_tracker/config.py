"""Safe, backwards-compatible configuration loading."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr

APP_ID_KEYS = ("FEISHU_APP_ID", "LARK_APP_ID", "APP_ID")
APP_SECRET_KEYS = ("FEISHU_APP_SECRET", "LARK_APP_SECRET", "APP_SECRET")
APP_TOKEN_KEYS = (
    "FEISHU_APP_TOKEN",
    "FEISHU_BASE_TOKEN",
    "BITABLE_APP_TOKEN",
)
BITABLE_URL_KEYS = ("FEISHU_BITABLE_URL",)
ENV_CANDIDATES = (".env", ".env.local", "ID.env")
TOKEN_PATTERN = re.compile(r"/(?:base|app)/([A-Za-z0-9_-]+)")


class ConfigurationError(RuntimeError):
    """Raised when required local configuration is absent."""


class Settings(BaseModel):
    """Runtime settings whose representation never exposes credentials."""

    model_config = ConfigDict(frozen=True)

    app_id: SecretStr = Field(repr=False)
    app_secret: SecretStr = Field(repr=False)
    app_token: SecretStr | None = Field(default=None, repr=False)
    bitable_url: str | None = None
    env_file: Path | None = Field(default=None, repr=False)
    api_base_url: str = "https://open.feishu.cn/open-apis"

    @property
    def app_id_value(self) -> str:
        return self.app_id.get_secret_value()

    @property
    def app_secret_value(self) -> str:
        return self.app_secret.get_secret_value()

    @property
    def resolved_app_token(self) -> str | None:
        if self.app_token:
            return self.app_token.get_secret_value()
        if self.bitable_url:
            match = TOKEN_PATTERN.search(self.bitable_url)
            if match:
                return match.group(1)
        return None


def _first(mapping: Mapping[str, str | None], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value and str(value).strip():
            return str(value).strip().strip('"').strip("'")
    return None


def discover_env(project_dir: Path) -> tuple[dict[str, str], Path | None]:
    """Merge known env files without mutating the process environment.

    Later candidates override earlier ones, and process variables override files.
    Values are deliberately never logged.
    """

    merged: dict[str, str] = {}
    chosen: Path | None = None
    for name in ENV_CANDIDATES:
        path = project_dir / name
        if path.is_file():
            for key, value in dotenv_values(path).items():
                if value is not None:
                    merged[key] = value
            chosen = path
    for key in (*APP_ID_KEYS, *APP_SECRET_KEYS, *APP_TOKEN_KEYS, *BITABLE_URL_KEYS):
        if key in os.environ:
            merged[key] = os.environ[key]
    return merged, chosen


def load_settings(project_dir: Path | None = None) -> Settings:
    project_dir = (project_dir or Path.cwd()).resolve()
    values, env_file = discover_env(project_dir)
    app_id = _first(values, APP_ID_KEYS)
    app_secret = _first(values, APP_SECRET_KEYS)
    missing: list[str] = []
    if not app_id:
        missing.append("FEISHU_APP_ID (or APP_ID/LARK_APP_ID)")
    if not app_secret:
        missing.append("FEISHU_APP_SECRET (or APP_SECRET/LARK_APP_SECRET)")
    if missing:
        raise ConfigurationError("Missing required configuration: " + ", ".join(missing))
    token = _first(values, APP_TOKEN_KEYS)
    url = _first(values, BITABLE_URL_KEYS)
    return Settings(
        app_id=SecretStr(app_id),
        app_secret=SecretStr(app_secret),
        app_token=SecretStr(token) if token else None,
        bitable_url=url,
        env_file=env_file,
    )


def save_app_token(settings: Settings, app_token: str, project_dir: Path | None = None) -> Path:
    """Persist a newly created Bitable token in an ignored local env file.

    The value is not returned in messages or written to tracked files.
    """

    project_dir = (project_dir or Path.cwd()).resolve()
    path = settings.env_file or (project_dir / "ID.env")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    replaced = False
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in APP_TOKEN_KEYS:
            if not replaced:
                output.append(f"FEISHU_APP_TOKEN={app_token}")
                replaced = True
        else:
            output.append(line)
    if not replaced:
        if output and output[-1]:
            output.append("")
        output.append(f"FEISHU_APP_TOKEN={app_token}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return path


def save_local_state(app_token: str, project_dir: Path | None = None) -> Path:
    """Write non-auth Bitable discovery state to an ignored file."""

    project_dir = (project_dir or Path.cwd()).resolve()
    path = project_dir / ".baoyan_tracker.json"
    path.write_text(json.dumps({"app_token": app_token}, ensure_ascii=False), encoding="utf-8")
    return path
