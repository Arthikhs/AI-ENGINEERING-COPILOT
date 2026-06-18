"""
Multi-Tenant SaaS — Organizations API
Org creation, member management, role-based access (Admin/Developer/Viewer).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from models.models import User, Organization, OrganizationMember, OrgRole, Repository
from database import get_db
from api.auth import get_current_user
import re

router = APIRouter(prefix="/orgs", tags=["organizations"])


# ── Request / Response models ──────────────────────────────────────────────────

class CreateOrgRequest(BaseModel):
    name: str
    description: Optional[str] = None

class InviteMemberRequest(BaseModel):
    username: str
    role: OrgRole = OrgRole.DEVELOPER

class UpdateRoleRequest(BaseModel):
    role: OrgRole


# ── Helpers ────────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

async def _get_member(org_id, user_id, db: AsyncSession) -> OrganizationMember:
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return member

async def _require_admin(org_id, user_id, db: AsyncSession):
    member = await _get_member(org_id, user_id, db)
    if member.role != OrgRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("")
async def create_organization(
    body: CreateOrgRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization. Creator becomes Admin."""
    slug = _slugify(body.name)
    # Ensure unique slug
    existing = await db.execute(select(Organization).where(Organization.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{str(current_user.id)[:6]}"

    org = Organization(name=body.name, slug=slug, description=body.description)
    db.add(org)
    await db.flush()

    # Creator is Admin
    member = OrganizationMember(org_id=org.id, user_id=current_user.id, role=OrgRole.ADMIN)
    db.add(member)
    await db.commit()
    await db.refresh(org)

    return {"id": str(org.id), "name": org.name, "slug": org.slug, "role": "admin"}


@router.get("")
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all organizations the current user belongs to."""
    result = await db.execute(
        select(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.org_id == Organization.id)
        .where(OrganizationMember.user_id == current_user.id)
    )
    rows = result.fetchall()
    return [
        {
            "id": str(org.id), "name": org.name, "slug": org.slug,
            "description": org.description, "role": member.role,
        }
        for org, member in rows
    ]


@router.get("/{org_id}/members")
async def list_members(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_member(org_id, current_user.id, db)  # must be a member
    result = await db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.org_id == org_id)
    )
    return [
        {
            "user_id": str(u.id), "username": u.username,
            "avatar_url": u.avatar_url, "role": m.role, "joined_at": m.joined_at,
        }
        for m, u in result.fetchall()
    ]


@router.post("/{org_id}/members")
async def invite_member(
    org_id: str,
    body: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a user to the org. Admin only."""
    await _require_admin(org_id, current_user.id, db)

    # Find user by username
    result = await db.execute(select(User).where(User.username == body.username))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail=f"User '{body.username}' not found")

    # Check not already member
    existing = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == target.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a member")

    member = OrganizationMember(org_id=org_id, user_id=target.id, role=body.role)
    db.add(member)
    await db.commit()
    return {"message": f"{body.username} added as {body.role}"}


@router.patch("/{org_id}/members/{user_id}")
async def update_member_role(
    org_id: str,
    user_id: str,
    body: UpdateRoleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a member's role. Admin only."""
    await _require_admin(org_id, current_user.id, db)
    member = await _get_member(org_id, user_id, db)
    member.role = body.role
    await db.commit()
    return {"message": f"Role updated to {body.role}"}


@router.delete("/{org_id}/members/{user_id}")
async def remove_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member. Admin only."""
    await _require_admin(org_id, current_user.id, db)
    member = await _get_member(org_id, user_id, db)
    await db.delete(member)
    await db.commit()
    return {"message": "Member removed"}


@router.get("/{org_id}/repos")
async def list_org_repos(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all repositories in an organization."""
    await _get_member(org_id, current_user.id, db)
    result = await db.execute(
        select(Repository).where(Repository.org_id == org_id)
    )
    repos = result.scalars().all()
    return [
        {
            "id": str(r.id), "full_name": r.full_name, "name": r.name,
            "language": r.language, "is_indexed": r.is_indexed,
            "total_files": r.total_files, "total_chunks": r.total_chunks,
        }
        for r in repos
    ]
