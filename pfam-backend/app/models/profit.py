"""Profit engine model: immutable profit metric snapshots per ad set per window."""
import enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class WindowType(str, enum.Enum):
    """Time window granularity for aggregated profit metrics."""
    DAILY = "daily"
    ROLLING_7D = "7d"
    ROLLING_14D = "14d"
    ROLLING_30D = "30d"


class ProfitMetric(UUIDPrimaryKeyMixin, Base):
    """Computed profit snapshot for one ad set over one time window.

    Formula (all values in integer cents):
        net_profit = attributed_revenue - spend - attributed_cogs - estimated_returns - platform_fees

    Records are append-only immutable snapshots — the unique constraint on
    (adset_id, window_type, window_start, window_end) means re-computing the
    same window is an upsert (overwrite) in the same transaction, not a new row.

    No updated_at column — computed_at marks when this snapshot was calculated.
    """

    __tablename__ = "profit_metrics"
    __table_args__ = (
        # Idempotency: one snapshot per ad set × window combination
        UniqueConstraint(
            "adset_id", "window_type", "window_start", "window_end",
            name="uq_profit_metrics_adset_window",
        ),
        # Primary query path for rule evaluation and dashboard queries (SRS Section 8)
        Index(
            "ix_profit_metrics_adset_window",
            "adset_id", "window_type", "window_start", "window_end",
        ),
        Index("ix_profit_metrics_org_id", "org_id"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    adset_id: Mapped[str] = mapped_column(
        ForeignKey("ad_sets.id", ondelete="CASCADE"),
        nullable=False,
    )

    window_type: Mapped[WindowType] = mapped_column(
        SAEnum(WindowType, name="window_type"),
        nullable=False,
    )
    window_start: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)

    # ── Core profit formula inputs, all in integer cents ─────────────────────
    # Actual ad spend from platform API for this window
    spend_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Revenue from orders attributed to this ad set in this window
    attributed_revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # COGS: sum(unit_cogs × quantity) for all attributed order line items
    attributed_cogs_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Estimated returns: sum(order_revenue × sku_return_rate) for attributed orders
    estimated_returns_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Platform/payment fees: configurable % + fixed per transaction
    platform_fees_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # ── Derived metrics ──────────────────────────────────────────────────────
    # net_profit = attributed_revenue - spend - cogs - returns - fees
    net_profit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Net profit margin as percentage: (net_profit / attributed_revenue) * 100
    # Stored as Numeric(8,4) e.g. 12.3456%
    net_profit_pct: Mapped[Numeric | None] = mapped_column(Numeric(8, 4), nullable=True)
    # True ROAS = attributed_revenue / spend; Numeric(10,4) covers values like 3.5000
    true_roas: Mapped[Numeric | None] = mapped_column(Numeric(10, 4), nullable=True)

    # ── Quality / coverage metadata ──────────────────────────────────────────
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Percentage of orders that could be attributed (vs. blended/unattributed)
    attribution_coverage_pct: Mapped[Numeric | None] = mapped_column(Numeric(5, 2), nullable=True)

    # UTC timestamp when this snapshot was calculated (immutable after insert)
    computed_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
