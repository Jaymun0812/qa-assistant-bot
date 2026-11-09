from datetime import datetime, timedelta

import pytest

from mqlbot_demo.alerts import Category, Issue, Model
from mqlbot_demo.alerts import rules
from tests.conftest import NOW, make_issue


@pytest.mark.parametrize("when, expected", [
    (datetime(2026, 11, 10, 8, 0), True),    # Tue 08:00 — window opens
    (datetime(2026, 11, 10, 10, 59), True),  # Tue 10:59 — last minute
    (datetime(2026, 11, 10, 7, 59), False),  # before window
    (datetime(2026, 11, 10, 11, 0), False),  # after window
    (datetime(2026, 11, 14, 9, 0), False),   # Saturday
])
def test_alert_window(when, expected):
    assert rules.is_alert_time(when) is expected


def test_model_resolved_from_folder_then_title(dev_model):
    index = rules.ModelIndex([dev_model])
    assert index.resolve(make_issue(folder="MDL-A100_NA_DEV")) is dev_model
    assert index.resolve(make_issue(folder="Common", title="[MDL-A100] crash")) is dev_model
    assert index.resolve(make_issue(folder="Common", title="no code")) is None


class TestNewIssues:
    def test_recent_issue_on_dev_model(self, dev_model, config, now):
        assert rules.classify_new(make_issue(), dev_model, config, now, set()) is Category.NEW

    def test_older_than_one_day_is_ignored(self, dev_model, config, now):
        issue = make_issue(created=now - timedelta(days=1, minutes=1))
        assert rules.classify_new(issue, dev_model, config, now, set()) is None

    def test_already_notified_is_ignored(self, dev_model, config, now):
        assert rules.classify_new(make_issue(), dev_model, config, now, {"DEMO-1"}) is None

    def test_completed_model_is_ignored(self, config, now):
        model = Model("MDL-A100", "dev", "completed", "lead")
        assert rules.classify_new(make_issue(), model, config, now, set()) is None

    def test_always_alarm_model(self, config, now):
        model = Model("MDL-E500", "MR", "active", "lead")
        assert rules.classify_new(make_issue(), model, config, now, set()) is Category.NEW

    @pytest.mark.parametrize("days_until, expected", [(5, Category.SIGNOFF_NEW), (14, Category.SIGNOFF_NEW), (15, None), (-1, None)])
    def test_signoff_window_boundaries(self, config, now, days_until, expected):
        model = Model("MDL-C300", "MR", "active", "lead", sign_off=now + timedelta(days=days_until))
        assert rules.classify_new(make_issue(), model, config, now, set()) is expected

    @pytest.mark.parametrize("stage", ["SMR", "smr"])
    def test_smr_stage_never_counts_as_signoff(self, config, now, stage):
        model = Model("MDL-C300", stage, "active", "lead", sign_off=now + timedelta(days=3))
        assert rules.classify_new(make_issue(), model, config, now, set()) is None


class TestResolved:
    def resolved(self, days_ago, **kw):
        return make_issue(status="Resolve", resolved=NOW - timedelta(days=days_ago), **kw)

    def test_priority_a_is_important(self, dev_model, config, now):
        issue = self.resolved(1, priority="A")
        assert rules.classify_resolved(issue, dev_model, config, now, {}) is Category.RESOLVE_IMPORTANT

    def test_must_check_is_important(self, dev_model, config, now):
        issue = self.resolved(1, must_check="Y")
        assert rules.classify_resolved(issue, dev_model, config, now, {}) is Category.RESOLVE_IMPORTANT

    @pytest.mark.parametrize("days_ago, expected", [(6, None), (7, Category.RESOLVE_LONG_PENDING), (89, Category.RESOLVE_LONG_PENDING), (91, None)])
    def test_long_pending_threshold_and_lookback(self, dev_model, config, now, days_ago, expected):
        assert rules.classify_resolved(self.resolved(days_ago), dev_model, config, now, {}) is expected

    def test_already_alerted_today_is_skipped_but_tomorrow_realerts(self, dev_model, config, now):
        issue = self.resolved(1, priority="A")
        log = {"DEMO-1": now.strftime("%Y-%m-%d 08:00:00")}
        assert rules.classify_resolved(issue, dev_model, config, now, log) is None
        assert rules.classify_resolved(issue, dev_model, config, now + timedelta(days=1), log) is Category.RESOLVE_IMPORTANT

    def test_excluded_folder_is_case_insensitive(self, dev_model, config, now):
        issue = self.resolved(1, priority="A", folder="my SANDBOX folder")
        assert rules.classify_resolved(issue, dev_model, config, now, {}) is None

    def test_regular_folder_excluded_only_from_long_pending(self, dev_model, config, now):
        assert rules.classify_resolved(self.resolved(10, folder="[Regular Folder] MDL-A100"), dev_model, config, now, {}) is None
        assert rules.classify_resolved(self.resolved(10, priority="A", folder="[Regular Folder] MDL-A100"),
                                       dev_model, config, now, {}) is Category.RESOLVE_IMPORTANT

    def test_open_issue_is_not_a_resolve_alert(self, dev_model, config, now):
        assert rules.classify_resolved(make_issue(priority="A"), dev_model, config, now, {}) is None


class TestReopen:
    def test_resolve_to_open_is_reopen(self, dev_model, config, now):
        state = {"DEMO-1": {"status": "Resolve"}}
        assert rules.detect_reopen(make_issue(), dev_model, config, now, state, {}) is Category.REOPEN

    @pytest.mark.parametrize("previous", [None, "Open", "Reject"])
    def test_other_transitions_are_not_reopen(self, dev_model, config, now, previous):
        state = {"DEMO-1": {"status": previous}} if previous else {}
        assert rules.detect_reopen(make_issue(), dev_model, config, now, state, {}) is None

    def test_issues_older_than_tracking_window_are_ignored(self, dev_model, config, now):
        issue = make_issue(created=now - timedelta(days=31))
        assert rules.detect_reopen(issue, dev_model, config, now, {"DEMO-1": {"status": "Resolve"}}, {}) is None

    def test_non_dev_model_needs_upcoming_signoff(self, config, now):
        state = {"DEMO-1": {"status": "Resolve"}}
        no_signoff = Model("MDL-D400", "MR", "active", "lead")
        soon = Model("MDL-C300", "MR", "active", "lead", sign_off=now + timedelta(days=3))
        assert rules.detect_reopen(make_issue(), no_signoff, config, now, state, {}) is None
        assert rules.detect_reopen(make_issue(), soon, config, now, state, {}) is Category.REOPEN
