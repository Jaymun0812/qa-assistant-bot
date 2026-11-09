# SME Finder

[Back to overview](../README.md) · Implementation: [`sme_search.py`](../mqlbot_demo/sme_search.py), [`sme_api.py`](../mqlbot_demo/sme_api.py)

**Enter a technical keyword or an issue-related sentence to find the subject matter experts (SMEs) on the team.**

## User Flow

1. Open SME Finder in the bot.
2. Enter a technical keyword or description, e.g. `wifi`, `network slicing`.
3. Review each result's name, team, Knox ID, SME area, and coverage.
4. Contact the SME whose coverage matches your need.

```text
🔍 SME Search Results (1)
Query: network slicing

1. Taylor Park (Network QA)
   Knox ID: taylor.park
   SME: 5G Network
   Coverage: 5G standalone and network slicing verification
   Matched on: network slicing, coverage:network, ...
```

## How Search Works

Each SME record has `keywords`, `sub_keywords`, an `sme` area, and a `coverage` description. The query is split into words and 2–4 word phrases, and every record is scored:

| Match | Points | Example |
| --- | --- | --- |
| Whole query phrase equals a keyword phrase | 5 | `network slicing` → `network slicing` |
| Query word equals a keyword | 5 | `gps` → `gps` |
| Single-word query appears as a word in a keyword phrase | 3 | `wifi` → `wifi calling` |
| Multi-word query partially contains a keyword (or vice versa) | 3 | `wifi calling issue` → `wifi calling` |
| Query term found in the SME area or coverage text | 2 | `location` → "Location accuracy …" |

- Generic words (`test`, `issue`, `feature`, `quality`, …) are never matched as keywords, so they don't flood the results.
- Results are sorted by score, then by name, so identical queries always return the same order.
- Optional team filter (case-insensitive) and result limit (`top_k`).
- **LLM fallback:** if keyword search finds nothing, an optional expander (Ollama in production) suggests related keywords and the search runs again. The expander is never called when keyword search already has results.
- Every search is recorded in a query log for search-quality review.

## API

`POST /api/find-sme`

```json
{
  "query": "wifi",
  "top_k": "all",
  "team_filter": null
}
```

| Field | Description |
| --- | --- |
| `query` | Required. Keyword or sentence; empty input returns 400 |
| `top_k` | `"all"` (default) or a positive integer / numeric string; invalid values return 422 |
| `team_filter` | Optional. Restrict the search to one team |

| Response field | Description |
| --- | --- |
| `total_count` | Number of candidates returned |
| `candidates` | `rank`, `name`, `team`, `knox_id`, `sme`, `coverage`, `score`, `match_reason` |
| `formatted_result` | Display-ready text for a single bot message |
| `candidate1_name` … `candidate10_coverage` | Flattened fields for bot platforms that cannot loop over arrays |
| `expanded_keywords` | Keywords added by the LLM fallback (empty if not used) |

Other endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/teams` | Team list |
| GET | `/api/sme-list` | SMEs grouped by team |
| GET | `/api/query-log` | Recent searches |

## Data

Mock records live in [`data/sme_data.json`](../mqlbot_demo/data/sme_data.json). The `coverage` field may contain `<br>` tags, as in the original spreadsheet source; they are stripped before matching and display.

## Troubleshooting

- **No results:** Try a shorter, more specific technical term, or remove the team filter.
- **Unexpected match:** Check `match_reason` to see which keyword or field produced the score.
