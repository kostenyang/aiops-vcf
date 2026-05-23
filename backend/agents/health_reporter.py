"""Agent 3: Health Reporter — generate customer health report. READ_ONLY."""
import json
from core.harness import guardrail, AgentMode
from core.claude_client import client, MODEL

@guardrail(AgentMode.READ_ONLY)
async def generate_health_report(env_data: dict) -> str:
    response = await client.messages.create(
        model=MODEL, max_tokens=4096,
        messages=[{"role": "user", "content": f"""You are a VMware PSO consultant.
Write a monthly health report in Traditional Chinese (technical terms in English).
Sections: 執行摘要 / 基礎架構健康狀況 / 告警摘要 / 容量展望 / 建議事項 / 後續行動
Use markdown. Environment data:
{json.dumps(env_data, indent=2)}"""}],
    )
    return response.content[0].text
