"""Tests for POST /api/capacity/plan (Capacity Planner agent)."""
import pytest
from unittest.mock import AsyncMock, patch

METRICS = {
    "cluster": "vcf-prod-cl01",
    "vsan_capacity_tb": 100,
    "vsan_used_tb": 61,
    "vsan_growth_rate_tb_per_month": 3.5,
    "host_count": 12,
    "cpu_utilization_avg_pct": 68,
    "memory_utilization_avg_pct": 72,
}

MOCK_PLAN = {
    "forecast_90d": {
        "vsan_used_tb": 71.5,
        "vsan_utilization_pct": 71.5,
        "risk": "low",
        "note": "Utilization remains below 80% threshold for 90 days",
    },
    "rightsizing": [
        "10 VMs are CPU-constrained (<2 vCPU, >90% utilization) — recommend increasing vCPU",
        "5 VMs show memory balloon >20% — recommend increasing memory allocation",
        "3 VMs idle >30 days — candidates for decommission",
    ],
    "expansion_triggers": [
        "vSAN utilization reaching 80% — estimated in ~55 days at current growth rate",
        "CPU cluster utilization approaching 85% — monitor closely",
    ],
    "procurement_timeline": {
        "recommended_action": "Order 2 additional ESXi hosts within 30 days",
        "lead_time_weeks": 8,
        "target_deployment": "2026-09-01",
        "estimated_cost_usd": 120000,
    },
}


@pytest.fixture
def mock_agent(make_response):
    with patch("agents.capacity_planner.client") as m:
        m.messages.create = AsyncMock(return_value=make_response(MOCK_PLAN))
        yield m


def test_plan_returns_all_sections(client, mock_agent):
    r = client.post("/api/capacity/plan", json={"metrics": METRICS})
    assert r.status_code == 200
    body = r.json()
    assert "forecast_90d" in body
    assert "rightsizing" in body
    assert "expansion_triggers" in body
    assert "procurement_timeline" in body


def test_plan_forecast_structure(client, mock_agent):
    r = client.post("/api/capacity/plan", json={"metrics": METRICS})
    forecast = r.json()["forecast_90d"]
    assert "vsan_utilization_pct" in forecast
    assert "risk" in forecast


def test_plan_rightsizing_is_list(client, mock_agent):
    r = client.post("/api/capacity/plan", json={"metrics": METRICS})
    assert isinstance(r.json()["rightsizing"], list)


def test_plan_calls_claude_once(client, mock_agent):
    client.post("/api/capacity/plan", json={"metrics": METRICS})
    mock_agent.messages.create.assert_awaited_once()


def test_plan_missing_metrics_key_returns_422(client):
    r = client.post("/api/capacity/plan", json={"wrong": {}})
    assert r.status_code == 422


def test_plan_no_body_returns_422(client):
    r = client.post("/api/capacity/plan")
    assert r.status_code == 422


def test_plan_claude_bad_json_returns_500(client, make_response):
    with patch("agents.capacity_planner.client") as m:
        m.messages.create = AsyncMock(return_value=make_response("{{broken"))
        r = client.post("/api/capacity/plan", json={"metrics": METRICS})
    assert r.status_code == 500
