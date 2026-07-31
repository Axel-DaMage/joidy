import httpx
from config import settings
from fastapi import APIRouter, HTTPException
from middleware.correlation_id import get_correlation_id
from pydantic import BaseModel

router = APIRouter(prefix="/ai", tags=["ai"])

class ClassifyRequest(BaseModel):
    note_id: int
    content: str
    existing_tags: list[str] = []

@router.post("/classify")
async def classify(req: ClassifyRequest):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {"X-Request-ID": get_correlation_id()}
            r = await client.post(
                f"{settings.ai_service_url}/classify",
                json=req.model_dump(),
                headers=headers,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            # AI classification is an optional enhancement — return a graceful
            # degraded response instead of 502 so the note save flow is not
            # disrupted and the user sees no error toast (#261).
            return {"status": "unavailable", "note_id": req.note_id, "suggestions": []}

@router.get("/usage")
async def usage():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"{settings.ai_service_url}/usage", headers={"X-Request-ID": get_correlation_id()})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return {"ai_enabled": False, "estimated_cost_usd": 0, "error": "AI service unreachable"}
