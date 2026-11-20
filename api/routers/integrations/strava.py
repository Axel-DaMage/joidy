"""Strava integration router."""

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from services import oauth_state
from services import strava_service as ss
from services.auth_service import get_current_user

router = APIRouter(prefix="/integrations/strava", tags=["integrations"])


class StravaAuthUrl(BaseModel):
    url: str


@router.get("/auth", response_model=StravaAuthUrl, dependencies=[Depends(get_current_user)])
async def get_strava_auth_url():
    """Return the Strava OAuth consent URL with a signed CSRF ``state`` (#1328)."""
    try:
        state = oauth_state.generate_state("strava")
        url = ss.get_auth_url(state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@router.get("/callback")
async def strava_oauth_callback(code: str = "", error: str = "", state: str = ""):
    """Handle the OAuth callback from Strava."""
    if error:
        raise HTTPException(status_code=400, detail=f"Strava OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    # CSRF gate (#1328): the state must be one this instance signed in /auth.
    # Verified before any token exchange so a forged callback cannot bind an
    # attacker's Strava account here.
    if not oauth_state.verify_state(state, "strava"):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

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
    per_page: int = 30,
    strava_token: str = Header(alias="X-Strava-Token"),
    user: dict = Depends(get_current_user),
):
    """List recent Strava activities.

    The Strava access token travels in the ``X-Strava-Token`` header — never
    as a query param, where it would leak into access logs, browser history
    and Referer headers (#1328). ``Authorization`` is not reused because it
    already carries the app JWT consumed by ``get_current_user``.
    """
    try:
        return await ss.list_activities(strava_token, per_page)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Strava API error")


@router.get("/athlete")
async def get_strava_athlete(
    strava_token: str = Header(alias="X-Strava-Token"),
    user: dict = Depends(get_current_user),
):
    """Get the authenticated Strava athlete. Token via ``X-Strava-Token`` header (#1328)."""
    try:
        return await ss.get_athlete(strava_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Strava API error")
