#!/usr/bin/env bash
set -e
echo "=== AIOps VCF Setup ==="

echo "[1/2] Backend..."
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
test -f .env || cp .env.example .env && echo "  .env created — fill in your keys"
deactivate
cd ..

echo "[2/2] Frontend..."
cd frontend
npm install
test -f .env.local || cp .env.example .env.local
cd ..

echo ""
echo "Done! Next:"
echo "  1. Edit backend/.env with ANTHROPIC_API_KEY + VCF credentials"
echo "  2. cd backend && source .venv/bin/activate && uvicorn api.main:app --reload"
echo "  3. cd frontend && npm run dev"
