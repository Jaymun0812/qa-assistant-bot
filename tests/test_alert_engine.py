from datetime import timedelta

from mqlbot_demo.alerts import AlertEngine, AlertHistoryStore, Category
from mqlbot_demo.alerts.notifier import SentMessage
from mqlbot_demo.alerts.scenario import apply_changes, load_scenario
from tests.conftest import NOW


class FakeNotifier:
    def __init__(self, fail_for=()):
        self.fail_for = set(fail_for)
        self.sent: list[SentMessage] = []

    def send(self, recipient, subject, contents):
        if recipient in self.fail_for:
            return False
        self.sent.append(SentMessage(recipient, subject, contents))
        return True

    def to(self, recipient):
        return [m for m in self.sent if m.recipient == recipient]


def build(tmp_path, now=NOW, notifier=None):
    models, issues, config, rft, changes = load_scenario(now)
    notifier = notifier or FakeNotifier()
    store = AlertHistoryStore(tmp_path).load()
    return AlertEngine(models, config, rft, store, notifier), issues, changes, notifier


def test_scenario_cycle_one_classification(tmp_path):
    engine, issues, _, _ = build(tmp_path)
    report = engine.run_cycle(issues, NOW)
    assert sorted(report.alerts[Category.NEW]) == ["DEMO-0001", "DEMO-0002", "DEMO-0005", "DEMO-0012"]
    assert report.alerts[Category.SIGNOFF_NEW] == ["DEMO-0003"]
    assert report.alerts[Category.RESOLVE_IMPORTANT] == ["DEMO-0007"]
    assert report.alerts[Category.RESOLVE_LONG_PENDING] == ["DEMO-0008"]
    assert report.skipped_no_owner == ["DEMO-0013"]


def test_issues_are_grouped_into_one_message_per_pl_lead(tmp_path):
    engine, issues, _, notifier = build(tmp_path)
    engine.run_cycle(issues, NOW)
    new_for_alpha = [m for m in notifier.to("lead.alpha") if m.subject.startswith("[PLM New Issue]")]
    assert len(new_for_alpha) == 1
    assert "DEMO-0001" in new_for_alpha[0].contents and "DEMO-0012" in new_for_alpha[0].contents


def test_resolve_alert_reaches_creator_and_rft_members(tmp_path):
    engine, issues, _, notifier = build(tmp_path)
    engine.run_cycle(issues, NOW)
    for recipient in ("lead.alpha", "sam.qa", "rft.one", "rft.two"):
        assert any("Important Resolve" in m.subject for m in notifier.to(recipient)), recipient


def test_second_cycle_detects_reopen_and_does_not_resend(tmp_path):
    engine, issues, changes, notifier = build(tmp_path)
    engine.run_cycle(issues, NOW)
    apply_changes(issues, changes)
    notifier.sent.clear()
    report = engine.run_cycle(issues, NOW + timedelta(minutes=5))
    assert dict(report.alerts) == {Category.REOPEN: ["DEMO-0007"]}
    assert {m.recipient for m in notifier.sent} == {"lead.alpha", "qa.manager"}


def test_history_survives_restart(tmp_path):
    engine, issues, _, _ = build(tmp_path)
    engine.run_cycle(issues, NOW)
    restarted, issues2, _, notifier = build(tmp_path)
    report = restarted.run_cycle(issues2, NOW + timedelta(minutes=5))
    assert report.total_alerts == 0
    assert all(m.subject == "[PLM Alert Summary]" for m in notifier.sent) or not notifier.sent


def test_failed_pl_lead_send_is_retried_next_cycle(tmp_path):
    engine, issues, _, notifier = build(tmp_path, notifier=FakeNotifier(fail_for={"lead.beta"}))
    first = engine.run_cycle(issues, NOW)
    assert "DEMO-0002" not in first.alerts[Category.NEW]
    assert "lead.beta" in first.failed_recipients
    notifier.fail_for.clear()
    second = engine.run_cycle(issues, NOW + timedelta(minutes=5))
    assert second.alerts[Category.NEW] == ["DEMO-0002"]


def test_resolve_alerts_are_not_sent_outside_window(tmp_path):
    saturday = NOW + timedelta(days=4)
    engine, issues, _, _ = build(tmp_path, now=saturday)
    report = engine.run_cycle(issues, saturday)
    assert Category.RESOLVE_IMPORTANT not in report.alerts
    assert Category.RESOLVE_LONG_PENDING not in report.alerts
    assert report.alerts[Category.NEW]  # new-issue alerts still run on weekends


def test_management_summary_is_sent(tmp_path):
    engine, issues, _, notifier = build(tmp_path)
    engine.run_cycle(issues, NOW)
    summary = [m for m in notifier.to("qa.manager") if m.subject == "[PLM Alert Summary]"]
    assert len(summary) == 1 and "PLM New Issue: 4" in summary[0].contents


def test_corrupted_history_file_does_not_crash(tmp_path):
    (tmp_path / "notified_issues.json").write_text("{not json", encoding="utf-8")
    store = AlertHistoryStore(tmp_path).load()
    assert store.notified == set()
