"""Strava integration router."""

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services import strava_service as ss
from services.auth_service import get_current_user

router = APIRouter(prefix="/integrations/strava", tags=["integrations"])


class StravaAuthUrl(BaseModel):
    url: str


@router.get("/auth", response_model=StravaAuthUrl)
async def get_strava_auth_url():
    """Return the Strava OAuth consent URL."""
    try:
        url = ss.get_auth_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@router.get("/callback")
async def strava_oauth_callback(code: str = "", error: str = ""):
    """Handle the OAuth callback from Strava."""
    if error:
        raise HTTPException(status_code=400, detail=f"Strava OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        tokens = await ss.exchange_code(code)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Strava token exchange failed")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in", 0),
        "token_type": tokens.get("token_type", "Bearer"),
        "athlete": tokens.get("athlete"),
    }


@router.get("/activities")
async def get_strava_activities(
    token: str,
    per_page: int = 30,
    user: dict = Depends(get_current_user),
):
    """List recent Strava activities."""
    try:
        return await ss.list_activities(token, per_page)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Strava API error")


@router.get("/athlete")
async def get_strava_athlete(token: str, user: dict = Depends(get_current_user)):
    """Get the authenticated Strava athlete."""
    try:
        return await ss.get_athlete(token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Strava API error")
