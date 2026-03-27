"""Notification models: delivery records and settings per organization."""
import enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class NotificationChannel(str, enum.Enum):
    """Supported delivery channels per SRS FR-14."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class Notification(UUIDPrimaryKeyMixin, Base):
    """Record of a single notification delivery attempt.

    Append-only: each retry creates a new row (tracked by retry_count on the
    delivery attempt, not by updating this row). Kept for 90-day history per SRS.
    """

    __tablename__ = "notifications"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Trigger category, e.g. "rule_triggered", "sync_failure", "payment_failed"
    trigger_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, name="notification_channel"),
        nullable=False,
        index=True,
    )

    # Full rendered payload (email body, Slack block, Webhook JSON)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Delivery timestamps and status
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    delivered_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"),
        nullable=False,
        default=DeliveryStatus.PENDING,
    )

    # How many delivery attempts have been made (0 = first attempt)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Error message from last failed attempt
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Idempotency key to prevent duplicate deliveries on retry
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )

    # Reference to the rule execution or audit event that triggered this notification
    source_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("automation_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
