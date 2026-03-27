"""Attribution models: AttributedOrder (linking orders to ad campaigns) and SkuReturnRate."""
import enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class AttributionTier(int, enum.Enum):
    """5-tier attribution waterfall as defined in PFAM SRS Section 8."""
    DIRECT_CLICK = 1       # fbclid / gclid / ttclid direct match — confidence 0.95
    CONVERSION_ID = 2      # Meta Pixel / Google Tag conversion event match — confidence 0.85
    SKU_WEIGHTED = 3       # SKU-weighted proportional attribution — confidence 0.70
    BLENDED = 4            # Blended by spend volume — confidence 0.50
    ML_PREDICTED = 5       # XGBoost model inference — confidence 0.60–0.85


class AttributionMethod(str, enum.Enum):
    """The specific matching logic used within a tier."""
    FBCLID = "fbclid"
    GCLID = "gclid"
    TTCLID = "ttclid"
    CONVERSION_EVENT = "conversion_event"
    SKU_WEIGHTED = "sku_weighted"
    BLENDED_SPEND = "blended_spend"
    ML_XGBOOST = "ml_xgboost"


class AttributedOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The result of the attribution engine linking one order to one ad set.

    A single order will have at most one AttributedOrder record per ad set.
    The unique constraint on (order_id, adset_id) enforces idempotency —
    re-running attribution for the same order/adset pair is an upsert.
    """

    __tablename__ = "attributed_orders"
    __table_args__ = (
        # Idempotency: one attribution result per order × ad set pair
        UniqueConstraint("order_id", "adset_id", name="uq_attributed_orders_order_adset"),
        # Query performance: aggregating revenue per ad set within a window
        Index("ix_attributed_orders_adset_window", "adset_id", "window_start", "window_end"),
        # Duplicate attribution detection
        Index("ix_attributed_orders_order_adset", "order_id", "adset_id"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adset_id: Mapped[str] = mapped_column(
        ForeignKey("ad_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attribution_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    # Confidence score 0.0–1.0 stored as Numeric(5,4) e.g. 0.9500
    confidence_score: Mapped[Numeric] = mapped_column(Numeric(5, 4), nullable=False)

    attribution_method: Mapped[AttributionMethod] = mapped_column(
        SAEnum(AttributionMethod, name="attribution_method"),
        nullable=False,
    )
    # The click ID value that was matched (null for probabilistic tiers)
    matched_click_id: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Revenue attributed to this adset from this order, in integer cents
    attributed_revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # The attribution window this record was computed within
    window_start: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)


class SkuReturnRate(UUIDPrimaryKeyMixin, Base):
    """Trailing historical return rate per SKU, used by the profit engine.

    Unique on (org_id, sku) — one rate record per SKU per organization.
    Recomputed nightly by the returns engine.
    """

    __tablename__ = "sku_return_rates"
    __table_args__ = (
        UniqueConstraint("org_id", "sku", name="uq_sku_return_rates_org_sku"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Trailing rates stored as Numeric(6,5) e.g. 0.12000 = 12%
    trailing_90d_rate: Mapped[Numeric | None] = mapped_column(Numeric(6, 5), nullable=True)
    trailing_180d_rate: Mapped[Numeric | None] = mapped_column(Numeric(6, 5), nullable=True)
    # Optional merchant override (takes precedence over computed rates)
    manual_override_rate: Mapped[Numeric | None] = mapped_column(Numeric(6, 5), nullable=True)

    last_computed_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
