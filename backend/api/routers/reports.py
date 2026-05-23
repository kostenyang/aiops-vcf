from fastapi import APIRouter, HTTPException, Body
from typing import Any
from agents.health_reporter import generate_health_report

router = APIRouter()

@router.post("/generate")
async def generate(env_data: dict[str, Any] = Body(...)):
    try:
        report = await generate_health_report(env_data)
        return {"report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
