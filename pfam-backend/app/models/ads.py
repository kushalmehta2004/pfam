"""Ad hierarchy models: Campaign, AdSet, AdInsight (daily metrics)."""
import enum
from datetime import date as Date

from sqlalchemy import JSON, BigInteger, Date as SADate, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy import Enum as SAEnum, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    DELETED = "deleted"
    UNKNOWN = "unknown"


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ad platform campaign entity. One level above AdSet."""

    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint(
            "ad_account_id", "platform_campaign_id",
            name="uq_campaigns_account_platform_id",
        ),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ad_account_id: Mapped[str] = mapped_column(
        ForeignKey("ad_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The ID as it appears in the ad platform (e.g. Meta campaign ID)
    platform_campaign_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[AdStatus] = mapped_column(
        SAEnum(AdStatus, name="ad_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AdStatus.UNKNOWN,
    )
    objective: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Budgets stored as integer cents
    daily_budget_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lifetime_budget_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    start_date: Mapped[Date | None] = mapped_column(SADate, nullable=True)
    end_date: Mapped[Date | None] = mapped_column(SADate, nullable=True)


class AdSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ad set / ad group entity (directly below Campaign)."""

    __tablename__ = "ad_sets"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "platform_adset_id",
            name="uq_adsets_campaign_platform_id",
        ),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[str] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform_adset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[AdStatus] = mapped_column(
        # Reuse the enum created above
        SAEnum(AdStatus, name="ad_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AdStatus.UNKNOWN,
    )

    daily_budget_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Summarized targeting stored as JSON blob (not queried, for display only)
    targeting_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AdInsight(UUIDPrimaryKeyMixin, Base):
    """Daily aggregated spend + impression metrics per ad set.

    No updated_at — records are upserted by (adset_id, date); once inserted
    they may be overwritten in the same transaction but never have row-level
    history. A unique constraint enforces idempotency.
    """

    __tablename__ = "ad_insights"
    __table_args__ = (
        # Idempotency: re-syncing the same day must not produce duplicates
        UniqueConstraint("adset_id", "date", name="uq_ad_insights_adset_date"),
        # High-freq query index for time-series spend queries and dashboard
        Index("ix_ad_insights_adset_date", "adset_id", "date"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adset_id: Mapped[str] = mapped_column(
        ForeignKey("ad_sets.id", ondelete="CASCADE"),
        nullable=False,
        # Covered by the composite index above
    )

    date: Mapped[Date] = mapped_column(SADate, nullable=False)

    # All monetary values in integer cents to avoid float precision issues
    spend_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    conversion_value_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Raw counts
    impressions: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reach: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    conversions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Derived rate metrics stored as Numeric for display; NOT used for profit math
    # (profit math uses raw cents fields above)
    cpm: Mapped[Numeric | None] = mapped_column(Numeric(18, 6), nullable=True)
    cpc: Mapped[Numeric | None] = mapped_column(Numeric(18, 6), nullable=True)
    ctr: Mapped[Numeric | None] = mapped_column(Numeric(10, 6), nullable=True)


class Ad(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Individual ad creative entity (directly below AdSet)."""

    __tablename__ = "ads"
    __table_args__ = (
        UniqueConstraint(
            "adset_id", "platform_ad_id",
            name="uq_ads_adset_platform_id",
        ),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adset_id: Mapped[str] = mapped_column(
        ForeignKey("ad_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform_ad_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[AdStatus] = mapped_column(
        SAEnum(AdStatus, name="ad_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AdStatus.UNKNOWN,
    )
    creative_thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

