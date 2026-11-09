from mqlbot_demo.alerts.__main__ import main


def test_alert_demo_runs_end_to_end(tmp_path, capsys):
    main(["--now", "2026-11-10T09:00", "--state-dir", str(tmp_path), "--quiet"])
    out = capsys.readouterr().out
    assert "Cycle 1" in out and "Cycle 2" in out
    assert "PLM Reopened Issue" in out
    assert (tmp_path / "notified_issues.json").exists()
