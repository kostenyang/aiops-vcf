"""Agent 4: Troubleshoot — diagnose + suggest fix. READ_ONLY (diagnosis). ACTION (remediation)."""
import json
from core.harness import guardrail, AgentMode
from core.claude_client import client, MODEL

@guardrail(AgentMode.READ_ONLY)
async def diagnose(symptom: str, context: dict) -> dict:
    response = await client.messages.create(
        model=MODEL, max_tokens=2048,
        messages=[{"role": "user", "content": f"""You are a VMware VCF troubleshooting expert.
Symptom: {symptom}
Context: {json.dumps(context, indent=2)}
Return JSON:
{{
  "root_causes": [],
  "diagnostic_commands": [],
  "remediation_steps": [],
  "impact": "..."
}}
Respond with valid JSON only."""}],
    )
    return json.loads(response.content[0].text)
