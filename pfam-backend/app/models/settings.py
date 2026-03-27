"""Settings models: COGS configuration entries per organization."""
import enum

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CogsScope(str, enum.Enum):
    """The level at which a COGS setting applies."""
    SKU = "sku"
    CATEGORY = "category"
    GLOBAL = "global"


class CogsType(str, enum.Enum):
    """Whether the COGS value is an absolute amount or a revenue percentage."""
    ABSOLUTE = "absolute"      # cogs_value is in cogs_value_cents
    PERCENTAGE = "percentage"  # cogs_value is stored in cogs_value_pct


class CogsDataSource(str, enum.Enum):
    """How this COGS value was provided."""
    SHOPIFY = "shopify"   # Imported from Shopify variant cost_per_item
    CSV = "csv"           # Uploaded via CSV
    MANUAL = "manual"     # Entered manually in the UI
    ESTIMATED = "estimated"  # Category-level percentage default


class CogsSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single COGS configuration entry for a SKU, category, or global fallback.

    Priority order (highest to lowest):
      1. SKU-level absolute  →  scope=SKU,      type=ABSOLUTE
      2. SKU-level percent   →  scope=SKU,      type=PERCENTAGE
      3. Category absolute   →  scope=CATEGORY, type=ABSOLUTE
      4. Category percent    →  scope=CATEGORY, type=PERCENTAGE
      5. Global percent      →  scope=GLOBAL,   type=PERCENTAGE

    Unique on (org_id, scope, scope_value) so there is exactly one active
    setting per SKU/category/global at any time.

    Changes are stored as new rows with new created_at/updated_at timestamps;
    caller code must handle version history if needed (Phase 9 COGS tracking).
    """

    __tablename__ = "cogs_settings"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "scope", "scope_value",
            name="uq_cogs_settings_org_scope_value",
        ),
        Index("ix_cogs_settings_org_scope", "org_id", "scope"),
    )

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scope: Mapped[CogsScope] = mapped_column(
        SAEnum(CogsScope, name="cogs_scope"),
        nullable=False,
    )
    # The specific SKU string, category string, or "global" for GLOBAL scope
    scope_value: Mapped[str] = mapped_column(String(255), nullable=False)

    cogs_type: Mapped[CogsType] = mapped_column(
        SAEnum(CogsType, name="cogs_type"),
        nullable=False,
    )
    # Used when cogs_type=ABSOLUTE: COGS per unit in integer cents
    cogs_value_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Used when cogs_type=PERCENTAGE: e.g. 0.40000 = 40%
    cogs_value_pct: Mapped[Numeric | None] = mapped_column(Numeric(6, 5), nullable=True)

    # ISO 4217 currency for absolute values (ignored for percentage type)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    source: Mapped[CogsDataSource] = mapped_column(
        SAEnum(CogsDataSource, name="cogs_data_source"),
        nullable=False,
        default=CogsDataSource.MANUAL,
    )

    # Actor who last modified this setting (for audit purposes)
    updated_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
