# Demo Guide

[Back to overview](../README.md) · Package: [`mqlbot_demo/`](../mqlbot_demo)

The production bot depends on internal systems. This repository re-implements its three services **offline with mock data**:

| Service | Modules | Mock data |
| --- | --- | --- |
| SME Finder | `sme_search.py`, `sme_api.py` | `data/sme_data.json` |
| PLM Issue Lookup | `plm_lookup.py`, `plm_client.py`, `plm_api.py`, `text_utils.py` | `data/plm_issues.json` |
| AI Summary | `summarizer.py` | Ollama if configured, otherwise rule-based |
| PLM Issue Alert | `alerts/` | `data/alert_scenario.json`; messages printed to the console |

## Quick Start

```bash
pip install -r requirements-demo.txt

# 1) Bot simulator + APIs
python -m uvicorn mqlbot_demo.app:app --reload
#   http://localhost:8000       chat-style bot simulator
#   http://localhost:8000/docs  interactive API docs

# 2) Alert service: two polling cycles over the mock scenario
python -m mqlbot_demo.alerts --now 2026-11-10T09:00

# 3) Tests
pytest --cov=mqlbot_demo
```

Things to try in the simulator: `wifi`, `network slicing`, `battery` in SME Finder; `DEMO-000101` (resolved, with history), `DEMO-000102` (open, cause under analysis), `DEMO-000103` (history service failure), `DEMO-999999` (not found) in Issue Lookup.

To use a local LLM for summaries, install [Ollama](https://ollama.com), pull a model, and set `OLLAMA_SUMMARY_MODEL` (e.g. `llama3.2`). Without it, the demo falls back to a deterministic rule-based summary.

## Alert Scenario

`python -m mqlbot_demo.alerts` runs two cycles five minutes apart. Times in the scenario are relative to `--now`, so it always produces alerts.

| Issue | Situation | Expected result |
| --- | --- | --- |
| DEMO-0001, 0002 | New issues on Dev / NDA models | New-issue alert |
| DEMO-0003 | New issue on a model with Sign Off in 5 days | Sign Off alert |
| DEMO-0004 | New issue on a model with Sign Off in 30 days | No alert |
| DEMO-0005 | New issue on an "always alarm" model | New-issue alert |
| DEMO-0006 | Created 3 days ago | No alert |
| DEMO-0007 | Priority A, resolved yesterday → reopened before cycle 2 | Important Resolve, then Reopen |
| DEMO-0008 | Resolved 9 days ago, not verified | Long-pending Resolve |
| DEMO-0009 | Priority B, resolved 2 days ago | No alert |
| DEMO-0010 | Priority A in an excluded folder | No alert |
| DEMO-0011 | Model already completed | No alert |
| DEMO-0012 | Folder has no model code; model found in title | New-issue alert |
| DEMO-0013 | Model has no PL Lead | Skipped and reported |

Cycle 2 shows that already-notified issues are not sent again and that the Resolve → Open transition is detected as a Reopen. Use `--now 2026-11-14T09:00` (Saturday) to see Resolve alerts held back outside the weekday 08:00–10:59 window.

## Design Choices

- **Pure, time-injected rules.** Every rule in `alerts/rules.py` receives `now` explicitly instead of reading the clock, which makes boundary conditions (exactly 7 days, 14-day Sign Off window, 10:59 vs 11:00) straightforward to test.
- **Pluggable notifier.** The engine depends on a `Notifier` protocol. The demo prints to the console; tests use a fake that can simulate failures; production would call the messenger API.
- **History keyed on the PL Lead.** History is written only after the PL Lead's message succeeds, so a failed send is retried on the next cycle. Files are written atomically (temp file + replace).
- **Graceful degradation.** If the PLM history call fails, the lookup still returns the issue details with a warning. If the LLM is unavailable, summaries fall back to rule-based output.
- **Rate limiting with an injectable clock.** The PLM client limits concurrent calls and calls per minute; tests drive it with a fake clock instead of waiting 60 seconds.

### Improvements over the production version

Re-implementing the services was also a chance to review the original design. These behaviors were changed intentionally:

| Area | Production | Demo |
| --- | --- | --- |
| Latest comment | First matching entry in API order | Chosen by date |
| Per-model extra recipients | First matching model in a message group | Union across all models in the group |
| Reopen history | Recorded on detection | Recorded after a successful send, so failures are retried |
| Model list | Accumulated in global state | Rebuilt from data for each engine |
| Rules | Read the system clock and global state | Pure functions that receive `now`, so every boundary is testable |

## Test Coverage

The suite (~100 tests) covers:

- **SME search:** scoring weights, phrase vs. word matching, excluded generic terms, team filter, `top_k` validation, stable tie-breaking, LLM-expansion fallback.
- **Issue lookup:** input aliases and template variables, HTML/table cleanup, log truncation, history fallback for cause/countermeasure, not-found and missing-input responses, history-failure degradation, rate limiting and concurrency caps.
- **Summaries:** minimum length validation, placeholder handling, offline fallback.
- **Alerts:** alert window boundaries, every category's inclusion and exclusion rules, grouping per PL Lead, recipient expansion (creator, RFT, per-model extras), deduplication across cycles and restarts, retry after failed sends, corrupted history files.
- **API contract:** request validation and response shapes the bot depends on.
