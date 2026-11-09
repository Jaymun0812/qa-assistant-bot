"""Text cleanup helpers for turning PLM HTML into messenger-friendly text."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

KERNEL_TIMESTAMP = re.compile(r"\[\s*\d+\.\d+\]\s*")


def _table_to_lines(table) -> list[str]:
    rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    header, *body = rows
    if not body:
        return [" | ".join(header)]
    lines = []
    for row in body:
        if len(row) == 2 and len(header) == 2:
            lines.append(f"- {row[0]}: {row[1]}")
        else:
            pairs = [f"{h}: {v}" for h, v in zip(header, row) if v]
            lines.append("- " + ", ".join(pairs))
    return lines


def clean_html(html: str | None) -> str:
    """Convert PLM rich-text HTML into readable plain text.

    Tables become "- key: value" lines, list items become bullets, and
    blank lines are collapsed so the result fits a messenger card.
    """
    if not html:
        return ""
    if "<" not in html:
        return html.strip()

    soup = BeautifulSoup(html, "html.parser")
    table_lines: list[str] = []
    for table in soup.find_all("table"):
        table_lines.extend(_table_to_lines(table))
        table.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for block in soup.find_all(["p", "div"]):
        block.insert_after("\n")

    lines: list[str] = []
    for raw in soup.get_text().split("\n"):
        line = raw.strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()

    parts = ["\n".join(lines)] if lines else []
    if table_lines:
        parts.append("\n".join(table_lines))
    return "\n\n".join(parts)


def truncate_text(text: str, max_lines: int = 100, max_chars_per_line: int = 200) -> str:
    """Shorten long logs: drop kernel timestamps, keep head and tail lines, cap line length."""
    if not text:
        return ""
    text = KERNEL_TIMESTAMP.sub("", text)
    lines = text.split("\n")
    if len(lines) > max_lines:
        half = max_lines // 2
        lines = lines[:half] + ["... (truncated) ..."] + lines[-half:]
    return "\n".join(
        line if len(line) <= max_chars_per_line else line[: max_chars_per_line - 3] + "..."
        for line in lines
    )
