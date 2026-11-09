"""JSON-backed alert history, so restarts do not re-send alerts."""

from __future__ import annotations

import json
import os
from pathlib import Path

FILES = {
    "notified": "notified_issues.json",
    "resolved_log": "resolved_notification_log.json",
    "state_log": "issue_state_log.json",
    "reopened_log": "reopened_notification_log.json",
}


class AlertHistoryStore:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory)
        self.notified: set[str] = set()
        self.resolved_log: dict[str, str] = {}
        self.state_log: dict[str, dict] = {}
        self.reopened_log: dict[str, str] = {}

    def _read(self, key: str, default):
        path = self.directory / FILES[key]
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def load(self) -> "AlertHistoryStore":
        self.notified = set(self._read("notified", []))
        self.resolved_log = self._read("resolved_log", {})
        self.state_log = self._read("state_log", {})
        self.reopened_log = self._read("reopened_log", {})
        return self

    def save(self) -> None:
        """Write each file atomically (temp file + replace) to avoid half-written history."""
        self.directory.mkdir(parents=True, exist_ok=True)
        payloads = {
            "notified": sorted(self.notified),
            "resolved_log": self.resolved_log,
            "state_log": self.state_log,
            "reopened_log": self.reopened_log,
        }
        for key, data in payloads.items():
            path = self.directory / FILES[key]
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
