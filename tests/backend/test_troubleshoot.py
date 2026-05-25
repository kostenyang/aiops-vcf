"""Tests for POST /api/troubleshoot/diagnose (Troubleshoot agent)."""
import pytest
from unittest.mock import AsyncMock, patch

SYMPTOM = "vSAN datastore showing as inaccessible on all hosts in cluster"
CONTEXT = {
    "cluster": "vcf-prod-cl01",
    "vcf_version": "5.2.1",
    "affected_hosts": ["esxi-01", "esxi-02", "esxi-03"],
    "error_code": "VSAN_HEALTH_ERROR",
    "last_change": "Network switch firmware update 2 hours ago",
}

MOCK_DIAGNOSIS = {
    "root_causes": [
        "vSAN witness appliance lost network connectivity after switch firmware update",
        "Split-brain scenario — hosts cannot reach witness, vSAN entered read-only mode",
    ],
    "diagnostic_commands": [
        "esxcli vsan cluster get",
        "esxcli vsan network list",
        "ping <witness-ip> from ESXi management VMkernel",
        "esxcli network ip interface list",
    ],
    "remediation_steps": [
        "Verify witness appliance VM is powered on and reachable",
        "Check vSAN VMkernel adapter MTU — ensure jumbo frames match switch config",
        "If network is healthy, restart vSAN management service: /etc/init.d/vsanmgmtd restart",
        "Monitor vSAN resync progress after connectivity restored",
    ],
    "impact": "All VMs on vSAN datastore are inaccessible. Production workload fully affected.",
}


@pytest.fixture
def mock_agent(make_response):
    with patch("agents.troubleshoot.client") as m:
        m.messages.create = AsyncMock(return_value=make_response(MOCK_DIAGNOSIS))
        yield m


def test_diagnose_returns_all_fields(client, mock_agent):
    r = client.post("/api/troubleshoot/diagnose", json={"symptom": SYMPTOM, "context": CONTEXT})
    assert r.status_code == 200
    body = r.json()
    assert "root_causes" in body
    assert "diagnostic_commands" in body
    assert "remediation_steps" in body
    assert "impact" in body
    assert isinstance(body["root_causes"], list)
    assert len(body["root_causes"]) > 0


def test_diagnose_calls_claude_once(client, mock_agent):
    client.post("/api/troubleshoot/diagnose", json={"symptom": SYMPTOM, "context": CONTEXT})
    mock_agent.messages.create.assert_awaited_once()


def test_diagnose_without_context_uses_default(client, mock_agent):
    """context field has a default of {} — omitting it should still work."""
    r = client.post("/api/troubleshoot/diagnose", json={"symptom": SYMPTOM})
    assert r.status_code == 200


def test_diagnose_empty_context(client, mock_agent):
    r = client.post("/api/troubleshoot/diagnose", json={"symptom": SYMPTOM, "context": {}})
    assert r.status_code == 200


def test_diagnose_missing_symptom_returns_422(client):
    r = client.post("/api/troubleshoot/diagnose", json={"context": CONTEXT})
    assert r.status_code == 422


def test_diagnose_no_body_returns_422(client):
    r = client.post("/api/troubleshoot/diagnose")
    assert r.status_code == 422


def test_diagnose_claude_bad_json_returns_500(client, make_response):
    with patch("agents.troubleshoot.client") as m:
        m.messages.create = AsyncMock(return_value=make_response("not json at all"))
        r = client.post("/api/troubleshoot/diagnose", json={"symptom": SYMPTOM})
    assert r.status_code == 500
