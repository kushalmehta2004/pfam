"""Platform connector models: Shopify stores and ad platform accounts."""
import enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Platform(str, enum.Enum):
    META = "meta"
    GOOGLE = "google"
    TIKTOK = "tiktok"


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    DISCONNECTED = "disconnected"


class Store(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A connected Shopify store per organization."""

    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("org_id", "shopify_store_id", name="uq_stores_org_shopify_id"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Shopify store domain, e.g. "mystore.myshopify.com"
    shopify_store_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # AES-256 encrypted access token stored as base64
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    # Initialization vector for AES-256 (base64-encoded)
    access_token_iv: Mapped[str] = mapped_column(String(64), nullable=False)

    # Shopify store region / locale (e.g. "us", "eu")
    region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Shopify plan name ingested from store info
    plan: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Sync state
    sync_status: Mapped[SyncStatus] = mapped_column(
        SAEnum(SyncStatus, name="sync_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SyncStatus.PENDING,
    )
    last_sync_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Historical import: how far back the initial import went (days)
    initial_sync_days: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class AdAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A connected ad platform account (Meta / Google / TikTok)."""

    __tablename__ = "ad_accounts"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "platform", "account_id",
            name="uq_ad_accounts_org_platform_account",
        ),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform: Mapped[Platform] = mapped_column(
        SAEnum(Platform, name="ad_platform", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    # Native platform account ID (e.g. Meta act_123456789)
    account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # AES-256 encrypted OAuth access token
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_iv: Mapped[str] = mapped_column(String(64), nullable=False)
    # Encrypted long-lived refresh token (Google OAuth, Meta long-lived token)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_iv: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ISO 4217 currency this account reports in
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    sync_status: Mapped[SyncStatus] = mapped_column(
        SAEnum(SyncStatus, name="sync_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SyncStatus.PENDING,
    )
    last_sync_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
