from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "feishu-sync.yml"


def test_github_actions_workflow_structure_and_secret_references():
    text = WORKFLOW.read_text(encoding="utf-8")
    document = yaml.load(text, Loader=yaml.BaseLoader)
    assert "workflow_dispatch" in document["on"]
    assert document["on"]["schedule"][0]["cron"] == "17 * * * *"
    job = document["jobs"]["daily-job"]
    assert job["env"]["BUSINESS_TIMEZONE"] == "Asia/Shanghai"
    assert "python scripts/daily_job.py --apply" in text
    for name in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APP_TOKEN"):
        assert f"secrets.{name}" in text
    assert "tenant_access_token" not in text
