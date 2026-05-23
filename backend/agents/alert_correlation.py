"""Agent 1: Alert Correlation — group noisy alerts, propose RCA. READ_ONLY."""
import json
from core.harness import guardrail, AgentMode
from core.claude_client import client, MODEL

@guardrail(AgentMode.READ_ONLY)
async def correlate_alerts(alerts: list[dict]) -> dict:
    response = await client.messages.create(
        model=MODEL, max_tokens=2048,
        messages=[{"role": "user", "content": f"""You are a VMware VCF operations expert.
Analyze these alerts and return JSON:
{{
  "incidents": [{{
    "id": "INC-001",
    "title": "...",
    "severity": "critical|high|medium|low",
    "alert_ids": [],
    "root_cause_hypothesis": "...",
    "next_steps": []
  }}]
}}
Alerts: {json.dumps(alerts, indent=2)}
Respond with valid JSON only."""}],
    )
    return json.loads(response.content[0].text)
