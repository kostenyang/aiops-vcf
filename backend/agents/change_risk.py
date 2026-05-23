"""Agent 2: Change Risk Scorer — score VCF upgrade/patch risk. READ_ONLY."""
import json
from core.harness import guardrail, AgentMode
from core.claude_client import client, MODEL

@guardrail(AgentMode.READ_ONLY)
async def score_change_risk(change: dict) -> dict:
    response = await client.messages.create(
        model=MODEL, max_tokens=2048,
        messages=[{"role": "user", "content": f"""You are a VMware VCF upgrade specialist.
Evaluate this change and return JSON:
{{
  "risk_score": 0-100,
  "risk_level": "low|medium|high|critical",
  "go_no_go": "go|no-go|conditional",
  "blockers": [],
  "checklist": [],
  "recommendation": "..."
}}
Change: {json.dumps(change, indent=2)}
Respond with valid JSON only."""}],
    )
    return json.loads(response.content[0].text)
