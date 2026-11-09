from mqlbot_demo.text_utils import clean_html, truncate_text


def test_plain_text_is_returned_unchanged():
    assert clean_html("  no html here ") == "no html here"


def test_empty_input():
    assert clean_html(None) == "" and truncate_text("") == ""


def test_table_becomes_key_value_lines():
    html = "<table><tr><th>Item</th><th>Value</th></tr><tr><td>Rate</td><td>8/10</td></tr></table>"
    assert clean_html(html) == "- Rate: 8/10"


def test_paragraphs_breaks_and_lists_are_preserved():
    html = "<p><b>Symptom</b><br>Drops on roaming</p><ul><li>HDR only</li><li>Not 1080p</li></ul>"
    text = clean_html(html)
    assert "Symptom\nDrops on roaming" in text
    assert "- HDR only" in text and "- Not 1080p" in text


def test_kernel_timestamps_are_removed():
    assert truncate_text("[ 4935.358407] wlan0: deauth") == "wlan0: deauth"


def test_long_text_keeps_head_and_tail():
    text = "\n".join(f"line {i}" for i in range(300))
    result = truncate_text(text, max_lines=100).split("\n")
    assert result[0] == "line 0" and result[-1] == "line 299"
    assert "... (truncated) ..." in result
    assert len(result) == 101


def test_long_lines_are_capped():
    assert len(truncate_text("x" * 500, max_chars_per_line=200)) == 200
