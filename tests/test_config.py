from __future__ import annotations

from baoyan_tracker.config import load_settings


def test_loads_compatible_env_names(tmp_path, monkeypatch):
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "APP_ID", "APP_SECRET"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "ID.env").write_text("APP_ID=cli_test1234\nAPP_SECRET=very-secret\n")
    settings = load_settings(tmp_path)
    assert settings.app_id_value == "cli_test1234"
    assert settings.app_secret_value == "very-secret"


def test_secrets_are_absent_from_repr(tmp_path, monkeypatch):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    (tmp_path / "ID.env").write_text(
        "FEISHU_APP_ID=cli_private1234\nFEISHU_APP_SECRET=never-log-this\n"
    )
    rendered = repr(load_settings(tmp_path))
    assert "cli_private1234" not in rendered
    assert "never-log-this" not in rendered


def test_extracts_app_token_from_url(tmp_path, monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "cli_x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret_x")
    monkeypatch.setenv("FEISHU_BITABLE_URL", "https://example.feishu.cn/base/bascnAbC123")
    assert load_settings(tmp_path).resolved_app_token == "bascnAbC123"
