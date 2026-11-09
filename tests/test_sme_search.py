import pytest

from mqlbot_demo.sme_search import flatten_candidates, format_result, parse_top_k, score_sme, search


def names(results):
    return [r["name"] for r in results]


def test_single_word_matches_word_inside_keyword_phrase(sme_records):
    results = search("wifi", sme_records)
    assert names(results) == ["Alex"]
    assert "wifi calling" in results[0]["match_reason"]


def test_exact_phrase_scores_higher_than_partial_word(sme_records):
    exact, _ = score_sme("network slicing", sme_records[1])
    partial, _ = score_sme("network", sme_records[1])
    assert exact > partial > 0


def test_generic_keywords_are_never_matched(sme_records):
    assert search("test", sme_records) == []


def test_coverage_text_contributes_to_score(sme_records):
    results = search("location", sme_records)
    assert names(results) == ["Casey"]
    assert results[0]["match_reason"] == "coverage:location"


def test_query_is_case_and_bracket_insensitive(sme_records):
    assert names(search("[WiFi]", sme_records)) == ["Alex"]


def test_team_filter_limits_scope(sme_records):
    assert search("wifi", sme_records, team_filter="Network") == []
    assert names(search("wifi", sme_records, team_filter="connectivity")) == ["Alex"]


def test_top_k_limits_results_and_ranks_are_sequential(sme_records):
    records = sme_records + [dict(sme_records[0], name="Aaron", knox_id="aaron")]
    results = search("wifi", records, top_k=1)
    assert len(results) == 1 and results[0]["rank"] == 1
    assert [r["rank"] for r in search("wifi", records)] == [1, 2]


def test_ties_are_broken_by_name(sme_records):
    records = [dict(sme_records[0], name="Zed"), dict(sme_records[0], name="Amy")]
    assert names(search("wifi", records)) == ["Amy", "Zed"]


def test_expanded_keywords_enable_fallback_match(sme_records):
    assert search("wlan", sme_records) == []
    assert names(search("wlan", sme_records, expanded_keywords=["wifi"])) == ["Alex"]


@pytest.mark.parametrize("value, expected", [("all", None), (None, None), ("", None), (3, 3), ("5", 5)])
def test_parse_top_k_valid(value, expected):
    assert parse_top_k(value) == expected


@pytest.mark.parametrize("value", [0, -1, "abc"])
def test_parse_top_k_invalid(value):
    with pytest.raises(ValueError):
        parse_top_k(value)


def test_flattened_fields_always_have_ten_slots(sme_records):
    flat = flatten_candidates(search("wifi", sme_records))
    assert flat["candidate1_name"] == "Alex"
    assert flat["candidate10_name"] == ""
    assert len([k for k in flat if k.endswith("_name")]) == 10


def test_format_result_handles_no_results():
    assert "No SME found" in format_result("xyz", [])
