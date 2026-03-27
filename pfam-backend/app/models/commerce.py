"""Commerce models: Shopify Orders, LineItems, and Returns (Refunds)."""
import enum

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CogsSource(str, enum.Enum):
    """Where the COGS value for this line item originated."""
    SHOPIFY = "shopify"
    CSV = "csv"
    MANUAL = "manual"
    ESTIMATED = "estimated"


class ReturnReasonCategory(str, enum.Enum):
    """High-level classification of return reason (from Shopify refund notes)."""
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    CHANGED_MIND = "changed_mind"
    SIZING = "sizing"
    OTHER = "other"


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Shopify order ingested for a connected store.

    Unique constraint on (store_id, shopify_order_id) ensures idempotent upserts.
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("store_id", "shopify_order_id", name="uq_orders_store_shopify_id"),
        # High-freq index for incremental sync and date-range queries (SRS Section 8)
        Index("ix_orders_store_created_at", "store_id", "shopify_created_at"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[str] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Shopify's native order ID (string to cover GID and integer IDs)
    shopify_order_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # The UTC timestamp when the order was placed in Shopify
    shopify_created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # All monetary values in integer cents.
    # Currency is stored per-order since multi-currency stores are supported.
    total_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_discounts_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # ISO 4217 currency the order was placed in
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    financial_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fulfillment_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # UTM / click-id fields parsed from Shopify order note attributes or landing URLs
    utm_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(128), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fbclid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    gclid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    ttclid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)


class LineItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Individual product line within an order, including COGS data.

    Unique constraint on (order_id, shopify_line_item_id) enables safe upserts
    when Shopify re-delivers order data with updated line items.
    """

    __tablename__ = "line_items"
    __table_args__ = (
        UniqueConstraint(
            "order_id", "shopify_line_item_id",
            name="uq_line_items_order_shopify_id",
        ),
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

    # Shopify's native line item ID (for idempotency key)
    shopify_line_item_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Product/variant identifiers
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    variant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # All monetary values as integer cents
    unit_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_discount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # COGS per unit; nullable until COGS data is configured
    unit_cogs_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    unit_cogs_source: Mapped[CogsSource | None] = mapped_column(
        SAEnum(CogsSource, name="cogs_source"),
        nullable=True,
    )


class Return(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A Shopify refund event, captured at line-item granularity where available."""

    __tablename__ = "returns"
    __table_args__ = (
        UniqueConstraint("order_id", "shopify_refund_id", name="uq_returns_order_shopify_id"),
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
    # Nullable: a refund may cover the whole order without line-item breakdown
    line_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("line_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Shopify's refund ID for idempotency
    shopify_refund_id: Mapped[str] = mapped_column(String(64), nullable=False)

    refund_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Human-readable reason from Shopify refund note
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_category: Mapped[ReturnReasonCategory | None] = mapped_column(
        SAEnum(ReturnReasonCategory, name="return_reason_category"),
        nullable=True,
    )

    # Defective/Fulfillment returns are NOT attributed to ad campaign performance
    is_fulfillment_fault: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
