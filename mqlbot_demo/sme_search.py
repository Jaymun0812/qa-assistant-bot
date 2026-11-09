"""Keyword-scored SME search, ported from the production SME Finder.

Scoring rules
-------------
* Exact match of a whole query phrase to a registered keyword phrase: 5 points
* Single-word query found as a word inside a keyword phrase: 3 points
* Multi-word query partially contained in a keyword phrase (or vice versa): 3 points
* Query term or phrase found in the SME area or coverage text: 2 points
Generic words such as "test" or "issue" are never matched as keywords.
"""

from __future__ import annotations

import re
from typing import Iterable

EXCLUDED_KEYWORDS = {
    "test", "tests", "testing", "issue", "issues", "management", "manage",
    "feature", "features", "analysis", "analyze", "execution", "execute",
    "support", "supports", "development", "develop", "operation", "operations",
    "platform", "systems", "strategy", "request", "requests", "lead", "leads",
    "presentation", "evaluation", "trend", "quality",
}

EXACT_MATCH = 5
WORD_MATCH = 3
FIELD_MATCH = 2
MAX_FLATTENED = 10


def _words(text: str) -> list[str]:
    cleaned = re.sub(r"[\[\]()#]", " ", text.lower())
    seen: list[str] = []
    for w in cleaned.split():
        if len(w) >= 2 and w not in seen:
            seen.append(w)
    return seen


def _phrases(words: list[str]) -> list[str]:
    return [" ".join(words[i:j]) for i in range(len(words)) for j in range(i + 2, min(i + 5, len(words) + 1))]


def _strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    return re.sub(r"<[^>]+>", "", text)


def _keyword_phrases(sme: dict) -> list[str]:
    combined = ",".join(filter(None, [sme.get("keywords", ""), sme.get("sub_keywords", "")]))
    return [k.strip().lower() for k in combined.split(",") if k.strip() and k.strip().lower() not in EXCLUDED_KEYWORDS]


def score_sme(query: str, sme: dict, expanded_keywords: Iterable[str] | None = None) -> tuple[int, list[str]]:
    """Return (score, matched reasons) for one SME record."""
    words = _words(query)
    phrases = _phrases(words)
    for kw in expanded_keywords or []:
        kw = kw.lower().strip()
        if kw and kw not in words:
            words.append(kw)
        if " " in kw and kw not in phrases:
            phrases.append(kw)

    score = 0
    matched: list[str] = []

    def hit(points: int, reason: str) -> None:
        nonlocal score
        score += points
        if reason not in matched:
            matched.append(reason)

    keyword_phrases = _keyword_phrases(sme)
    for phrase in phrases:
        for kw in keyword_phrases:
            if phrase == kw:
                hit(EXACT_MATCH, kw)

    multi_word_query = len(words) > 1
    for word in words:
        for kw in keyword_phrases:
            if kw == word:
                hit(EXACT_MATCH, kw)
            elif not multi_word_query and word in kw.split():
                hit(WORD_MATCH, kw)
            elif multi_word_query and len(word) >= 3 and len(kw) >= 3 and (word in kw or kw in word):
                hit(WORD_MATCH, kw)

    coverage = _strip_html(sme.get("coverage", "") or "").lower()
    area = (sme.get("sme", "") or "").lower()
    for term in words + phrases:
        if len(term) < 3:
            continue
        if term in coverage:
            hit(FIELD_MATCH, f"coverage:{term}")
        if term in area:
            hit(FIELD_MATCH, f"sme:{term}")

    return score, matched


def parse_top_k(value: str | int | None) -> int | None:
    """"all" / None → no limit; positive integers (or numeric strings) → limit."""
    if value is None or (isinstance(value, str) and value.strip().lower() in ("", "all")):
        return None
    number = int(value)
    if number <= 0:
        raise ValueError("top_k must be a positive integer or 'all'")
    return number


def search(
    query: str,
    sme_list: list[dict],
    top_k: str | int | None = "all",
    team_filter: str | None = None,
    expanded_keywords: Iterable[str] | None = None,
) -> list[dict]:
    """Rank SMEs for a query. Ties are broken by name for stable output."""
    limit = parse_top_k(top_k)
    expanded = list(expanded_keywords or [])
    scored = []
    for sme in sme_list:
        if team_filter and sme.get("team", "").lower() != team_filter.lower():
            continue
        score, matched = score_sme(query, sme, expanded)
        if score > 0:
            scored.append((score, sme, matched))
    scored.sort(key=lambda item: (-item[0], item[1].get("name", "")))
    if limit is not None:
        scored = scored[:limit]
    return [
        {
            "rank": rank,
            "name": sme.get("name", ""),
            "team": sme.get("team", ""),
            "knox_id": sme.get("knox_id", ""),
            "sme": sme.get("sme", ""),
            "coverage": _strip_html(sme.get("coverage", "")),
            "score": score,
            "match_reason": ", ".join(matched),
        }
        for rank, (score, sme, matched) in enumerate(scored, start=1)
    ]


def format_result(query: str, candidates: list[dict]) -> str:
    if not candidates:
        return f"🔍 No SME found for '{query}'.\nTry a shorter technical keyword or a different team filter."
    lines = [f"🔍 SME Search Results ({len(candidates)})", f"Query: {query}", ""]
    for c in candidates:
        lines += [
            f"{c['rank']}. {c['name']} ({c['team']})",
            f"   Knox ID: {c['knox_id']}",
            f"   SME: {c['sme']}",
            f"   Coverage: {c['coverage']}",
            f"   Matched on: {c['match_reason']}",
            "",
        ]
    return "\n".join(lines).rstrip()


def flatten_candidates(candidates: list[dict], size: int = MAX_FLATTENED) -> dict:
    """Bot platforms that cannot loop over arrays read candidate1_name … candidate10_name."""
    flat = {}
    for i in range(size):
        c = candidates[i] if i < len(candidates) else {}
        for field in ("name", "team", "knox_id", "sme", "coverage"):
            flat[f"candidate{i + 1}_{field}"] = c.get(field, "")
    return flat
