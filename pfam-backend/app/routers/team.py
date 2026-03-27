from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.middleware.rbac import UserContext, get_current_user_context, require_roles
from app.models.user import User, UserRole
from app.services.auth.audit import append_audit_event

router = APIRouter(prefix="/team", tags=["Team"])


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    clerk_user_id: str
    org_id: str
    role: UserRole
    is_active: bool


class TeamMemberListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TeamMemberResponse]


class InviteMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clerk_user_id: str = Field(min_length=1, max_length=128)
    role: UserRole = Field(default=UserRole.READ_ONLY)


class UpdateRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole


def _to_member_response(user: User) -> TeamMemberResponse:
    return TeamMemberResponse(
        id=user.id,
        clerk_user_id=user.clerk_user_id,
        org_id=user.org_id,
        role=user.role,
        is_active=user.is_active,
    )


@router.get(
    "/members",
    response_model=TeamMemberListResponse,
    dependencies=[
        Depends(
            require_roles(
                UserRole.OWNER,
                UserRole.ADMIN,
                UserRole.ANALYST,
                UserRole.READ_ONLY,
            )
        )
    ],
)
async def list_team_members(
    context: Annotated[UserContext, Depends(get_current_user_context)],
    db: AsyncSession = Depends(get_db_session),
) -> TeamMemberListResponse:
    stmt = (
        select(User)
        .where(User.org_id == context.org_id)
        .order_by(User.created_at.asc())
    )
    result = await db.execute(stmt)
    members = result.scalars().all()
    return TeamMemberListResponse(items=[_to_member_response(member) for member in members])


@router.post(
    "/invite",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.OWNER, UserRole.ADMIN))],
)
async def invite_team_member(
    payload: InviteMemberRequest,
    context: Annotated[UserContext, Depends(get_current_user_context)],
    db: AsyncSession = Depends(get_db_session),
) -> TeamMemberResponse:
    stmt = select(User).where(
        User.org_id == context.org_id,
        User.clerk_user_id == payload.clerk_user_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "MEMBER_EXISTS", "message": "Member already exists in organization"},
        )

    new_member = User(
        org_id=context.org_id,
        clerk_user_id=payload.clerk_user_id,
        role=payload.role,
        is_active=True,
    )
    db.add(new_member)
    await db.flush()

    await append_audit_event(
        db,
        org_id=context.org_id,
        event_type="team.member_invited",
        actor_user_id=context.db_user_id,
        target_user_id=new_member.id,
        metadata_json={"role": payload.role.value},
    )
    await db.commit()
    await db.refresh(new_member)
    return _to_member_response(new_member)


@router.patch(
    "/members/{member_id}/role",
    response_model=TeamMemberResponse,
    dependencies=[Depends(require_roles(UserRole.OWNER, UserRole.ADMIN))],
)
async def update_member_role(
    payload: UpdateRoleRequest,
    member_id: Annotated[str, Path(min_length=1)],
    context: Annotated[UserContext, Depends(get_current_user_context)],
    db: AsyncSession = Depends(get_db_session),
) -> TeamMemberResponse:
    stmt = select(User).where(User.org_id == context.org_id, User.id == member_id)
    member = (await db.execute(stmt)).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MEMBER_NOT_FOUND", "message": "Team member not found"},
        )

    if context.role == UserRole.ADMIN and member.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ROLE_FORBIDDEN", "message": "Admin cannot modify owner role"},
        )

    previous_role = member.role
    member.role = payload.role
    await db.flush()

    await append_audit_event(
        db,
        org_id=context.org_id,
        event_type="team.member_role_updated",
        actor_user_id=context.db_user_id,
        target_user_id=member.id,
        metadata_json={"from_role": previous_role.value, "to_role": payload.role.value},
    )
    await db.commit()
    await db.refresh(member)
    return _to_member_response(member)


@router.delete(
    "/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(UserRole.OWNER, UserRole.ADMIN))],
)
async def remove_team_member(
    member_id: Annotated[str, Path(min_length=1)],
    context: Annotated[UserContext, Depends(get_current_user_context)],
    db: AsyncSession = Depends(get_db_session),
) -> None:
    stmt = select(User).where(User.org_id == context.org_id, User.id == member_id)
    member = (await db.execute(stmt)).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MEMBER_NOT_FOUND", "message": "Team member not found"},
        )

    if context.role == UserRole.ADMIN and member.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ROLE_FORBIDDEN", "message": "Admin cannot remove owner"},
        )

    target_user_id = member.id
    await db.delete(member)
    await db.flush()

    await append_audit_event(
        db,
        org_id=context.org_id,
        event_type="team.member_removed",
        actor_user_id=context.db_user_id,
        target_user_id=target_user_id,
        metadata_json={},
    )
    await db.commit()
