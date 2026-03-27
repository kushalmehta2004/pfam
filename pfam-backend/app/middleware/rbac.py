from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.middleware.auth import verify_clerk_jwt
from app.models.user import User, UserRole
from app.services.auth.audit import append_audit_event


class UserContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    org_id: str
    role: UserRole
    db_user_id: str


async def get_current_user_context(
    request: Request,
    jwt_payload: dict = Depends(verify_clerk_jwt),
    db: AsyncSession = Depends(get_db_session),
) -> UserContext:
    org_id = str(jwt_payload.get("org_id", ""))
    clerk_user_id = str(jwt_payload.get("sub", ""))
    if not org_id or not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CLAIMS", "message": "Missing org_id or user_id"},
        )

    stmt = select(User).where(
        User.org_id == org_id,
        User.clerk_user_id == clerk_user_id,
        User.is_active.is_(True),
    )
    result = await db.execute(stmt)
    db_user = result.scalar_one_or_none()
    if db_user is None:
        await append_audit_event(
            db,
            org_id=org_id,
            event_type="auth.user_not_provisioned",
            actor_user_id=None,
            metadata_json={"clerk_user_id": clerk_user_id},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_PROVISIONED", "message": "User is not provisioned"},
        )

    request.state.org_id = org_id
    request.state.user_id = clerk_user_id
    request.state.db_user_id = db_user.id
    request.state.role = db_user.role.value
    await append_audit_event(
        db,
        org_id=org_id,
        event_type="auth.user_authenticated",
        actor_user_id=db_user.id,
        metadata_json={},
    )
    await db.commit()
    return UserContext(
        user_id=clerk_user_id,
        org_id=org_id,
        role=db_user.role,
        db_user_id=db_user.id,
    )


def require_roles(*allowed_roles: UserRole) -> Callable:
    allowed = set(allowed_roles)

    async def role_guard(
        context: UserContext = Depends(get_current_user_context),
        db: AsyncSession = Depends(get_db_session),
    ) -> UserContext:
        if context.role not in allowed:
            await append_audit_event(
                db,
                org_id=context.org_id,
                event_type="auth.role_denied",
                actor_user_id=context.db_user_id,
                metadata_json={
                    "required_roles": sorted(role.value for role in allowed),
                    "actual_role": context.role.value,
                },
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ROLE_FORBIDDEN", "message": "Insufficient role permissions"},
            )
        return context

    return role_guard
