from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agents.troubleshoot import diagnose

router = APIRouter()

class DiagnoseRequest(BaseModel):
    symptom: str
    context: dict = {}

@router.post("/diagnose")
async def run_diagnose(req: DiagnoseRequest):
    try:
        return await diagnose(req.symptom, req.context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
