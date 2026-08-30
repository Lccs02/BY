"""Authenticate against Feishu without printing credentials or tokens."""

from __future__ import annotations

from baoyan_tracker.config import ConfigurationError, load_settings
from baoyan_tracker.feishu_client import FeishuAPIError, FeishuClient


def main() -> int:
    try:
        settings = load_settings()
        with FeishuClient(settings) as client:
            client.authenticate()
        print("[PASS] Feishu authentication successful")
        return 0
    except (ConfigurationError, FeishuAPIError) as exc:
        print(f"[FAIL] Feishu authentication: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
