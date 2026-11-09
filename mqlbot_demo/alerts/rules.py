"""Pure classification rules. Every function takes `now` explicitly so the rules are testable."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from .models import AlertConfig, Category, Issue, Model

MODEL_CODE = re.compile(r"MDL-[A-Z]\d{3}")
SIGNOFF_EXCLUDED_STAGES = {"smr", "dev", "nda"}
REGULAR_FOLDER_TAG = "[regular folder]"


def is_alert_time(now: datetime) -> bool:
    """Resolve alerts are sent on weekdays between 08:00 and 10:59."""
    return now.weekday() < 5 and 8 <= now.hour <= 10


def extract_model_code(text: str) -> str | None:
    match = MODEL_CODE.search(text or "")
    return match.group(0) if match else None


class ModelIndex:
    def __init__(self, models: list[Model]):
        self._models = {m.name: m for m in models}

    def resolve(self, issue: Issue) -> Model | None:
        """Match by folder name first, then fall back to a model code in the title."""
        for source in (issue.folder, issue.title):
            code = extract_model_code(source)
            if code and code in self._models:
                return self._models[code]
        return None


def is_signoff_model(model: Model, now: datetime, days: int) -> bool:
    return (
        model.stage_type.lower() not in SIGNOFF_EXCLUDED_STAGES
        and model.status.lower() != "completed"
        and bool(model.pl_lead)
        and model.sign_off is not None
        and now <= model.sign_off <= now + timedelta(days=days)
    )


def classify_new(issue: Issue, model: Model | None, config: AlertConfig, now: datetime, notified: set[str]) -> Category | None:
    if model is None or not model.pl_lead or model.status.lower() == "completed":
        return None
    if issue.number in notified or issue.created < now - timedelta(days=config.new_issue_window_days):
        return None
    if model.is_dev or model.name in config.always_alarm_models:
        return Category.NEW
    if is_signoff_model(model, now, config.signoff_days):
        return Category.SIGNOFF_NEW
    return None


def _is_excluded_folder(folder: str, config: AlertConfig) -> bool:
    folder_lower = (folder or "").lower()
    return any(ex.lower() in folder_lower for ex in config.excluded_folders_for_resolved)


def classify_resolved(issue: Issue, model: Model | None, config: AlertConfig, now: datetime, resolved_log: dict[str, str]) -> Category | None:
    if issue.status != "Resolve" or issue.resolved is None or model is None or not model.pl_lead:
        return None
    if issue.resolved < now - timedelta(days=config.resolved_lookback_days):
        return None
    if _is_excluded_folder(issue.folder, config):
        return None
    last_sent = resolved_log.get(issue.number, "")
    if last_sent.startswith(now.strftime("%Y-%m-%d")):
        return None
    if issue.priority == "A" or issue.must_check == "Y":
        return Category.RESOLVE_IMPORTANT
    if (now - issue.resolved).days >= config.resolved_days_threshold and REGULAR_FOLDER_TAG not in issue.folder.lower():
        return Category.RESOLVE_LONG_PENDING
    return None


def detect_reopen(issue: Issue, model: Model | None, config: AlertConfig, now: datetime,
                  state_log: dict[str, dict], reopened_log: dict[str, str]) -> Category | None:
    """A Reopen is a recorded `Resolve` state that is now `Open`."""
    if issue.created < now - timedelta(days=config.reopen_tracking_days):
        return None
    previous = state_log.get(issue.number, {}).get("status")
    if previous != "Resolve" or issue.status != "Open":
        return None
    if reopened_log.get(issue.number, "").startswith(now.strftime("%Y-%m-%d")):
        return None
    if model is None or not (model.is_dev or is_signoff_model(model, now, config.signoff_days)):
        return None
    return Category.REOPEN
