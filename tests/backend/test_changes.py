"""Tests for POST /api/changes/risk (Change Risk Scorer agent)."""
import pytest
from unittest.mock import AsyncMock, patch

CHANGE = {
    "title": "Upgrade VCF to 5.3",
    "type": "upgrade",
    "target": "VCF 5.2.1 → 5.3.0",
    "vcf_version": "5.2.1",
    "maintenance_window": "2026-06-01 02:00–04:00 UTC",
    "rollback_plan": "Snapshot all management VMs + restore previous bundle",
}

MOCK_GO = {
    "risk_score": 32,
    "risk_level": "low",
    "go_no_go": "go",
    "blockers": [],
    "checklist": [
        "Verify vSAN health is green",
        "Take snapshots of SDDC Manager and vCenter",
        "Notify stakeholders of maintenance window",
        "Run VCF pre-check bundle and confirm pass",
    ],
    "recommendation": "Low-risk upgrade. Proceed during scheduled maintenance window.",
}

MOCK_NO_GO = {
    "risk_score": 88,
    "risk_level": "critical",
    "go_no_go": "no-go",
    "blockers": [
        "vSAN health check failed — disk group rebuild in progress",
        "Unsupported NIC firmware version on esxi-03",
    ],
    "checklist": [],
    "recommendation": "Resolve all blockers before rescheduling upgrade.",
}

MOCK_CONDITIONAL = {
    "risk_score": 62,
    "risk_level": "medium",
    "go_no_go": "conditional",
    "blockers": [],
    "checklist": ["Extend maintenance window to 6 hours", "Confirm rollback snapshot is current"],
    "recommendation": "Proceed only if extended maintenance window is approved.",
}


@pytest.fixture
def mock_agent(make_response):
    with patch("agents.change_risk.client") as m:
        m.messages.create = AsyncMock(return_value=make_response(MOCK_GO))
        yield m


def test_risk_go_decision(client, mock_agent):
    r = client.post("/api/changes/risk", json=CHANGE)
    assert r.status_code == 200
    body = r.json()
    assert body["go_no_go"] == "go"
    assert isinstance(body["risk_score"], int)
    assert 0 <= body["risk_score"] <= 100
    assert body["risk_level"] in ("low", "medium", "high", "critical")
    assert isinstance(body["checklist"], list)
    assert isinstance(body["blockers"], list)
    assert "recommendation" in body


def test_risk_no_go_has_blockers(client, mock_agent, make_response):
    mock_agent.messages.create.return_value = make_response(MOCK_NO_GO)
    r = client.post("/api/changes/risk", json=CHANGE)
    assert r.status_code == 200
    body = r.json()
    assert body["go_no_go"] == "no-go"
    assert len(body["blockers"]) > 0
    assert body["risk_score"] >= 70


def test_risk_conditional(client, mock_agent, make_response):
    mock_agent.messages.create.return_value = make_response(MOCK_CONDITIONAL)
    r = client.post("/api/changes/risk", json=CHANGE)
    assert r.status_code == 200
    assert r.json()["go_no_go"] == "conditional"


def test_risk_calls_claude_once(client, mock_agent):
    client.post("/api/changes/risk", json=CHANGE)
    mock_agent.messages.create.assert_awaited_once()


def test_risk_no_body_returns_422(client):
    r = client.post("/api/changes/risk")
    assert r.status_code == 422


def test_risk_claude_bad_json_returns_500(client, make_response):
    with patch("agents.change_risk.client") as m:
        m.messages.create = AsyncMock(return_value=make_response("oops not json"))
        r = client.post("/api/changes/risk", json=CHANGE)
    assert r.status_code == 500
