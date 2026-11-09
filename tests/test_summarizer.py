import asyncio

from mqlbot_demo.summarizer import MIN_TEXT_LENGTH, rule_based_summary, summarize

TEXT = "Wi-Fi drops every time the device roams between two access points. It recovers after 5 seconds. Logs attached."


def test_short_text_is_rejected():
    result = asyncio.run(summarize("too short"))
    assert result["success"] is False and str(MIN_TEXT_LENGTH) in result["error"]


def test_whitespace_does_not_count_toward_minimum():
    assert asyncio.run(summarize(" " * 100 + "short"))["success"] is False


def test_rule_based_fallback_when_no_llm(monkeypatch):
    monkeypatch.delenv("OLLAMA_SUMMARY_MODEL", raising=False)
    result = asyncio.run(summarize(TEXT, "Roaming threshold too aggressive", "N/A"))
    assert result["success"] and result["engine"] == "rule-based"
    assert "Cause: Roaming threshold too aggressive" in result["summary_en"]
    assert "Countermeasure: Under analysis" in result["summary_en"]
    assert "대책: 분석 중" in result["summary_ko"]


def test_unreachable_llm_falls_back(monkeypatch):
    monkeypatch.setenv("OLLAMA_SUMMARY_MODEL", "llama3.2")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    assert asyncio.run(summarize(TEXT))["engine"] == "rule-based"


def test_symptom_uses_first_two_sentences():
    _, en = rule_based_summary(TEXT, None, None)
    assert "Logs attached" not in en and "recovers after 5 seconds" in en
