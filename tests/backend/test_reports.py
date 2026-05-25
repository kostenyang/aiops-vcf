"""Tests for POST /api/reports/generate (Health Reporter agent)."""
import pytest
from unittest.mock import AsyncMock, patch

ENV_DATA = {
    "customer": "ACME Corp",
    "period": "2026-05",
    "vcf_version": "5.2.1",
    "cluster_count": 3,
    "host_count": 12,
    "vm_count": 340,
    "alerts_this_month": 47,
    "critical_alerts": 2,
    "cpu_utilization_avg": 68,
    "memory_utilization_avg": 72,
    "vsan_capacity_used_pct": 61,
}

MOCK_REPORT = """\
# VCF 月度健康報告 — ACME Corp（2026-05）

## 執行摘要
本月基礎架構整體運行穩定，共產生 47 個告警，其中 2 個屬嚴重等級，均已妥善處理。

## 基礎架構健康狀況
- **vCenter**：正常運行，無重大事件
- **vSAN**：容量使用率 61%，健康狀態良好
- **NSX**：網路平面運行正常

## 告警摘要
| 等級 | 數量 |
|------|------|
| Critical | 2 |
| High | 8 |
| Medium | 37 |

## 容量展望
依現有成長速率估計，vSAN 容量將於 90 天後達到 72%，建議規劃擴充。

## 建議事項
1. 評估 vSAN 節點擴充計畫
2. 複查 Critical 告警根因，確認已完全修復

## 後續行動
| 行動項目 | 負責人 | 預計完成日 |
|----------|--------|------------|
| vSAN 容量規劃會議 | 維運團隊 | 2026-06-15 |
"""


@pytest.fixture
def mock_agent(make_response):
    with patch("agents.health_reporter.client") as m:
        m.messages.create = AsyncMock(return_value=make_response(MOCK_REPORT))
        yield m


def test_generate_returns_report_string(client, mock_agent):
    r = client.post("/api/reports/generate", json=ENV_DATA)
    assert r.status_code == 200
    body = r.json()
    assert "report" in body
    assert isinstance(body["report"], str)
    assert len(body["report"]) > 0


def test_generate_report_contains_markdown(client, mock_agent):
    r = client.post("/api/reports/generate", json=ENV_DATA)
    assert r.status_code == 200
    # Report should be markdown (has headings)
    assert "#" in r.json()["report"]


def test_generate_calls_claude_once(client, mock_agent):
    client.post("/api/reports/generate", json=ENV_DATA)
    mock_agent.messages.create.assert_awaited_once()


def test_generate_minimal_env_data(client, mock_agent):
    """Endpoint should accept any dict — even a minimal one."""
    r = client.post("/api/reports/generate", json={"customer": "Test", "period": "2026-05"})
    assert r.status_code == 200


def test_generate_no_body_returns_422(client):
    r = client.post("/api/reports/generate")
    assert r.status_code == 422
