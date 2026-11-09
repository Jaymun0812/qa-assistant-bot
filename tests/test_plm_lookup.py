import asyncio

import pytest

from mqlbot_demo.plm_client import MockPLMClient, RateLimiter
from mqlbot_demo.plm_lookup import extract_issue_number, lookup_issue, normalize_issue


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("body, expected", [
    ({"issueNumber": " demo-000101 "}, "DEMO-000101"),
    ({"issue_number": "demo-1"}, "DEMO-1"),
    ({"defectCode": "demo-2"}, "DEMO-2"),
    ({"userInput": {"issueNumber": "demo-3"}}, "DEMO-3"),
    ({"issueNumber": "${issueNumber}"}, ""),
    ({}, ""),
])
def test_extract_issue_number(body, expected):
    assert extract_issue_number(body) == expected


def test_found_issue_has_card_fields_and_top_level_copy():
    result = run(lookup_issue(MockPLMClient(), "DEMO-000101"))
    out = result["output"]
    assert result["resultCode"] == "SUCCESS" and out["found"] is True
    assert result["plmTitle"] == out["plmTitle"]
    assert "Reproduction rate: 8/10" in out["description"]
    assert "[ 4935" not in out["description"]


def test_cause_and_countermeasure_fall_back_to_resolve_history():
    out = run(lookup_issue(MockPLMClient(), "DEMO-000101"))["output"]
    assert out["cause"].startswith("Roaming threshold")
    assert "hysteresis" in out["countermeasure"]


def test_latest_comment_is_chosen_by_date_not_order():
    detail = {"issueNumber": "X"}
    history = [
        {"action": "Comment", "date": "2026-11-01 09:00", "comment": "old", "user": "a"},
        {"action": "Comment", "date": "2026-11-05 09:00", "comment": "new", "user": "b"},
    ]
    assert normalize_issue(detail, history)["latestComment"].startswith("new")


def test_missing_cause_shows_under_analysis():
    out = run(lookup_issue(MockPLMClient(), "DEMO-000102"))["output"]
    assert out["cause"] == "Under analysis"


def test_not_found_returns_found_false_with_success_code():
    result = run(lookup_issue(MockPLMClient(), "DEMO-999999"))
    assert result["resultCode"] == "SUCCESS"
    assert result["output"]["found"] is False
    assert "plmTitle" not in result


def test_missing_input_returns_guidance_message():
    result = run(lookup_issue(MockPLMClient(), ""))
    assert result["output"] == {"found": False, "message": "Please enter a PLM issue number."}


def test_history_failure_degrades_to_detail_only():
    out = run(lookup_issue(MockPLMClient(), "DEMO-000103"))["output"]
    assert out["found"] is True
    assert out["warnings"] == ["History unavailable: History service timed out"]


def test_rate_limiter_waits_when_per_minute_budget_is_used():
    clock = {"t": 0.0}
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        clock["t"] += seconds

    limiter = RateLimiter(max_concurrent=3, max_per_minute=2, clock=lambda: clock["t"], sleep=fake_sleep)

    async def call():
        return "ok"

    async def scenario():
        return [await limiter.run(call) for _ in range(3)]

    assert run(scenario()) == ["ok"] * 3
    assert len(sleeps) == 1 and 59 < sleeps[0] <= 61


def test_rate_limiter_caps_concurrency():
    limiter = RateLimiter(max_concurrent=2, max_per_minute=100)
    active = {"now": 0, "peak": 0}

    async def call():
        active["now"] += 1
        active["peak"] = max(active["peak"], active["now"])
        await asyncio.sleep(0.01)
        active["now"] -= 1

    async def scenario():
        await asyncio.gather(*(limiter.run(call) for _ in range(6)))

    run(scenario())
    assert active["peak"] == 2


def test_one_lookup_makes_two_plm_calls():
    client = MockPLMClient()
    run(lookup_issue(client, "DEMO-000101"))
    assert client.call_count == 2
