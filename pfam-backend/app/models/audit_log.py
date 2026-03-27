import enum

from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now
from datetime import datetime
from sqlalchemy import DateTime


class ActorType(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only audit trail — never UPDATE or DELETE rows from this table."""

    __tablename__ = "audit_log"

    # created_at only — no updated_at, audit log is immutable
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=False
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Who performed the action: a user or the system (background worker)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[ActorType] = mapped_column(
        SAEnum(ActorType, name="actor_type"),
        nullable=False,
        default=ActorType.SYSTEM,
    )

    # What happened (e.g. "rule_triggered", "campaign_paused", "user_role_changed", "login")
    action_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    # What entity was affected (e.g. "campaign", "adset", "user", "rule")
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Ad platform context for automation actions
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("automation_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Profit metric snapshot that triggered the action (JSON)
    metric_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Raw platform API request/response for debugging
    api_request_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    api_response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Legacy: kept for Phase-1 auth/RBAC events
    target_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

