# AGENTS.md — Harness Engineering Rules

## Agent modes

| Mode | Allowed | Approval needed |
|------|---------|----------------|
| READ_ONLY | Query APIs, analyze, report | No |
| ACTION | Execute runbooks, create tickets | Yes — human-in-the-loop |

## Guardrails

- Agents MUST NOT store credentials in prompts or logs
- Agents MUST NOT execute destructive operations autonomously
- All agent calls logged with input hash + output summary
- Change Risk score >= 70 → human sign-off required

## Tool access matrix

| Agent | VCF Ops | vCenter | NSX | ITSM write |
|-------|---------|---------|-----|------------|
| Alert Correlation | read | read | read | — |
| Change Risk | read | read | — | — |
| Health Reporter | read | read | read | — |
| Troubleshoot | read | read | read | approval |
| Capacity Planner | read | read | — | — |
