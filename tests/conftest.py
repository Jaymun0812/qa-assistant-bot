from datetime import datetime

import pytest

from mqlbot_demo.alerts import AlertConfig, Issue, Model

# A Tuesday inside the 08:00–10:59 Resolve alert window
NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture
def now():
    return NOW


@pytest.fixture
def sme_records():
    return [
        {"name": "Alex", "team": "Connectivity", "knox_id": "alex", "sme": "Wi-Fi",
         "keywords": "wifi, wifi calling", "sub_keywords": "hotspot", "coverage": "Wi-Fi feature verification"},
        {"name": "Blake", "team": "Network", "knox_id": "blake", "sme": "5G",
         "keywords": "network slicing, volte", "sub_keywords": "", "coverage": "5G SA verification"},
        {"name": "Casey", "team": "System", "knox_id": "casey", "sme": "GPS",
         "keywords": "gps, test", "sub_keywords": "", "coverage": "Location accuracy"},
    ]


@pytest.fixture
def dev_model():
    return Model(name="MDL-A100", stage_type="dev", status="active", pl_lead="lead.alpha")


@pytest.fixture
def config():
    return AlertConfig(extra_recipients_per_project={"MDL-A100": ["extra.one"]},
                       always_alarm_models=["MDL-E500"], excluded_folders_for_resolved=["Sandbox"])


def make_issue(**overrides):
    base = dict(number="DEMO-1", title="Sample", folder="MDL-A100_NA_DEV", priority="B", must_check="N",
                status="Open", created=NOW.replace(hour=7), creator="creator.one", resolved=None)
    base.update(overrides)
    return Issue(**base)
