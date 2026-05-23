from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.alert_correlation import correlate_alerts

router = APIRouter()

class AlertsRequest(BaseModel):
    alerts: list[dict]

@router.post("/correlate")
async def correlate(req: AlertsRequest):
    try:
        return await correlate_alerts(req.alerts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
