"""PLM issue lookup: fetch, normalize, and shape results for AI Builder."""

from __future__ import annotations

import re

from .plm_client import MockPLMClient, PLMError
from .text_utils import clean_html, truncate_text

RESPONSE_VERSION = "2.0"
DESCRIPTION_MAX_LINES = 100
SECTION_MAX_LINES = 50
TEMPLATE_VARIABLE = re.compile(r"^\$\{[^}]*\}$|^\{\{[^}]*\}\}$")
INPUT_ALIASES = ("issueNumber", "issue_number", "defectCode")


def normalize_issue_number(value: str | None) -> str:
    """Trim, uppercase, and drop unresolved bot template variables like ${issueNumber}."""
    value = (value or "").strip()
    if TEMPLATE_VARIABLE.match(value):
        return ""
    return value.upper()


def extract_issue_number(body: dict) -> str:
    """Accept issueNumber, issue_number, defectCode, or userInput.issueNumber."""
    for key in INPUT_ALIASES:
        if body.get(key):
            return normalize_issue_number(str(body[key]))
    user_input = body.get("userInput")
    if isinstance(user_input, dict):
        return normalize_issue_number(str(user_input.get("issueNumber", "")))
    return ""


def _latest(history: list[dict], action: str) -> dict:
    entries = [h for h in history if h.get("action") == action]
    return max(entries, key=lambda h: h.get("date", ""), default={})


def format_attachments(attachments: list[dict]) -> str:
    lines = []
    for a in attachments:
        size_mb = a.get("fileSize", 0) / 1_000_000
        lines.append(f"📎 {a.get('fileName', '')} ({size_mb:.1f} MB)")
    return "\n".join(lines)


def normalize_issue(detail: dict, history: list[dict]) -> dict:
    """Merge detail + history into the flat structure bound to the output card.

    Cause and countermeasure fall back to the most recent Resolve entry in the
    history when the detail record does not contain them.
    """
    resolve = _latest(history, "Resolve")
    comment = _latest(history, "Comment")
    cause = detail.get("cause") or resolve.get("cause", "")
    countermeasure = detail.get("countermeasure") or resolve.get("countermeasure", "")
    latest_comment = (
        f"{comment['comment']} — {comment.get('user', '')} ({comment.get('date', '')})" if comment else ""
    )
    attachments = detail.get("attachments", [])
    return {
        "found": True,
        "issueNumber": detail.get("issueNumber", ""),
        "plmTitle": detail.get("title", ""),
        "plmStatus": detail.get("status", ""),
        "priority": detail.get("priority", ""),
        "createUser": detail.get("createUser", ""),
        "createUserName": detail.get("createUserName", ""),
        "regDate": detail.get("regDate", ""),
        "refObjectName": detail.get("folder", ""),
        "description": truncate_text(clean_html(detail.get("description_html", "")), DESCRIPTION_MAX_LINES),
        "cause": truncate_text(clean_html(cause), SECTION_MAX_LINES) or "Under analysis",
        "countermeasure": truncate_text(clean_html(countermeasure), SECTION_MAX_LINES) or "Under analysis",
        "latestComment": truncate_text(latest_comment, SECTION_MAX_LINES),
        "attachments": attachments,
        "attachmentsText": format_attachments(attachments),
    }


def _response(output: dict, result_code: str = "SUCCESS", copy_to_top_level: bool = False) -> dict:
    response = {"version": RESPONSE_VERSION, "resultCode": result_code, "output": output}
    if copy_to_top_level:
        response.update({k: v for k, v in output.items() if k not in response})
    return response


async def lookup_issue(client: MockPLMClient, issue_number: str) -> dict:
    """Look up one issue. History failures degrade gracefully to detail-only results."""
    if not issue_number:
        return _response({"found": False, "message": "Please enter a PLM issue number."})

    try:
        detail = await client.get_detail(issue_number)
    except PLMError as exc:
        return _response({"found": False, "message": f"PLM lookup failed: {exc}"}, result_code="ERROR")
    if not detail:
        return _response({
            "found": False,
            "issueNumber": issue_number,
            "message": f"Issue {issue_number} was not found. Please check the number.",
        })

    warnings = []
    try:
        history = await client.get_history(issue_number)
    except PLMError as exc:
        history = []
        warnings.append(f"History unavailable: {exc}")

    output = normalize_issue(detail, history)
    if warnings:
        output["warnings"] = warnings
    return _response(output, copy_to_top_level=True)
