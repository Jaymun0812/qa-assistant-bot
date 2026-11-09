"""Korean/English issue summaries.

Uses a local Ollama model when OLLAMA_SUMMARY_MODEL is set and reachable,
and falls back to a deterministic rule-based summary otherwise, so the demo
runs fully offline.
"""

from __future__ import annotations

import os
import re

import httpx

MIN_TEXT_LENGTH = 50
PLACEHOLDERS = {"", "n/a", "na", "-", "none", "tbd"}

PROMPT = """You are a QA engineer. Summarize the PLM issue below in {language}.
Use three short lines: Symptom, Cause, Countermeasure.
If cause or countermeasure is missing, write "Under analysis" (or "분석 중" in Korean).
Do not include company names.

Description: {text}
Cause: {cause}
Countermeasure: {countermeasure}"""


def _first_sentences(text: str, count: int = 2, max_chars: int = 300) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    summary = " ".join(sentences[:count])
    return summary if len(summary) <= max_chars else summary[: max_chars - 3] + "..."


def _value(text: str | None) -> str:
    return "" if (text or "").strip().lower() in PLACEHOLDERS else (text or "").strip()


def rule_based_summary(text: str, cause: str | None, countermeasure: str | None) -> tuple[str, str]:
    symptom = _first_sentences(text)
    cause_v, fix_v = _value(cause), _value(countermeasure)
    summary_ko = "\n".join([
        f"• 현상: {symptom}",
        f"• 원인: {cause_v or '분석 중'}",
        f"• 대책: {fix_v or '분석 중'}",
    ])
    summary_en = "\n".join([
        f"• Symptom: {symptom}",
        f"• Cause: {cause_v or 'Under analysis'}",
        f"• Countermeasure: {fix_v or 'Under analysis'}",
    ])
    return summary_ko, summary_en


async def _ollama(prompt: str, model: str, base_url: str) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{base_url}/api/generate", json={"model": model, "prompt": prompt, "stream": False})
        resp.raise_for_status()
        return resp.json().get("response", "").strip()


async def summarize(text: str, cause: str | None = None, countermeasure: str | None = None) -> dict:
    text = (text or "").strip()
    if len(text) < MIN_TEXT_LENGTH:
        return {
            "success": False, "summary_ko": "", "summary_en": "", "engine": "none",
            "error": f"text must be at least {MIN_TEXT_LENGTH} characters",
        }

    model = os.getenv("OLLAMA_SUMMARY_MODEL", "").strip()
    if model:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        fields = dict(text=text, cause=_value(cause) or "N/A", countermeasure=_value(countermeasure) or "N/A")
        try:
            summary_ko = await _ollama(PROMPT.format(language="Korean", **fields), model, base_url)
            summary_en = await _ollama(PROMPT.format(language="English", **fields), model, base_url)
            if summary_ko or summary_en:
                return {"success": True, "summary_ko": summary_ko, "summary_en": summary_en, "engine": f"ollama:{model}", "error": None}
        except httpx.HTTPError:
            pass  # fall back to the rule-based summary below

    summary_ko, summary_en = rule_based_summary(text, cause, countermeasure)
    return {"success": True, "summary_ko": summary_ko, "summary_en": summary_en, "engine": "rule-based", "error": None}
