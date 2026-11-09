# PLM Issue Lookup

[Back to overview](../README.md) · Implementation: [`plm_lookup.py`](../mqlbot_demo/plm_lookup.py), [`plm_client.py`](../mqlbot_demo/plm_client.py), [`summarizer.py`](../mqlbot_demo/summarizer.py), [`plm_api.py`](../mqlbot_demo/plm_api.py)

**Enter a PLM issue number to see its details and history, formatted for easy reading in the messenger.**

## User Flow

1. Open PLM Issue Lookup in the bot.
2. Enter the issue number (e.g. `DEMO-000101`).
3. Review the title, status, priority, description, cause, countermeasure, and latest comment.
4. Optionally request a Korean/English summary.

## How It Works

1. **Normalize input** — Trim whitespace, uppercase, and ignore unresolved bot template variables such as `${issueNumber}`.
2. **Fetch detail and history** — Two PLM calls per lookup, both through a rate limiter (3 concurrent calls, 20 calls per minute).
3. **Clean content** — HTML tables become `- key: value` lines, lists become bullets, kernel timestamps such as `[ 4935.358407]` are removed.
4. **Fill gaps from history** — If the detail record has no cause or countermeasure, the most recent Resolve entry in the history is used; otherwise the field shows "Under analysis".
5. **Truncate** — Description up to 100 lines; cause, countermeasure, and comment up to 50 lines each; long lines are capped.
6. **Shape the response** — Results go in `output` and are copied to the top level for bot variable binding.

If the history call fails, the lookup still returns the issue details with a `warnings` entry instead of failing.

| Section | Contents |
| --- | --- |
| Basic info | Issue number, title, status, priority, creator, registration time, model/folder |
| Description | Cleaned issue description |
| Cause / Countermeasure | From the detail record or the latest Resolve history entry |
| Latest Comment | Most recent comment by date, with author and time |
| Attachments | File names and sizes (metadata only) |

## API

`POST /api/aibuilder/issue-lookup` (GET with query parameters is also supported)

```json
{ "issueNumber": "DEMO-000101" }
```

`issueNumber`, `issue_number`, `defectCode`, and `userInput.issueNumber` are all accepted.

```json
{
  "version": "2.0",
  "resultCode": "SUCCESS",
  "output": {
    "found": true,
    "issueNumber": "DEMO-000101",
    "plmTitle": "[MDL-A100] Wi-Fi disconnects repeatedly when switching access points",
    "plmStatus": "Resolve",
    "priority": "A",
    "cause": "Roaming threshold was too aggressive after the driver update."
  }
}
```

| Case | Response |
| --- | --- |
| Found | `resultCode="SUCCESS"`, `output.found=true`, fields also copied to the top level |
| Not found | `resultCode="SUCCESS"`, `output.found=false`, guidance message |
| Missing input | `output.found=false`, "Please enter a PLM issue number." |
| PLM detail failure | `resultCode="ERROR"`, `output.found=false` |
| History failure | Found result with `output.warnings` |

Always branch on `output.found`; `resultCode="SUCCESS"` alone does not mean the issue exists.

### Korean / English Summary

`POST /api/aibuilder/ai-summary` is a separate call made after the lookup.

```json
{
  "text": "Wi-Fi drops every time the device roams between two access points on the same SSID.",
  "issue_number": "DEMO-000101",
  "cause": "Roaming threshold was too aggressive after the driver update.",
  "countermeasure": "N/A"
}
```

- `text` must be at least 50 characters after trimming; otherwise `success=false`.
- With `OLLAMA_SUMMARY_MODEL` set and Ollama running, a local LLM writes the summaries.
- Otherwise (or if Ollama is unreachable), a rule-based summary is returned: the first sentences as the symptom, plus cause and countermeasure, with "Under analysis" / "분석 중" for placeholders like `N/A`.
- The response contains `success`, `summary_ko`, `summary_en`, `engine` (`ollama:<model>` or `rule-based`), and `error`.

## Output App Card (Adaptive Card 1.3)

The lookup API returns **data, not card JSON**. In Knox AI Builder, bind the response fields to an output card:

| Card variable | Source field |
| --- | --- |
| `${issueNumber}` | `output.issueNumber` |
| `${plmTitle}` | `output.plmTitle` |
| `${plmStatus}` | `output.plmStatus` |
| `${priority}` | `output.priority` |
| `${createUserName}` / `${createUser}` | `output.createUserName` / `output.createUser` |
| `${regDate}` | `output.regDate` |
| `${refObjectName}` | `output.refObjectName` |
| `${description}` | `output.description` |
| `${cause}` / `${countermeasure}` | `output.cause` / `output.countermeasure` |
| `${latestComment}` | `output.latestComment` |

<details>
<summary>Expand output app card JSON</summary>

```json
{
  "type": "AdaptiveCard",
  "body": [
    { "type": "TextBlock", "text": "📌 ${issueNumber}", "size": "Large", "weight": "Bolder" },
    { "type": "TextBlock", "text": "${plmTitle}", "wrap": true, "size": "Default" },
    {
      "type": "ColumnSet",
      "columns": [
        { "type": "Column", "width": "auto", "items": [ { "type": "TextBlock", "text": "Status:", "size": "Small", "isSubtle": true } ] },
        { "type": "Column", "width": "stretch", "items": [ { "type": "TextBlock", "text": "${plmStatus}", "size": "Small", "color": "Good", "weight": "Bolder" } ] },
        { "type": "Column", "width": "auto", "items": [ { "type": "TextBlock", "text": "Priority:", "size": "Small", "isSubtle": true } ] },
        { "type": "Column", "width": "stretch", "items": [ { "type": "TextBlock", "text": "${priority}", "size": "Small", "weight": "Bolder" } ] }
      ]
    },
    {
      "type": "ColumnSet",
      "columns": [
        { "type": "Column", "width": "auto", "items": [ { "type": "TextBlock", "text": "Created by:", "size": "Small", "isSubtle": true } ] },
        { "type": "Column", "width": "stretch", "items": [ { "type": "TextBlock", "text": "${createUserName} (${createUser})", "size": "Small" } ] }
      ]
    },
    {
      "type": "ColumnSet",
      "columns": [
        { "type": "Column", "width": "auto", "items": [ { "type": "TextBlock", "text": "Registered:", "size": "Small", "isSubtle": true } ] },
        { "type": "Column", "width": "stretch", "items": [ { "type": "TextBlock", "text": "${regDate}", "size": "Small" } ] }
      ]
    },
    { "type": "TextBlock", "text": "📁 Model: ${refObjectName}", "size": "Small", "isSubtle": true, "spacing": "Small" },
    { "type": "TextBlock", "text": "📋 Description", "size": "Small", "weight": "Bolder", "spacing": "Medium" },
    { "type": "TextBlock", "text": "${description}", "wrap": true, "size": "Small" },
    { "type": "TextBlock", "text": "🔧 Countermeasure", "size": "Small", "weight": "Bolder", "spacing": "Medium" },
    { "type": "TextBlock", "text": "${countermeasure}", "wrap": true, "size": "Small" },
    { "type": "TextBlock", "text": "🔍 Cause", "size": "Small", "weight": "Bolder", "spacing": "Medium" },
    { "type": "TextBlock", "text": "${cause}", "wrap": true, "size": "Small" },
    { "type": "TextBlock", "text": "💬 Latest Comment", "size": "Small", "weight": "Bolder", "spacing": "Medium" },
    { "type": "TextBlock", "text": "${latestComment}", "wrap": true, "size": "Small" }
  ],
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "version": "1.3"
}
```

</details>

## Mock Issues

| Issue | Demonstrates |
| --- | --- |
| `DEMO-000101` | HTML table cleanup, kernel log removal, cause/countermeasure from Resolve history, attachments |
| `DEMO-000102` | Open issue with cause still under analysis |
| `DEMO-000103` | History service failure → detail-only result with a warning |
| `DEMO-999999` | Not found |

Data: [`data/plm_issues.json`](../mqlbot_demo/data/plm_issues.json).
