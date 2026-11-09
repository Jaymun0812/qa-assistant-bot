"""Run the alert demo: two polling cycles over the mock scenario.

    python -m mqlbot_demo.alerts --now 2026-11-10T09:00

Cycle 1 sends new-issue and Resolve alerts. Between cycles one resolved issue
is reopened. Cycle 2 shows the Reopen alert and that nothing is sent twice.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta

from . import rules
from .engine import AlertEngine
from .models import CATEGORY_TITLES, Category
from .notifier import ConsoleNotifier
from .scenario import apply_changes, load_scenario
from .store import AlertHistoryStore


def print_report(title, report):
    print(f"\n{'=' * 64}\n{title} — {report.now:%a %Y-%m-%d %H:%M}"
          f" (Resolve window: {'open' if rules.is_alert_time(report.now) else 'closed'})\n{'=' * 64}")
    if not report.total_alerts:
        print("No new alerts (already notified issues are deduplicated).")
    for category in Category:
        if report.alerts.get(category):
            print(f"  {CATEGORY_TITLES[category]:<45} {', '.join(report.alerts[category])}")
    if report.skipped_no_owner:
        print(f"  Skipped (no PL Lead / unknown model): {', '.join(report.skipped_no_owner)}")
    print(f"  Messages sent: {report.messages_sent}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="MQL_PLMate alert demo")
    parser.add_argument("--now", help="Simulated time, e.g. 2026-11-10T09:00 (default: current time)")
    parser.add_argument("--state-dir", default=".demo_state", help="Where alert history JSON files are written")
    parser.add_argument("--keep-state", action="store_true", help="Reuse history from a previous run")
    parser.add_argument("--quiet", action="store_true", help="Hide individual messages")
    args = parser.parse_args(argv)

    now = datetime.fromisoformat(args.now) if args.now else datetime.now().replace(microsecond=0)
    if not args.keep_state:
        shutil.rmtree(args.state_dir, ignore_errors=True)

    models, issues, config, rft_mapping, changes = load_scenario(now)
    store = AlertHistoryStore(args.state_dir).load()
    engine = AlertEngine(models, config, rft_mapping, store, ConsoleNotifier(verbose=not args.quiet),
                         issue_url_template="https://plm.example.com/issues/{plm_id}")

    print_report("Cycle 1", engine.run_cycle(issues, now))
    apply_changes(issues, changes)
    print(f"\n↻ Between cycles: {', '.join(changes)} changed {changes}")
    print_report("Cycle 2 (+5 min)", engine.run_cycle(issues, now + timedelta(minutes=5)))
    print(f"\nHistory saved to {args.state_dir}/")


if __name__ == "__main__":
    main()
