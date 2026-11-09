"""One polling cycle: classify issues, group them per PL Lead, send, and record history."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import rules
from .models import CATEGORY_TITLES, AlertConfig, Category, Issue, Model
from .notifier import Notifier
from .store import AlertHistoryStore

TIMESTAMP = "%Y-%m-%d %H:%M:%S"


@dataclass
class CycleReport:
    now: datetime
    alerts: dict[Category, list[str]] = field(default_factory=lambda: defaultdict(list))
    skipped_no_owner: list[str] = field(default_factory=list)
    messages_sent: int = 0
    failed_recipients: list[str] = field(default_factory=list)

    @property
    def total_alerts(self) -> int:
        return sum(len(v) for v in self.alerts.values())


def _unique(items):
    seen = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


class AlertEngine:
    def __init__(self, models: list[Model], config: AlertConfig, rft_mapping: dict[str, list[str]],
                 store: AlertHistoryStore, notifier: Notifier, issue_url_template: str = "{plm_id}"):
        self.index = rules.ModelIndex(models)
        self.config = config
        self.rft_mapping = rft_mapping
        self.store = store
        self.notifier = notifier
        self.issue_url_template = issue_url_template

    # ---------- classification ----------
    def classify(self, issues: list[Issue], now: datetime, report: CycleReport) -> dict[tuple[Category, str], list[tuple[Issue, Model]]]:
        groups: dict[tuple[Category, str], list[tuple[Issue, Model]]] = defaultdict(list)
        alert_window = rules.is_alert_time(now)

        for issue in issues:
            model = self.index.resolve(issue)
            if model is None or not model.pl_lead:
                if issue.created >= now - timedelta(days=self.config.new_issue_window_days):
                    report.skipped_no_owner.append(issue.number)
                continue

            categories = [
                rules.classify_new(issue, model, self.config, now, self.store.notified),
                rules.detect_reopen(issue, model, self.config, now, self.store.state_log, self.store.reopened_log),
            ]
            if alert_window:
                categories.append(rules.classify_resolved(issue, model, self.config, now, self.store.resolved_log))
            for category in filter(None, categories):
                groups[(category, model.pl_lead)].append((issue, model))

        # remember the current state of tracked issues for the next Reopen comparison
        for issue in issues:
            if issue.created >= now - timedelta(days=self.config.reopen_tracking_days):
                self.store.state_log[issue.number] = {"status": issue.status, "last_updated": now.strftime(TIMESTAMP)}
        return groups

    # ---------- recipients & message ----------
    def recipients(self, category: Category, pl_lead: str, items: list[tuple[Issue, Model]]) -> list[str]:
        extras = []
        for issue, model in items:
            if category in (Category.NEW, Category.SIGNOFF_NEW) or model.is_dev:
                extras += self.config.extra_recipients_per_project.get(model.name, [])
            if category in (Category.RESOLVE_IMPORTANT, Category.RESOLVE_LONG_PENDING):
                extras.append(issue.creator)
                extras += self.rft_mapping.get(issue.creator, [])
        return _unique([pl_lead] + extras)

    def format_message(self, category: Category, items: list[tuple[Issue, Model]], now: datetime) -> tuple[str, str]:
        subject = f"[{CATEGORY_TITLES[category]}] Alert ({len(items)})"
        lines = [subject, ""]
        for issue, model in items:
            lines += [
                f"Issue: {issue.number}",
                f"Title: {issue.title}",
                f"Model/Folder: {model.name} / {issue.folder}",
                f"Stage: {model.stage_type}" + (f" (Sign Off {model.sign_off:%Y-%m-%d})" if model.sign_off else ""),
                f"Priority: {issue.priority}  Must Check: {issue.must_check}",
            ]
            if issue.resolved and category in (Category.RESOLVE_IMPORTANT, Category.RESOLVE_LONG_PENDING):
                days = (now - issue.resolved).days
                lines.append(f"Resolved: {issue.resolved:%Y-%m-%d} ({days} day{'s' if days != 1 else ''} ago)")
            lines += [f"Link: {self.issue_url_template.format(plm_id=issue.number)}", ""]
        return subject, "\n".join(lines).rstrip()

    # ---------- history ----------
    def record(self, category: Category, items: list[tuple[Issue, Model]], now: datetime) -> None:
        stamp = now.strftime(TIMESTAMP)
        for issue, _ in items:
            if category in (Category.NEW, Category.SIGNOFF_NEW):
                self.store.notified.add(issue.number)
            elif category is Category.REOPEN:
                self.store.reopened_log[issue.number] = stamp
            else:
                self.store.resolved_log[issue.number] = stamp

    # ---------- cycle ----------
    def run_cycle(self, issues: list[Issue], now: datetime) -> CycleReport:
        report = CycleReport(now=now)
        groups = self.classify(issues, now, report)

        for (category, pl_lead), items in sorted(groups.items(), key=lambda kv: (kv[0][0].value, kv[0][1])):
            subject, contents = self.format_message(category, items, now)
            recipients = self.recipients(category, pl_lead, items)
            lead_ok = False
            for recipient in recipients:
                ok = self.notifier.send(recipient, subject, contents)
                report.messages_sent += int(ok)
                if not ok:
                    report.failed_recipients.append(recipient)
                if recipient == pl_lead:
                    lead_ok = ok
            # history is keyed on the PL Lead: a failed send is retried next cycle
            if lead_ok:
                self.record(category, items, now)
                report.alerts[category] += [issue.number for issue, _ in items]

        if report.total_alerts and self.config.additional_recipients:
            summary = self.format_summary(report)
            for recipient in self.config.additional_recipients.values():
                self.notifier.send(recipient, "[PLM Alert Summary]", summary)

        self.store.save()
        return report

    def format_summary(self, report: CycleReport) -> str:
        lines = [f"[PLM Alert Summary] {report.now:%Y-%m-%d %H:%M}"]
        for category in Category:
            if report.alerts.get(category):
                lines.append(f"- {CATEGORY_TITLES[category]}: {len(report.alerts[category])}")
        return "\n".join(lines)

