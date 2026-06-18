"""
Prompt Management System API
Store prompt versions, history, A/B test configurations, and rollback.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from database import get_db
from api.auth import get_current_user
from models.models import User, PromptTemplate, PromptVersion

router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptCreateRequest(BaseModel):
    name: str
    agent_type: str
    content: str
    description: Optional[str] = None
    ab_group: Optional[str] = None   # "A" | "B" | None


class PromptUpdateRequest(BaseModel):
    content: str
    description: Optional[str] = None
    ab_group: Optional[str] = None


# ── List all prompt templates ──────────────────────────────────────────────────

@router.get("")
async def list_prompts(
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(PromptTemplate)
    if agent_type:
        q = q.where(PromptTemplate.agent_type == agent_type)
    result = await db.execute(q.order_by(PromptTemplate.created_at.desc()))
    templates = result.scalars().all()
    return {
        "prompts": [
            {
                "id": str(t.id),
                "name": t.name,
                "agent_type": t.agent_type,
                "description": t.description,
                "active_version": t.active_version,
                "ab_group": t.ab_group,
                "created_at": t.created_at.isoformat(),
            }
            for t in templates
        ]
    }


# ── Create new prompt ──────────────────────────────────────────────────────────

@router.post("")
async def create_prompt(
    body: PromptCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    template = PromptTemplate(
        name=body.name,
        agent_type=body.agent_type,
        description=body.description,
        active_version=1,
        ab_group=body.ab_group,
        created_by=current_user.id,
    )
    db.add(template)
    await db.flush()  # get template.id

    version = PromptVersion(
        template_id=template.id,
        version=1,
        content=body.content,
        created_by=current_user.id,
    )
    db.add(version)
    await db.commit()
    return {"id": str(template.id), "version": 1}


# ── Get prompt with all versions ───────────────────────────────────────────────

@router.get("/{prompt_id}")
async def get_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Prompt not found")

    versions_result = await db.execute(
        select(PromptVersion)
        .where(PromptVersion.template_id == prompt_id)
        .order_by(PromptVersion.version.desc())
    )
    versions = versions_result.scalars().all()

    return {
        "id": str(template.id),
        "name": template.name,
        "agent_type": template.agent_type,
        "description": template.description,
        "active_version": template.active_version,
        "ab_group": template.ab_group,
        "versions": [
            {
                "version": v.version,
                "content": v.content,
                "created_at": v.created_at.isoformat(),
                "is_active": v.version == template.active_version,
            }
            for v in versions
        ],
    }


# ── Add new version ────────────────────────────────────────────────────────────

@router.post("/{prompt_id}/versions")
async def add_version(
    prompt_id: str,
    body: PromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Get max version
    max_result = await db.execute(
        select(func.max(PromptVersion.version)).where(PromptVersion.template_id == prompt_id)
    )
    next_version = (max_result.scalar() or 0) + 1

    version = PromptVersion(
        template_id=template.id,
        version=next_version,
        content=body.content,
        created_by=current_user.id,
    )
    db.add(version)
    if body.ab_group is not None:
        template.ab_group = body.ab_group
    await db.commit()
    return {"version": next_version}


# ── Rollback to a specific version ────────────────────────────────────────────

@router.post("/{prompt_id}/rollback/{version}")
async def rollback_prompt(
    prompt_id: str,
    version: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Prompt not found")

    ver_result = await db.execute(
        select(PromptVersion).where(
            PromptVersion.template_id == prompt_id,
            PromptVersion.version == version,
        )
    )
    if not ver_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    template.active_version = version
    await db.commit()
    return {"active_version": version}


# ── Get active prompt content for an agent ────────────────────────────────────

@router.get("/active/{agent_type}")
async def get_active_prompt(
    agent_type: str,
    ab_group: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the active prompt content for a given agent type (used by agents at runtime)."""
    q = select(PromptTemplate).where(PromptTemplate.agent_type == agent_type)
    if ab_group:
        q = q.where(PromptTemplate.ab_group == ab_group)
    result = await db.execute(q.limit(1))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="No prompt found for this agent type")

    ver_result = await db.execute(
        select(PromptVersion).where(
            PromptVersion.template_id == template.id,
            PromptVersion.version == template.active_version,
        )
    )
    version = ver_result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Active version content missing")

    return {
        "id": str(template.id),
        "agent_type": agent_type,
        "version": version.version,
        "content": version.content,
        "ab_group": template.ab_group,
    }
