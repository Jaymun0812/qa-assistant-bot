"""Load the demo scenario, converting relative times into absolute timestamps."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .models import AlertConfig, Issue, Model

SCENARIO_FILE = Path(__file__).resolve().parent.parent / "data" / "alert_scenario.json"


def load_scenario(now: datetime, path: Path | str = SCENARIO_FILE):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    models = [
        Model(
            name=m["name"], stage_type=m["stage_type"], status=m["status"], pl_lead=m["pl_lead"],
            sign_off=(now + timedelta(days=m["sign_off_in_days"])) if m.get("sign_off_in_days") is not None else None,
        )
        for m in data["models"]
    ]
    issues = [
        Issue(
            number=i["number"], title=i["title"], folder=i["folder"], priority=i["priority"],
            must_check=i["must_check"], status=i["status"], creator=i["creator"],
            created=now - timedelta(hours=i["created_hours_ago"]),
            resolved=(now - timedelta(days=i["resolved_days_ago"])) if "resolved_days_ago" in i else None,
        )
        for i in data["issues"]
    ]
    return (models, issues, AlertConfig.from_dict(data["config"]), data["rft_mapping"], data.get("next_cycle_changes", {}))


def apply_changes(issues: list[Issue], changes: dict[str, dict]) -> None:
    for issue in issues:
        for field, value in changes.get(issue.number, {}).items():
            setattr(issue, field, value)
