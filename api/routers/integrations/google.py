"""Google Calendar, Tasks, Gmail and Contacts integration router."""

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services import google_service as gs
from services.auth_service import get_current_user

router = APIRouter(prefix="/integrations/google", tags=["integrations"])


class GoogleAuthUrl(BaseModel):
    url: str


class GoogleTokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str
    scope: str | None = None


@router.get("/auth", response_model=GoogleAuthUrl)
async def get_google_auth_url():
    """Return the Google OAuth consent URL."""
    try:
        url = gs.get_auth_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@router.get("/callback")
async def google_oauth_callback(code: str = "", error: str = ""):
    """Handle the OAuth callback from Google."""
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        tokens = await gs.exchange_code(code)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google token exchange failed")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in", 0),
        "token_type": tokens.get("token_type", "Bearer"),
        "scope": tokens.get("scope"),
    }


@router.get("/calendars")
async def get_google_calendars(token: str, user: dict = Depends(get_current_user)):
    """List Google Calendars for the provided access token."""
    try:
        return await gs.list_calendars(token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/calendars/{calendar_id}/events")
async def get_google_calendar_events(
    calendar_id: str,
    token: str,
    user: dict = Depends(get_current_user),
):
    """List events from a Google Calendar."""
    try:
        return await gs.list_events(token, calendar_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/tasks")
async def get_google_task_lists(token: str, user: dict = Depends(get_current_user)):
    """List Google Tasks lists for the provided access token."""
    try:
        return await gs.list_task_lists(token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/gmail")
async def get_google_gmail_messages(
    token: str,
    max_results: int = 10,
    user: dict = Depends(get_current_user),
):
    """List recent Gmail message headers."""
    try:
        return await gs.list_gmail_messages(token, max_results)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/contacts")
async def get_google_contacts(
    token: str,
    page_size: int = 50,
    user: dict = Depends(get_current_user),
):
    """List Google Contacts."""
    try:
        return await gs.list_contacts(token, page_size)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")
