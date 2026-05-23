from fastapi import APIRouter, HTTPException, Body
from typing import Any
from agents.change_risk import score_change_risk

router = APIRouter()

@router.post("/risk")
async def risk(change: dict[str, Any] = Body(...)):
    try:
        return await score_change_risk(change)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
