import httpx
from fastapi import APIRouter, HTTPException
from config import settings

router = APIRouter(prefix="/integrations/github", tags=["integrations"])

GITHUB_API = "https://api.github.com"


def _headers():
    if not settings.github_token:
        raise HTTPException(status_code=400, detail="GitHub token not configured")
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@router.get("/status")
def github_status():
    return {"connected": bool(settings.github_token), "username": settings.github_username or None}


@router.get("/issues")
async def get_assigned_issues():
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{GITHUB_API}/issues",
            headers=_headers(),
            params={"filter": "assigned", "state": "open", "per_page": 20},
        )
        r.raise_for_status()
        issues = r.json()
        return [
            {
                "id": i["id"],
                "number": i["number"],
                "title": i["title"],
                "repo": i["repository"]["full_name"] if "repository" in i else "",
                "url": i["html_url"],
                "labels": [l["name"] for l in i.get("labels", [])],
                "updated_at": i["updated_at"],
            }
            for i in issues
        ]
