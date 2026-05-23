# AIOps for VCF

AI-powered operations platform for VMware Cloud Foundation.

## Agents

| Agent | Purpose | Mode |
|-------|---------|------|
| Alert Correlation | Group noisy alerts, RCA | Read-only |
| Change Risk Scorer | VCF upgrade risk scoring | Read-only |
| Health Reporter | Auto customer reports | Read-only |
| Troubleshoot Agent | Diagnose + suggest fix | Read-only → Action (approval) |
| Capacity Planner | Forecast + right-sizing | Read-only |

## Quick Start

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn api.main:app --reload

# Frontend
cd frontend && npm install && cp .env.example .env.local && npm run dev
```

## Setup

```bash
bash scripts/setup.sh
```
