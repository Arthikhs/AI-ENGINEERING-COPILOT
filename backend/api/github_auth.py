import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import User
from database import get_db
from api.auth import create_access_token
from config import get_settings
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.get("/github/login")
async def github_login():
    """Redirect URL for GitHub OAuth."""
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope=repo,user:email"
    )
    return {"auth_url": github_auth_url}


@router.get("/github/callback")
async def github_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handle GitHub OAuth callback and issue JWT."""
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()

    github_token = token_data.get("access_token")
    if not github_token:
        raise HTTPException(status_code=400, detail="GitHub OAuth failed")

    # Fetch GitHub user info
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {github_token}"},
        )
        github_user = user_resp.json()

    # Upsert user
    result = await db.execute(select(User).where(User.github_id == str(github_user["id"])))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            github_id=str(github_user["id"]),
            username=github_user["login"],
            email=github_user.get("email"),
            avatar_url=github_user.get("avatar_url"),
            github_access_token=github_token,
        )
        db.add(user)
    else:
        user.github_access_token = github_token
        user.avatar_url = github_user.get("avatar_url")

    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id), user.username)
    return TokenResponse(
        access_token=token,
        user={"id": str(user.id), "username": user.username, "avatar_url": user.avatar_url},
    )
