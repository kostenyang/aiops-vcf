"""Tests for POST /api/alerts/correlate (Alert Correlation agent)."""
import pytest
from unittest.mock import AsyncMock, patch

ALERTS = [
    {"id": "ALT-001", "name": "vSAN disk degraded", "severity": "critical", "host": "esxi-01"},
    {"id": "ALT-002", "name": "CPU usage > 90%",    "severity": "high",     "host": "esxi-01"},
    {"id": "ALT-003", "name": "NFS latency high",   "severity": "medium",   "host": "esxi-02"},
]

MOCK_INCIDENTS = {
    "incidents": [{
        "id": "INC-001",
        "title": "vSAN Storage Degradation on esxi-01",
        "severity": "critical",
        "alert_ids": ["ALT-001", "ALT-002"],
        "root_cause_hypothesis": "Physical disk failure triggering vSAN rebuild and elevated CPU",
        "next_steps": [
            "Run esxcli storage core device list on esxi-01",
            "Check vSAN disk group health",
            "Replace failed disk and monitor resync progress",
        ],
    }]
}


@pytest.fixture
def mock_agent(make_response):
    with patch("agents.alert_correlation.client") as m:
        m.messages.create = AsyncMock(return_value=make_response(MOCK_INCIDENTS))
        yield m


def test_correlate_returns_incidents(client, mock_agent):
    r = client.post("/api/alerts/correlate", json={"alerts": ALERTS})
    assert r.status_code == 200
    body = r.json()
    assert "incidents" in body
    inc = body["incidents"][0]
    assert "id" in inc
    assert "title" in inc
    assert inc["severity"] in ("critical", "high", "medium", "low")
    assert isinstance(inc["next_steps"], list)


def test_correlate_calls_claude_with_alerts(client, mock_agent):
    client.post("/api/alerts/correlate", json={"alerts": ALERTS})
    mock_agent.messages.create.assert_awaited_once()


def test_correlate_empty_alerts(client, mock_agent, make_response):
    mock_agent.messages.create.return_value = make_response({"incidents": []})
    r = client.post("/api/alerts/correlate", json={"alerts": []})
    assert r.status_code == 200
    assert r.json()["incidents"] == []


def test_correlate_missing_alerts_key_returns_422(client):
    r = client.post("/api/alerts/correlate", json={"wrong_key": []})
    assert r.status_code == 422


def test_correlate_no_body_returns_422(client):
    r = client.post("/api/alerts/correlate")
    assert r.status_code == 422


def test_correlate_claude_returns_bad_json_gives_500(client, make_response):
    with patch("agents.alert_correlation.client") as m:
        m.messages.create = AsyncMock(return_value=make_response("not {{ valid json"))
        r = client.post("/api/alerts/correlate", json={"alerts": ALERTS})
    assert r.status_code == 500
