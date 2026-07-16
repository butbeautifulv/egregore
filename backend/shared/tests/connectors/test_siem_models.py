from __future__ import annotations

import pytest

from connectors.siem_poll.models import SiemRawAlert, map_siem_severity, normalize_siem_alert


@pytest.mark.unit
def test_from_siem_record_splunk_style():
    alert = SiemRawAlert.from_siem_record(
        {
            "_id": "notable-1",
            "search_name": "Suspicious PowerShell",
            "urgency": "high",
            "description": "Encoded command detected",
            "dest": "ws-42",
            "sourcetype": "WinEventLog",
        }
    )
    assert alert.id == "notable-1"
    assert alert.rule_name == "Suspicious PowerShell"
    assert alert.host == "ws-42"


@pytest.mark.unit
def test_normalize_siem_alert_maps_security_event():
    alert = SiemRawAlert(
        id="a1",
        rule_name="Brute Force",
        severity="critical",
        message="Failed logins",
        host="dc-01",
    )
    event = normalize_siem_alert(alert, source="splunk")
    assert event.type == "siem.alert"
    assert event.source == "splunk"
    assert event.severity == "critical"
    assert event.payload["rule_name"] == "Brute Force"
    assert event.correlation_id == "a1"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("high", "high"),
        ("CRITICAL", "critical"),
        ("8", "critical"),
        ("unknown", "medium"),
    ],
)
def test_map_siem_severity(raw: str, expected: str):
    assert map_siem_severity(raw) == expected
