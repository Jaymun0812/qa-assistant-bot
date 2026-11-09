from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Category(str, Enum):
    NEW = "new"
    SIGNOFF_NEW = "signoff_new"
    RESOLVE_IMPORTANT = "resolve_important"
    RESOLVE_LONG_PENDING = "resolve_long_pending"
    REOPEN = "reopen"


CATEGORY_TITLES = {
    Category.NEW: "PLM New Issue",
    Category.SIGNOFF_NEW: "PLM New Issue - Sign Off Approaching",
    Category.RESOLVE_IMPORTANT: "PLM Important Resolve - Verification Needed",
    Category.RESOLVE_LONG_PENDING: "PLM Long-Pending Resolve",
    Category.REOPEN: "PLM Reopened Issue",
}


@dataclass
class Model:
    name: str
    stage_type: str
    status: str
    pl_lead: str
    sign_off: datetime | None = None

    @property
    def is_dev(self) -> bool:
        """Dev/NDA models in progress with an assigned PL Lead."""
        return self.stage_type.lower() in ("dev", "nda") and self.status.lower() != "completed" and bool(self.pl_lead)


@dataclass
class Issue:
    number: str
    title: str
    folder: str
    priority: str
    must_check: str
    status: str
    created: datetime
    creator: str
    resolved: datetime | None = None


@dataclass
class AlertConfig:
    additional_recipients: dict[str, str] = field(default_factory=dict)
    extra_recipients_per_project: dict[str, list[str]] = field(default_factory=dict)
    always_alarm_models: list[str] = field(default_factory=list)
    excluded_folders_for_resolved: list[str] = field(default_factory=list)
    new_issue_window_days: int = 1
    signoff_days: int = 14
    resolved_lookback_days: int = 90
    resolved_days_threshold: int = 7
    reopen_tracking_days: int = 30

    @classmethod
    def from_dict(cls, data: dict) -> "AlertConfig":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)
