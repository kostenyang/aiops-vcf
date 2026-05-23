from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.capacity_planner import plan_capacity

router = APIRouter()

class CapacityRequest(BaseModel):
    metrics: dict

@router.post("/plan")
async def plan(req: CapacityRequest):
    try:
        return await plan_capacity(req.metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
