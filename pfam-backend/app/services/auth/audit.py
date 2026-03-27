from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def append_audit_event(
    session: AsyncSession,
    *,
    org_id: str,
    event_type: str,
    actor_user_id: str | None,
    target_user_id: str | None = None,
    metadata_json: dict | None = None,
) -> None:
    # Append-only behavior: create-only writes to audit_log.
    entry = AuditLog(
        org_id=org_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_user_id=target_user_id,
        metadata_json=metadata_json or {},
    )
    session.add(entry)
    await session.flush()
