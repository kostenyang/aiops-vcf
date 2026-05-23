"""Agent 5: Capacity Planner — forecast & right-sizing. READ_ONLY."""
import json
from core.harness import guardrail, AgentMode
from core.claude_client import client, MODEL

@guardrail(AgentMode.READ_ONLY)
async def plan_capacity(metrics: dict) -> dict:
    response = await client.messages.create(
        model=MODEL, max_tokens=2048,
        messages=[{"role": "user", "content": f"""You are a vSAN ESA capacity planning specialist.
Metrics: {json.dumps(metrics, indent=2)}
Return JSON with keys: forecast_90d, rightsizing, expansion_triggers, procurement_timeline.
Respond with valid JSON only."""}],
    )
    return json.loads(response.content[0].text)
