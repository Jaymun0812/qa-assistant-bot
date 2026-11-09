# PLM Issue Alert

[Back to overview](../README.md) · Implementation: [`mqlbot_demo/alerts/`](../mqlbot_demo/alerts)

**A polling service that checks issue data on a schedule and messages the responsible owners about issues that need attention, so nobody has to check manually.**

In production the service polls every five minutes. The demo CLI runs two cycles back to back over a mock scenario.

## Alert Categories

| Category | Condition | When checked | Deduplication |
| --- | --- | --- | --- |
| New issue | Created within the last day, on a Dev/NDA model or an "always alarm" model | Every cycle | Sent once per issue |
| Sign Off approaching | Created within the last day, on a model whose Sign Off is within 14 days | Every cycle | Shares history with new issues |
| Important Resolve | Status `Resolve` and Priority `A` or Must Check `Y` | Weekdays 08:00–10:59 | Once per day, re-alerted next weekday until verified |
| Long-pending Resolve | Other `Resolve` issues pending 7+ days | Weekdays 08:00–10:59 | Once per day, re-alerted next weekday until verified |
| Reopen | Previously recorded `Resolve`, now `Open` | Every cycle | Once per day |

Scope rules:

- **Dev/NDA models** must be in progress and have a PL Lead.
- **Sign Off** excludes SMR, Dev, and NDA stages and completed models. Only issues created in the last day are reported; it is not a backlog sweep.
- **Resolve** checks only issues resolved within the last 90 days and skips configured excluded folders. Long-pending checks also skip `[Regular Folder]`.
- **Reopen** tracks issues created within the last 30 days, on Dev/NDA models or models approaching Sign Off.
- Issues whose model cannot be found, or whose model has no PL Lead, are reported as skipped.

### Model Matching

The model code is taken from the issue's folder name (e.g. `MDL-A100_NA_DEV` → `MDL-A100`). If the folder has no model code, the title is tried (e.g. `[MDL-A100] Hotspot clients lose connection`).

## Recipients

Issues are grouped into **one message per category per PL Lead**.

| Category | Recipients |
| --- | --- |
| New / Sign Off approaching | PL Lead + per-model extra recipients |
| Important / Long-pending Resolve | PL Lead + issue creator + the creator's RFT members (+ per-model extras for Dev/NDA) |
| Reopen | PL Lead (+ per-model extras for Dev/NDA) |
| Cycle summary | Configured management recipients |

Duplicates are removed, so a person listed more than once receives one copy.

## Sample Message

```text
[PLM Important Resolve - Verification Needed] Alert (1)

Issue: DEMO-0007
Title: Call audio cuts out on speakerphone
Model/Folder: MDL-A100 / MDL-A100_NA_DEV
Stage: dev
Priority: A  Must Check: N
Resolved: 2026-11-09 (1 day ago)
Link: https://plm.example.com/issues/DEMO-0007
```

## Reliability

| Mechanism | Behavior |
| --- | --- |
| Persistent history | Four JSON files (sent issues, Resolve log, issue states, Reopen log) survive restarts, so nothing is sent twice |
| Atomic writes | Each file is written to a temp file and then replaced, so a crash cannot leave half-written history |
| Retry on failure | History is recorded only after the PL Lead's message succeeds; a failed send is retried next cycle |
| Corrupted history | An unreadable file is treated as empty instead of crashing the service |
| State tracking | Every cycle records each tracked issue's status, which is what makes Reopen detection possible |

## Configuration

`AlertConfig` ([`models.py`](../mqlbot_demo/alerts/models.py)) holds the rules; the demo values come from the `config` block of [`data/alert_scenario.json`](../mqlbot_demo/data/alert_scenario.json).

| Setting | Default | Meaning |
| --- | --- | --- |
| `additional_recipients` | `{}` | Cycle summary recipients |
| `extra_recipients_per_project` | `{}` | Per-model extra recipients |
| `always_alarm_models` | `[]` | Models that always get new-issue alerts |
| `excluded_folders_for_resolved` | `[]` | Folder names excluded from Resolve alerts (case-insensitive) |
| `new_issue_window_days` | `1` | How recent an issue must be to count as new |
| `signoff_days` | `14` | Sign Off look-ahead window |
| `resolved_lookback_days` | `90` | Oldest Resolve date considered |
| `resolved_days_threshold` | `7` | Days until a Resolve is long-pending |
| `reopen_tracking_days` | `30` | How far back issues are tracked for Reopen |

## Running

```bash
python -m mqlbot_demo.alerts --now 2026-11-10T09:00
```

| Option | Description |
| --- | --- |
| `--now` | Simulated time (default: current time). Scenario times are relative to it |
| `--state-dir` | Where history files are written (default `.demo_state/`) |
| `--keep-state` | Reuse history from the previous run instead of starting fresh |
| `--quiet` | Show only the cycle reports, not each message |

## Extending

The engine depends on a small `Notifier` protocol:

```python
class Notifier(Protocol):
    def send(self, recipient: str, subject: str, contents: str) -> bool: ...
```

The demo ships a `ConsoleNotifier`; tests use a fake that can simulate failures. Connecting a real messenger only requires a class with the same `send` method.

## Troubleshooting

| Symptom | Check in order |
| --- | --- |
| Missing new-issue alert | Created within the last day → model matched → Dev/NDA or always-alarm → PL Lead → not already sent |
| Missing Sign Off alert | Stage not SMR/Dev/NDA → not completed → Sign Off within 14 days → created within the last day |
| Missing Resolve alert | Weekday 08:00–10:59 → status `Resolve` → resolved within 90 days → priority or elapsed days → excluded folders → not sent today |
| Missing Reopen alert | Created within 30 days → previous state `Resolve` recorded → now `Open` → Dev/NDA or Sign Off model |
| Duplicates after restart | History directory preserved between runs |
